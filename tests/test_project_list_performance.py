import time
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

import app.models  # noqa: F401
from app.crud import project as project_crud
from app.db.base import Base
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth
from app.models.models import Contact, Customer, Milestone, Project, Role, Stream, User


@pytest.fixture
def metrics_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    role = Role(name="Admin")
    session.add(role)
    session.flush()
    user = User(
        role_id=role.id,
        email="metrics@prosohm.com",
        password_hash="hash",
        first_name="Metrics",
        last_name="Tester",
        is_active=True,
    )
    customer = Customer(name="Metrics Customer", is_active=True)
    session.add_all([user, customer])
    session.flush()
    contact = Contact(
        customer_id=customer.id,
        first_name="Primary",
        last_name="Contact",
        is_active=True,
    )
    stream = Stream(name="Metrics Stream", is_active=True)
    session.add_all([contact, stream])
    session.flush()

    for index in range(25):
        project = Project(
            tool_number=f"T-{index}",
            part_description=f"Part {index}",
            customer_id=customer.id,
            customer_contact_id=contact.id,
            design_leader_id=user.id,
            stream_id=stream.id,
            code=f"MET-{index}",
            quoted_hours=Decimal("10.00"),
            due_date=date(2026, 8, 1),
            execution_status=ExecutionStatus.currently_being_worked_on,
            health=ProjectHealth.green,
        )
        session.add(project)
        session.flush()
        for sort_order in range(1, 4):
            session.add(
                Milestone(
                    project_id=project.id,
                    name=f"Milestone {sort_order}",
                    status=(
                        MilestoneStatus.completed
                        if sort_order == 1
                        else MilestoneStatus.not_started
                    ),
                    sort_order=sort_order,
                )
            )
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_project_list_uses_batch_progress_queries(metrics_session):
    queries: list[str] = []

    def log_query(_conn, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)

    event.listen(metrics_session.bind, "before_cursor_execute", log_query)
    try:
        start = time.perf_counter()
        rows = project_crud.get_multi_read(metrics_session, skip=0, limit=500)
        elapsed_ms = (time.perf_counter() - start) * 1000
    finally:
        event.remove(metrics_session.bind, "before_cursor_execute", log_query)

    assert len(rows) == 25
    # Query count must stay a small constant (batched), never scale with the
    # number of projects. Base list + progress/milestone batches plus the
    # batched display-name lookups (customers, users, teams, types).
    assert len(queries) <= 8
    assert elapsed_ms < 500
    # Display names are resolved via the batched lookups.
    assert all(row.customer_name == "Metrics Customer" for row in rows)
    assert all(row.design_leader_name == "Metrics Tester" for row in rows)
