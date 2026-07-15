import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models.finance  # noqa: F401
from app.core.security import hash_password
from app.db.phase7_schema_sync import ensure_phase7_foundation
from app.db.phase8_schema_sync import ensure_phase8_foundation
from app.db.phase9_schema_sync import ensure_phase9_foundation
from app.db.phase14_kpi_schema_sync import ensure_phase14_kpi_foundation
from app.db.phase17_ebmp_finance_schema_sync import ensure_phase17_ebmp_finance_foundation
from app.db.phase18_finance_annual_plan_schema_sync import (
    ensure_phase18_finance_annual_plan_foundation,
)
from app.db.phase19_timesheet_report_inclusion_schema_sync import (
    ensure_phase19_timesheet_report_inclusion_foundation,
)
from app.db.phase20_project_complexity_schema_sync import ensure_project_complexity
from app.db.phase22_finance_rebuild_schema_sync import ensure_phase22_finance_rebuild_foundation
from app.db.phase23_finance_team_scope_schema_sync import (
    ensure_phase23_finance_team_scope_foundation,
)
from app.db.phase24_user_requires_salary_schema_sync import (
    ensure_phase24_user_requires_salary_foundation,
)
from app.db.phase25_expense_purchase_date_schema_sync import (
    ensure_phase25_expense_purchase_date_foundation,
)
from app.db.phase26_customer_currency_schema_sync import (
    ensure_phase26_customer_currency_foundation,
)
from app.db.phase27_fx_rate_backfill import ensure_phase27_fx_rate_backfill
from app.db.schema_sync import ensure_admin_schema, ensure_project_lifecycle_schema, ensure_project_stage_and_execution_status, ensure_user_lifecycle_schema, ensure_user_auth_schema, ensure_user_access_schema, ensure_non_productive_codes, ensure_standard_task_types, ensure_timesheet_entry_work_category, ensure_timesheet_entry_leave_count, ensure_timesheet_entry_soft_delete, ensure_team_schema, ensure_user_team_schema
from app.db.design_team import DESIGN_TEAM, build_design_team_users
from app.db.project_template_seed import ensure_project_types_and_templates
from app.db.base import Base
from app.api.deps import get_db
from app.main import app
from app.models.enums import ExecutionStatus, MilestoneStatus
from app.models.models import (
    Contact,
    Customer,
    Milestone,
    Project,
    ProjectType,
    Role,
    Stream,
    TaskType,
    User,
)
from sqlalchemy import select

DEFAULT_PASSWORD = "Password@123"

IDS = {
    "role_admin": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "role_pm": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "role_design_leader": uuid.UUID("d7a67e79-dffa-42f8-bea4-f646f73fd3fd"),
    "role_designer": uuid.UUID("85e2fc34-f0f3-468f-9390-9d8efb1c2a4f"),
    "role_senior_designer": uuid.UUID("e5e5e5e5-e5e5-4e5e-8e5e-e5e5e5e5e5e1"),
    "role_junior_designer": uuid.UUID("f6f6f6f6-f6f6-4f6f-8f6f-f6f6f6f6f6f1"),
    "role_surfacer": uuid.UUID("04582a31-25bf-4709-ac44-e6e05aae8406"),
    "role_read_only": uuid.UUID("88888888-8888-8888-8888-888888888888"),
    "role_planning_board": uuid.UUID("88888888-8888-8888-8888-888888888889"),
    "user_admin": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    "user_pm": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    "user_anurag": uuid.UUID("7cf429ba-ca31-4752-9a03-afa3ba4700a3"),
    "user_binil": uuid.UUID("1bb6229f-dcff-419a-a8fa-2b8a7fd15043"),
    "user_senior_designer": uuid.UUID("10000001-0001-4001-8001-000000000001"),
    "user_junior_designer": uuid.UUID("10000003-0003-4003-8003-000000000003"),
    "user_ranjith": uuid.UUID("731ddf9e-d2d9-450b-a675-cb2ca8a021e3"),
    "user_readonly": uuid.UUID("99999999-9999-9999-9999-999999999999"),
    "user_planning_board": uuid.UUID("99999999-9999-9999-9999-999999999998"),
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
            Role(
                id=IDS["role_read_only"],
                name="Read Only",
                description="View-only access",
            ),
            Role(
                id=IDS["role_planning_board"],
                name="Planning Board",
                description="Wall monitor — read-only planning board",
            ),
        ]
    )
    password_hash = hash_password(DEFAULT_PASSWORD)
    role_by_name = {
        "Admin": IDS["role_admin"],
        "Engineering Manager": IDS["role_pm"],
        "Design Leader": IDS["role_design_leader"],
        "Designer": IDS["role_designer"],
        "Senior Designer": IDS["role_senior_designer"],
        "Junior Designer": IDS["role_junior_designer"],
        "Surfacer": IDS["role_surfacer"],
        "Read Only": IDS["role_read_only"],
        "Planning Board": IDS["role_planning_board"],
    }
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
            *build_design_team_users(password_hash, role_by_name),
            User(
                id=IDS["user_ranjith"],
                role_id=IDS["role_surfacer"],
                email="ranjith@prosohm.com",
                password_hash=password_hash,
                first_name="Ranjith",
                last_name="K",
                is_active=True,
            ),
            User(
                id=IDS["user_readonly"],
                role_id=IDS["role_read_only"],
                email="readonly@prosohm.com",
                password_hash=password_hash,
                first_name="Read",
                last_name="Only",
                is_active=True,
            ),
            User(
                id=IDS["user_planning_board"],
                role_id=IDS["role_planning_board"],
                email="planning-board@prosohm.com",
                password_hash=password_hash,
                first_name="Planning",
                last_name="Board",
                is_active=True,
                must_change_password=False,
            ),
        ]
    )
    session.flush()
    from app.core.timesheet_eligibility import default_requires_timesheet_for_role
    from app.core.salary_eligibility import default_requires_salary_for_role

    for seeded_user in session.scalars(select(User)).all():
        role = session.get(Role, seeded_user.role_id)
        if role is not None:
            seeded_user.requires_timesheet = default_requires_timesheet_for_role(role.name)
            seeded_user.requires_salary = default_requires_salary_for_role(role.name)
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
            name="Prosohm Test Customer",
            code="PTC",
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
            due_date=date.today() + timedelta(days=60),
            execution_status=ExecutionStatus.currently_being_worked_on,
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
    ensure_project_types_and_templates(session)
    mold_type = session.scalar(select(ProjectType).where(ProjectType.name == "Mold Design"))
    if mold_type is not None:
        IDS["project_type_mold"] = mold_type.id
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
    ensure_admin_schema(engine)
    ensure_project_lifecycle_schema(engine)
    ensure_project_stage_and_execution_status(engine)
    ensure_user_lifecycle_schema(engine)
    ensure_user_auth_schema(engine)
    ensure_user_access_schema(engine)
    ensure_team_schema(engine)
    ensure_user_team_schema(engine)
    ensure_timesheet_entry_work_category(engine)
    ensure_non_productive_codes(engine)
    ensure_timesheet_entry_leave_count(engine)
    ensure_timesheet_entry_soft_delete(engine)
    ensure_phase14_kpi_foundation(engine)
    ensure_phase17_ebmp_finance_foundation(engine)
    ensure_phase18_finance_annual_plan_foundation(engine)
    ensure_phase19_timesheet_report_inclusion_foundation(engine)
    ensure_phase22_finance_rebuild_foundation(engine)
    ensure_phase23_finance_team_scope_foundation(engine)
    ensure_phase24_user_requires_salary_foundation(engine)
    ensure_phase25_expense_purchase_date_foundation(engine)
    ensure_phase26_customer_currency_foundation(engine)
    ensure_phase27_fx_rate_backfill(engine)
    ensure_project_complexity(engine)
    ensure_standard_task_types(engine)
    ensure_phase7_foundation(engine)
    ensure_phase8_foundation(engine)
    ensure_phase9_foundation(engine)
    return engine


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture
def seeded_db(test_session_factory, test_engine):
    session = test_session_factory()
    milestone = _seed_database(session)
    session.close()
    ensure_phase14_kpi_foundation(test_engine)
    ensure_phase17_ebmp_finance_foundation(test_engine)
    ensure_phase18_finance_annual_plan_foundation(test_engine)
    ensure_phase19_timesheet_report_inclusion_foundation(test_engine)
    ensure_phase22_finance_rebuild_foundation(test_engine)
    ensure_phase23_finance_team_scope_foundation(test_engine)
    ensure_phase24_user_requires_salary_foundation(test_engine)
    ensure_phase25_expense_purchase_date_foundation(test_engine)
    ensure_phase26_customer_currency_foundation(test_engine)
    ensure_phase27_fx_rate_backfill(test_engine)
    ensure_project_complexity(test_engine)
    ensure_standard_task_types(test_engine)
    return milestone


def get_design_task_type_id(session) -> uuid.UUID:
    task_type = session.scalar(
        select(TaskType).where(
            TaskType.name == "Design",
            TaskType.stream_id == IDS["stream"],
        )
    )
    assert task_type is not None, "Design task type not seeded"
    return task_type.id


@pytest.fixture
def client(test_session_factory, seeded_db):
    import app.db.session as db_session_module

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    original_session_local = db_session_module.SessionLocal
    app.dependency_overrides[get_db] = override_get_db
    db_session_module.SessionLocal = test_session_factory

    db = test_session_factory()
    try:
        design_task_type_id = get_design_task_type_id(db)
    finally:
        db.close()

    with TestClient(app) as test_client:
        test_client.milestone_id = str(seeded_db.id)
        test_client.project_id = str(seeded_db.project_id)
        test_client.user_id = str(IDS["user_anurag"])
        test_client.task_type_id = str(design_task_type_id)
        test_client.auth_headers = login(test_client, "admin@prosohm.com")
        yield test_client

    app.dependency_overrides.clear()
    db_session_module.SessionLocal = original_session_local


@pytest.fixture
def session(test_session_factory, seeded_db):
    db = test_session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def project_type_mold_id(test_session_factory, seeded_db):
    db = test_session_factory()
    try:
        project_type = db.scalar(
            select(ProjectType).where(ProjectType.name == "Mold Design")
        )
        assert project_type is not None
        return str(project_type.id)
    finally:
        db.close()


@pytest.fixture
def auth_headers(client):
    return client.auth_headers


@pytest.fixture
def production_release(monkeypatch):
    """Disable internal release bypass so forced password change behavior can be tested."""
    monkeypatch.setattr("app.core.config.INTERNAL_RELEASE", False)
    monkeypatch.setattr("app.core.release_mode.INTERNAL_RELEASE", False)


def list_items(response):
    """Unwrap paginated list API responses for tests."""
    data = response.json()
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data
