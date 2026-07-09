"""Phase 14 — operational role types, KPI participation flags, task type categories."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import DashboardProfile, TaskTypeFunctionCategory
from app.models.models import OperationalRoleType, Role, TaskType, User

ENGINEERING_ROLE_NAMES = frozenset(
    {
        "Designer",
        "Senior Designer",
        "Junior Designer",
        "Surfacer",
    }
)
MANAGEMENT_ROLE_NAMES = frozenset(
    {
        "Design Leader",
        "Engineering Manager",
        "Project Manager",
    }
)
ADMINISTRATION_ROLE_NAMES = frozenset(
    {
        "Admin",
        "HR",
        "Finance",
        "IT",
    }
)

OPERATIONAL_ROLE_SEED = (
    {
        "code": "engineering",
        "name": "Engineering",
        "description": "Billable engineering delivery roles",
        "dashboard_profile": DashboardProfile.engineering,
        "default_kpi_engineering_productivity": True,
        "default_kpi_capacity_planning": True,
        "default_kpi_utilization": True,
        "default_kpi_workload_planning": True,
        "default_kpi_dashboard_productivity": True,
    },
    {
        "code": "management",
        "name": "Management",
        "description": "Team and project leadership roles",
        "dashboard_profile": DashboardProfile.management,
        "default_kpi_engineering_productivity": False,
        "default_kpi_capacity_planning": False,
        "default_kpi_utilization": False,
        "default_kpi_workload_planning": False,
        "default_kpi_dashboard_productivity": False,
    },
    {
        "code": "administration",
        "name": "Administration",
        "description": "Administrative and system support roles",
        "dashboard_profile": DashboardProfile.administration,
        "default_kpi_engineering_productivity": False,
        "default_kpi_capacity_planning": False,
        "default_kpi_utilization": False,
        "default_kpi_workload_planning": False,
        "default_kpi_dashboard_productivity": False,
    },
    {
        "code": "sales",
        "name": "Sales",
        "description": "Future-ready sales operational role",
        "dashboard_profile": DashboardProfile.management,
        "default_kpi_engineering_productivity": False,
        "default_kpi_capacity_planning": False,
        "default_kpi_utilization": False,
        "default_kpi_workload_planning": False,
        "default_kpi_dashboard_productivity": False,
    },
)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    if not _sqlite_has_column(engine, table, column):
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def _pg_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        )


def _ensure_user_kpi_columns(engine: Engine) -> None:
    columns = [
        ("operational_role_type_id", "VARCHAR(36)"),
        ("kpi_engineering_productivity", "BOOLEAN NOT NULL DEFAULT 1"),
        ("kpi_capacity_planning", "BOOLEAN NOT NULL DEFAULT 1"),
        ("kpi_utilization", "BOOLEAN NOT NULL DEFAULT 1"),
        ("kpi_workload_planning", "BOOLEAN NOT NULL DEFAULT 1"),
        ("kpi_dashboard_productivity", "BOOLEAN NOT NULL DEFAULT 1"),
    ]
    dialect = engine.dialect.name
    if dialect == "sqlite":
        for column, definition in columns:
            _sqlite_add_column(engine, "users", column, definition)
    elif dialect == "postgresql":
        for column, definition in columns:
            _pg_add_column(engine, "users", column, definition)


def _ensure_task_type_category(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _sqlite_add_column(
            engine,
            "task_types",
            "function_category",
            "VARCHAR(50) NOT NULL DEFAULT 'engineering'",
        )
    elif dialect == "postgresql":
        _pg_add_column(
            engine,
            "task_types",
            "function_category",
            "VARCHAR(50) NOT NULL DEFAULT 'engineering'",
        )


def _seed_operational_role_types(session: Session) -> dict[str, uuid.UUID]:
    by_code: dict[str, uuid.UUID] = {}
    for item in OPERATIONAL_ROLE_SEED:
        existing = session.scalar(
            select(OperationalRoleType).where(OperationalRoleType.code == item["code"])
        )
        if existing is None:
            record = OperationalRoleType(**item)
            session.add(record)
            session.flush()
            by_code[item["code"]] = record.id
        else:
            for key, value in item.items():
                if key != "code":
                    setattr(existing, key, value)
            by_code[item["code"]] = existing.id
    return by_code


def _infer_operational_code(role_name: str) -> str:
    if role_name in ENGINEERING_ROLE_NAMES:
        return "engineering"
    if role_name in MANAGEMENT_ROLE_NAMES:
        if role_name == "Design Leader":
            return "engineering"
        return "management"
    if role_name in ADMINISTRATION_ROLE_NAMES:
        return "administration"
    return "engineering"


def _backfill_users(session: Session, role_types: dict[str, uuid.UUID]) -> None:
    users = session.scalars(select(User).join(Role, User.role_id == Role.id)).all()
    for user in users:
        role_name = user.role.name if user.role else ""
        code = _infer_operational_code(role_name)
        op_id = role_types.get(code)
        if user.operational_role_type_id is None and op_id is not None:
            user.operational_role_type_id = op_id
        op_type = (
            session.get(OperationalRoleType, user.operational_role_type_id)
            if user.operational_role_type_id
            else None
        )
        if op_type is None:
            continue
        apply_operational_role_defaults(user, op_type)
        if role_name == "Design Leader":
            user.kpi_engineering_productivity = True
            user.kpi_capacity_planning = True
            user.kpi_utilization = True
            user.kpi_workload_planning = True
            user.kpi_dashboard_productivity = True


def apply_operational_role_defaults(user: User, operational_role: OperationalRoleType) -> None:
    user.operational_role_type_id = operational_role.id
    user.kpi_engineering_productivity = operational_role.default_kpi_engineering_productivity
    user.kpi_capacity_planning = operational_role.default_kpi_capacity_planning
    user.kpi_utilization = operational_role.default_kpi_utilization
    user.kpi_workload_planning = operational_role.default_kpi_workload_planning
    user.kpi_dashboard_productivity = operational_role.default_kpi_dashboard_productivity


def _backfill_task_types(session: Session) -> None:
    management_names = {
        "customer meeting",
        "planning",
        "project review",
        "hiring",
        "interview",
        "quoting",
        "management meeting",
        "performance review",
    }
    admin_names = {"it", "hr", "finance", "documentation", "training", "office work"}
    for task_type in session.scalars(select(TaskType)).all():
        name = (task_type.name or "").strip().lower()
        if name in management_names:
            task_type.function_category = TaskTypeFunctionCategory.management
        elif name in admin_names:
            task_type.function_category = TaskTypeFunctionCategory.administration
        elif not task_type.function_category:
            task_type.function_category = TaskTypeFunctionCategory.engineering


def ensure_phase14_kpi_foundation(engine: Engine) -> None:
    Base = OperationalRoleType.metadata
    Base.create_all(bind=engine, tables=[OperationalRoleType.__table__])
    _ensure_user_kpi_columns(engine)
    _ensure_task_type_category(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        role_types = _seed_operational_role_types(session)
        _backfill_users(session, role_types)
        _backfill_task_types(session)
        session.commit()
