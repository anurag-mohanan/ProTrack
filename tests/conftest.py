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

DEFAULT_PASSWORD = "Password@123"

IDS = {
    "role_admin": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "role_pm": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "role_design_leader": uuid.UUID("d7a67e79-dffa-42f8-bea4-f646f73fd3fd"),
    "role_designer": uuid.UUID("85e2fc34-f0f3-468f-9390-9d8efb1c2a4f"),
    "role_senior_designer": uuid.UUID("e5e5e5e5-e5e5-4e5e-8e5e-e5e5e5e5e5e1"),
    "role_junior_designer": uuid.UUID("f6f6f6f6-f6f6-4f6f-8f6f-f6f6f6f6f6f1"),
    "role_surfacer": uuid.UUID("04582a31-25bf-4709-ac44-e6e05aae8406"),
    "user_admin": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    "user_pm": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    "user_anurag": uuid.UUID("7cf429ba-ca31-4752-9a03-afa3ba4700a3"),
    "user_binil": uuid.UUID("1bb6229f-dcff-419a-a8fa-2b8a7fd15043"),
    "user_senior_designer": uuid.UUID("c3c3c3c3-c3c3-4c3c-8c3c-c3c3c3c3c3c3"),
    "user_junior_designer": uuid.UUID("d4d4d4d4-d4d4-4d4d-8d4d-d4d4d4d4d4d4"),
    "user_ranjith": uuid.UUID("731ddf9e-d2d9-450b-a675-cb2ca8a021e3"),
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
            Role(id=IDS["role_admin"], name="Admin", description="Admin"),
            Role(id=IDS["role_pm"], name="Engineering Manager", description="Engineering Manager"),
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
                id=IDS["role_senior_designer"],
                name="Senior Designer",
                description="Senior design work with project edit on assignments",
            ),
            Role(
                id=IDS["role_junior_designer"],
                name="Junior Designer",
                description="Entry-level design work and time logging",
            ),
            Role(
                id=IDS["role_surfacer"],
                name="Surfacer",
                description="Surface modeling",
            ),
        ]
    )
    password_hash = hash_password(DEFAULT_PASSWORD)
    session.add_all(
        [
            User(
                id=IDS["user_admin"],
                role_id=IDS["role_admin"],
                email="admin@prosohm.com",
                password_hash=password_hash,
                first_name="System",
                last_name="Admin",
                is_active=True,
            ),
            User(
                id=IDS["user_pm"],
                role_id=IDS["role_pm"],
                email="pm@prosohm.com",
                password_hash=password_hash,
                first_name="Project",
                last_name="Manager",
                is_active=True,
            ),
            User(
                id=IDS["user_anurag"],
                role_id=IDS["role_design_leader"],
                email="anurag@prosohm.com",
                password_hash=password_hash,
                first_name="Anurag",
                last_name="Mohanan",
                is_active=True,
            ),
            User(
                id=IDS["user_binil"],
                role_id=IDS["role_designer"],
                email="binil@prosohm.com",
                password_hash=password_hash,
                first_name="Binil",
                last_name="JR",
                is_active=True,
            ),
            User(
                id=IDS["user_senior_designer"],
                role_id=IDS["role_senior_designer"],
                email="senior@prosohm.com",
                password_hash=password_hash,
                first_name="Priya",
                last_name="Nair",
                is_active=True,
            ),
            User(
                id=IDS["user_junior_designer"],
                role_id=IDS["role_junior_designer"],
                email="junior@prosohm.com",
                password_hash=password_hash,
                first_name="Alex",
                last_name="Thomas",
                is_active=True,
            ),
            User(
                id=IDS["user_ranjith"],
                role_id=IDS["role_surfacer"],
                email="ranjith@prosohm.com",
                password_hash=password_hash,
                first_name="Ranjith",
                last_name="K",
                is_active=True,
            ),
        ]
    )
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


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture
def seeded_db(test_session_factory):
    session = test_session_factory()
    milestone = _seed_database(session)
    session.close()
    return milestone


@pytest.fixture
def client(test_session_factory, seeded_db):
    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        test_client.milestone_id = str(seeded_db.id)
        test_client.project_id = str(seeded_db.project_id)
        test_client.user_id = str(IDS["user_anurag"])
        test_client.auth_headers = login(test_client, "admin@prosohm.com")
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def session(test_session_factory, seeded_db):
    db = test_session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(client):
    return client.auth_headers
