import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.api.deps import get_db
from app.main import app
from app.models.enums import MilestoneStatus, ProjectStatus
from app.models.models import (
    Contact,
    Customer,
    Milestone,
    Project,
    Role,
    Stream,
    User,
)

IDS = {
    "role_design_leader": uuid.UUID("d7a67e79-dffa-42f8-bea4-f646f73fd3fd"),
    "role_designer": uuid.UUID("85e2fc34-f0f3-468f-9390-9d8efb1c2a4f"),
    "role_surfacer": uuid.UUID("04582a31-25bf-4709-ac44-e6e05aae8406"),
    "user_anurag": uuid.UUID("7cf429ba-ca31-4752-9a03-afa3ba4700a3"),
    "user_binil": uuid.UUID("1bb6229f-dcff-419a-a8fa-2b8a7fd15043"),
    "stream": uuid.UUID("a4b9ba7c-4ff4-4a2c-8dc7-823a7cfacb55"),
    "customer": uuid.UUID("3946c135-d515-4bbd-affb-00b5c1893832"),
    "contact": uuid.UUID("b5301223-164f-4035-8017-252ff0452fa6"),
    "project": uuid.UUID("11111111-1111-1111-1111-111111111101"),
    "milestone": uuid.UUID("22222222-2222-2222-2222-222222222201"),
}

MILESTONE_NAMES = (
    "Feasibility",
    "Blockout",
    "Roughing",
    "Intermediate Review",
    "Final Review",
    "File Release",
    "BOM Release",
)


def _seed_database(session) -> Milestone:
    session.add_all(
        [
            Role(
                id=IDS["role_design_leader"],
                name="Design Leader",
                description="Lead design projects",
            ),
            Role(
                id=IDS["role_designer"],
                name="Designer",
                description="Design work",
            ),
            Role(
                id=IDS["role_surfacer"],
                name="Surfacer",
                description="Surface modeling",
            ),
        ]
    )
    anurag = User(
        id=IDS["user_anurag"],
        role_id=IDS["role_design_leader"],
        email="anurag@prosohm.com",
        password_hash=hash_password("changeme"),
        first_name="Anurag",
        last_name="Mohanan",
        is_active=True,
    )
    binil = User(
        id=IDS["user_binil"],
        role_id=IDS["role_designer"],
        email="binil@prosohm.com",
        password_hash=hash_password("changeme"),
        first_name="Binil",
        last_name="JR",
        is_active=True,
    )
    session.add_all([anurag, binil])
    session.add(
        Stream(
            id=IDS["stream"],
            name="Mold Design",
            description="Mold design projects",
            is_active=True,
        )
    )
    session.add(
        Customer(
            id=IDS["customer"],
            name="TI Automotive",
            code="TI",
            is_active=True,
        )
    )
    session.add(
        Contact(
            id=IDS["contact"],
            customer_id=IDS["customer"],
            first_name="Steve",
            last_name="Johnson",
            is_primary=True,
        )
    )
    session.add(
        Project(
            id=IDS["project"],
            tool_number="T-100",
            part_description="Test part",
            customer_id=IDS["customer"],
            customer_contact_id=IDS["contact"],
            design_leader_id=IDS["user_anurag"],
            designer_id=IDS["user_binil"],
            stream_id=IDS["stream"],
            code="TEST-001",
            quoted_hours=Decimal("120.00"),
            actual_hours=Decimal("0"),
            due_date=date(2026, 7, 1),
            status=ProjectStatus.in_progress,
        )
    )
    milestone = None
    for sort_order, name in enumerate(MILESTONE_NAMES, start=1):
        row = Milestone(
            id=IDS["milestone"] if sort_order == 1 else uuid.uuid4(),
            project_id=IDS["project"],
            name=name,
            description=f"{name} milestone",
            status=MilestoneStatus.not_started,
            due_date=date(2026, 6, sort_order),
            sort_order=sort_order,
        )
        session.add(row)
        if sort_order == 1:
            milestone = row
    assert milestone is not None
    session.commit()
    session.refresh(milestone)
    return milestone


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = testing_session_local()
    milestone = _seed_database(session)
    session.close()

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        test_client.milestone_id = str(milestone.id)
        test_client.project_id = str(milestone.project_id)
        test_client.user_id = str(IDS["user_anurag"])
        yield test_client

    app.dependency_overrides.clear()
