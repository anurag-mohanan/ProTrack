"""Phase 7 schema migrations and master-data seeds."""

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.foundation import (
    CompanySettings,
    ContactType,
    Department,
    EngineeringDiscipline,
    FilePathSettings,
    NotificationSettings,
    Skill,
)
from app.models.models import Customer, Stream, TaskType


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


def ensure_phase7_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    user_columns = [
        ("department_id", "BLOB" if dialect == "sqlite" else "UUID"),
        ("working_hours_per_day", "NUMERIC(4, 2) NOT NULL DEFAULT 8"),
        ("working_days", "VARCHAR(50) NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri'"),
        ("employment_type", "VARCHAR(32)"),
        ("skill_level", "VARCHAR(32)"),
        ("joining_date", "DATE"),
        ("leaving_date", "DATE"),
        ("availability_status", "VARCHAR(32) NOT NULL DEFAULT 'available'"),
        ("max_allocation_percent", "INTEGER NOT NULL DEFAULT 100"),
    ]
    customer_columns = [
        ("default_project_template_id", "BLOB" if dialect == "sqlite" else "UUID"),
        ("default_team_id", "BLOB" if dialect == "sqlite" else "UUID"),
        ("default_project_type_id", "BLOB" if dialect == "sqlite" else "UUID"),
        ("default_folder_structure", "VARCHAR(500)"),
        ("due_date_calculation", "VARCHAR(40) NOT NULL DEFAULT 'from_start'"),
        ("project_number_format", "VARCHAR(100)"),
        ("project_number_prefix", "VARCHAR(50)"),
        ("next_project_sequence", "INTEGER NOT NULL DEFAULT 1"),
    ]

    if dialect == "sqlite":
        for column, definition in user_columns:
            _sqlite_add_column(engine, "users", column, definition)
        for column, definition in customer_columns:
            _sqlite_add_column(engine, "customers", column, definition)
        _sqlite_add_column(engine, "contacts", "contact_type_id", "BLOB")
        _sqlite_add_column(engine, "projects", "priority", "VARCHAR(20) NOT NULL DEFAULT 'medium'")
        _sqlite_add_column(engine, "project_template_milestones", "project_stage", "VARCHAR(20)")
        _sqlite_add_column(engine, "project_template_milestones", "estimated_hours", "NUMERIC(8, 2)")
        return

    if dialect == "postgresql":
        for column, definition in user_columns:
            _pg_add_column(engine, "users", column, definition)
        for column, definition in customer_columns:
            _pg_add_column(engine, "customers", column, definition)
        _pg_add_column(engine, "contacts", "contact_type_id", "UUID")
        _pg_add_column(engine, "projects", "priority", "VARCHAR(20) NOT NULL DEFAULT 'medium'")
        _pg_add_column(engine, "project_template_milestones", "project_stage", "VARCHAR(20)")
        _pg_add_column(engine, "project_template_milestones", "estimated_hours", "NUMERIC(8, 2)")


DEPARTMENT_SEED = (
    ("Mold Design", "MD"),
    ("Surfacing", "SURF"),
    ("DFM", "DFM"),
    ("Engineering Changes", "EC"),
    ("Administration", "ADMIN"),
    ("Business Development", "BD"),
)

CONTACT_TYPE_SEED = (
    "Engineering",
    "Purchasing",
    "Program Manager",
    "Quality",
    "Tool Shop",
    "Accounts",
)

DISCIPLINE_SEED = (
    "Plastic Injection Mold",
    "Die Casting",
    "Fixture Design",
    "Electrode Design",
    "Automation",
    "Tooling Support",
)

SKILL_SEED = (
    ("NX", "CAD"),
    ("Creo", "CAD"),
    ("CATIA", "CAD"),
    ("SolidWorks", "CAD"),
    ("AutoCAD", "CAD"),
    ("Moldflow", "Analysis"),
)

EXTRA_TASK_TYPES = (
    "Meetings",
    "Training",
    "Review",
    "Project Management",
    "Administration",
)


def ensure_phase7_seed_data(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        if session.scalar(select(CompanySettings.id).limit(1)) is None:
            session.add(
                CompanySettings(
                    company_name="Prosohm Engineering",
                    currency="INR",
                    timezone="Asia/Kolkata",
                    financial_year_start_month=4,
                    default_working_hours_per_day=Decimal("8"),
                )
            )

        if session.scalar(select(FilePathSettings.id).limit(1)) is None:
            session.add(FilePathSettings())

        if session.scalar(select(NotificationSettings.id).limit(1)) is None:
            session.add(NotificationSettings())

        existing_departments = set(session.scalars(select(Department.name)).all())
        for name, code in DEPARTMENT_SEED:
            if name not in existing_departments:
                session.add(Department(name=name, code=code))

        existing_contact_types = set(session.scalars(select(ContactType.name)).all())
        for name in CONTACT_TYPE_SEED:
            if name not in existing_contact_types:
                session.add(ContactType(name=name))

        existing_disciplines = set(session.scalars(select(EngineeringDiscipline.name)).all())
        for name in DISCIPLINE_SEED:
            if name not in existing_disciplines:
                session.add(EngineeringDiscipline(name=name))

        existing_skills = set(session.scalars(select(Skill.name)).all())
        for name, category in SKILL_SEED:
            if name not in existing_skills:
                session.add(Skill(name=name, category=category))

        mold_stream = session.scalar(select(Stream).where(Stream.name == "Mold Design"))
        if mold_stream is not None:
            existing_task_types = {
                row.name
                for row in session.scalars(
                    select(TaskType).where(TaskType.stream_id == mold_stream.id)
                ).all()
            }
            for name in EXTRA_TASK_TYPES:
                if name not in existing_task_types:
                    session.add(
                        TaskType(
                            stream_id=mold_stream.id,
                            name=name,
                            description=name,
                            is_billable=name not in {"Meetings", "Training", "Administration"},
                        )
                    )

        session.commit()
    finally:
        session.close()


def ensure_phase7_foundation(engine: Engine) -> None:
    ensure_phase7_columns(engine)
    ensure_phase7_seed_data(engine)
