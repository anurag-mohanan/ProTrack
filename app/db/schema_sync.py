"""Apply lightweight schema updates for databases created before MVP columns."""

from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.permissions import JUNIOR_DESIGNER, SENIOR_DESIGNER
from app.core.security import hash_password
from app.db.design_team import ensure_design_team_users
from app.models.models import NonProductiveCode, Project, Role, Stream, TaskType, TimesheetEntry
from app.services.project_calculation_service import recalculate_project


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _backfill_project_actual_hours(session: Session) -> None:
    project_ids = session.scalars(select(Project.id)).all()
    for project_id in project_ids:
        total = session.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                TimesheetEntry.project_id == project_id
            )
        )
        project = session.get(Project, project_id)
        if project is not None:
            project.actual_hours = Decimal(str(total or 0))
            session.add(project)
    session.commit()


def ensure_project_actual_hours(engine: Engine) -> None:
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "actual_hours"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE projects "
                        "ADD COLUMN actual_hours NUMERIC(8, 2) NOT NULL DEFAULT 0"
                    )
                )
            session = sessionmaker(bind=engine)()
            try:
                _backfill_project_actual_hours(session)
            finally:
                session.close()
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS actual_hours NUMERIC(8, 2) NOT NULL DEFAULT 0"
                )
            )
        session = sessionmaker(bind=engine)()
        try:
            _backfill_project_actual_hours(session)
        finally:
            session.close()


def _backfill_project_health(session: Session) -> None:
    project_ids = session.scalars(select(Project.id)).all()
    for project_id in project_ids:
        recalculate_project(session, project_id)


def ensure_project_health(engine: Engine) -> None:
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "health"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE projects "
                        "ADD COLUMN health VARCHAR(10) NOT NULL DEFAULT 'green'"
                    )
                )
            session = sessionmaker(bind=engine)()
            try:
                _backfill_project_health(session)
            finally:
                session.close()
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DO $$ BEGIN "
                    "CREATE TYPE project_health AS ENUM ('green', 'yellow', 'red'); "
                    "EXCEPTION WHEN duplicate_object THEN NULL; "
                    "END $$;"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS health project_health NOT NULL DEFAULT 'green'"
                )
            )
        session = sessionmaker(bind=engine)()
        try:
            _backfill_project_health(session)
        finally:
            session.close()


def ensure_timesheet_approval_comments(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "timesheets", "approval_comments"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE timesheets ADD COLUMN approval_comments TEXT")
                )
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheets "
                    "ADD COLUMN IF NOT EXISTS approval_comments TEXT"
                )
            )


DESIGN_ROLE_SEED = (
    (SENIOR_DESIGNER, "Senior design work with project edit on assignments"),
    (JUNIOR_DESIGNER, "Entry-level design work and time logging"),
)


def ensure_design_roles(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        for name, description in DESIGN_ROLE_SEED:
            existing = session.scalar(select(Role).where(Role.name == name))
            if existing is None:
                session.add(Role(name=name, description=description))
        session.commit()
    finally:
        session.close()


def ensure_design_team(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        ensure_design_team_users(session, hash_password("Password@123"))
    finally:
        session.close()


def ensure_admin_schema(engine: Engine) -> None:
    dialect = engine.dialect.name

    def _ensure_column_sqlite(table: str, column: str, ddl: str) -> None:
        if not _sqlite_has_column(engine, table, column):
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

    if dialect == "sqlite":
        _ensure_column_sqlite(
            "users",
            "must_change_password",
            "must_change_password BOOLEAN NOT NULL DEFAULT 0",
        )
        _ensure_column_sqlite("customers", "notes", "notes TEXT")
        _ensure_column_sqlite(
            "contacts",
            "is_active",
            "is_active BOOLEAN NOT NULL DEFAULT 1",
        )
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS notes TEXT")
            )
            connection.execute(
                text(
                    "ALTER TABLE contacts "
                    "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )


def ensure_project_template_schema(engine: Engine) -> None:
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "project_type_id"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN project_type_id BLOB")
                )
        if not _sqlite_has_column(engine, "projects", "project_template_id"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN project_template_id BLOB")
                )
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS project_type_id UUID "
                    "REFERENCES project_types(id)"
                )
            )
def ensure_project_lifecycle_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    project_columns = (
        ("completed_at", "completed_at DATETIME"),
        ("is_archived", "is_archived BOOLEAN NOT NULL DEFAULT 0"),
        ("archived_at", "archived_at DATETIME"),
        ("archived_by_id", "archived_by_id BLOB"),
        ("is_deleted", "is_deleted BOOLEAN NOT NULL DEFAULT 0"),
        ("deleted_at", "deleted_at DATETIME"),
        ("deleted_by_id", "deleted_by_id BLOB"),
    )

    if dialect == "sqlite":
        for column_name, ddl in project_columns:
            if not _sqlite_has_column(engine, "projects", column_name):
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE projects ADD COLUMN {ddl}"))
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP")
            )
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_archived "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP")
            )
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_by_id UUID "
                    "REFERENCES users(id)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_deleted "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
            )
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS deleted_by_id UUID "
                    "REFERENCES users(id)"
                )
            )


def ensure_user_lifecycle_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    user_columns = (
        ("is_archived", "is_archived BOOLEAN NOT NULL DEFAULT 0"),
        ("archived_at", "archived_at DATETIME"),
        ("is_deleted", "is_deleted BOOLEAN NOT NULL DEFAULT 0"),
        ("deleted_at", "deleted_at DATETIME"),
        ("deleted_by_id", "deleted_by_id BLOB"),
    )

    if dialect == "sqlite":
        for column_name, ddl in user_columns:
            if not _sqlite_has_column(engine, "users", column_name):
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {ddl}"))
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_archived "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP")
            )
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deleted "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
            )
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_by_id UUID "
                    "REFERENCES users(id)"
                )
            )


NP_CODE_SEED: tuple[tuple[str, str, int], ...] = (
    ("C500", "Lack of Work", 1),
    ("C501", "IT / Software Issues", 2),
    ("C502", "Meetings", 3),
    ("C503", "File Upload / Download", 4),
    ("C504", "Training", 5),
    ("C505", "Administration", 6),
    ("EST001", "Estimation", 7),
)

STANDARD_TASK_TYPE_NAMES: tuple[tuple[str, str], ...] = (
    ("Design", "Productive design work"),
    ("Surfacing", "Surface modeling work"),
    ("Feasibility", "Feasibility assessment"),
    ("Engineering Change (EC)", "Engineering change orders"),
    ("2D Drawings", "2D drawing production"),
)


def ensure_non_productive_codes(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        existing = session.scalar(select(func.count()).select_from(NonProductiveCode)) or 0
        if int(existing) == 0:
            for code, description, sort_order in NP_CODE_SEED:
                session.add(
                    NonProductiveCode(
                        code=code,
                        description=description,
                        sort_order=sort_order,
                        is_active=True,
                    )
                )
            session.commit()
    finally:
        session.close()


def ensure_standard_task_types(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        stream = session.scalar(select(Stream).where(Stream.name == "Mold Design"))
        if stream is None:
            return
        existing_names = {
            row.name
            for row in session.scalars(
                select(TaskType).where(TaskType.stream_id == stream.id)
            ).all()
        }
        for name, description in STANDARD_TASK_TYPE_NAMES:
            if name in existing_names:
                continue
            session.add(
                TaskType(
                    stream_id=stream.id,
                    name=name,
                    description=description,
                    is_billable=True,
                    is_active=True,
                )
            )
        session.commit()
    finally:
        session.close()


def _sqlite_rebuild_timesheet_entries(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE timesheet_entries_new (
                    id BLOB PRIMARY KEY,
                    timesheet_id BLOB NOT NULL REFERENCES timesheets(id) ON DELETE CASCADE,
                    project_id BLOB REFERENCES projects(id),
                    customer_id BLOB REFERENCES customers(id),
                    task_type_id BLOB REFERENCES task_types(id),
                    milestone_id BLOB REFERENCES milestones(id),
                    non_productive_code_id BLOB REFERENCES non_productive_codes(id),
                    work_category VARCHAR(32) NOT NULL DEFAULT 'productive',
                    is_billable BOOLEAN NOT NULL DEFAULT 1,
                    entry_date DATE NOT NULL,
                    hours NUMERIC(5, 2) NOT NULL,
                    description TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    CHECK (hours > 0 AND hours <= 24)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO timesheet_entries_new (
                    id, timesheet_id, project_id, customer_id, task_type_id,
                    milestone_id, non_productive_code_id, work_category, is_billable,
                    entry_date, hours, description, created_at, updated_at
                )
                SELECT
                    id, timesheet_id, project_id, customer_id, task_type_id,
                    milestone_id, non_productive_code_id,
                    COALESCE(work_category, 'productive'), COALESCE(is_billable, 1),
                    entry_date, hours, description, created_at, updated_at
                FROM timesheet_entries
                """
            )
        )
        connection.execute(text("DROP TABLE timesheet_entries"))
        connection.execute(
            text("ALTER TABLE timesheet_entries_new RENAME TO timesheet_entries")
        )


def ensure_timesheet_entry_work_category(engine: Engine) -> None:
    dialect = engine.dialect.name
    entry_columns_sqlite = (
        ("customer_id", "customer_id BLOB"),
        ("non_productive_code_id", "non_productive_code_id BLOB"),
        ("work_category", "work_category VARCHAR(32) NOT NULL DEFAULT 'productive'"),
        ("is_billable", "is_billable BOOLEAN NOT NULL DEFAULT 1"),
    )

    if dialect == "sqlite":
        for column_name, ddl in entry_columns_sqlite:
            if not _sqlite_has_column(engine, "timesheet_entries", column_name):
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE timesheet_entries ADD COLUMN {ddl}")
                    )
        with engine.connect() as connection:
            rows = connection.execute(text("PRAGMA table_info(timesheet_entries)")).fetchall()
        project_col = next((row for row in rows if row[1] == "project_id"), None)
        if project_col is not None and project_col[3] == 1:
            _sqlite_rebuild_timesheet_entries(engine)
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ALTER COLUMN project_id DROP NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS "
                    "customer_id UUID REFERENCES customers(id)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS "
                    "non_productive_code_id UUID REFERENCES non_productive_codes(id)"
                )
            )
            connection.execute(
                text(
                    "DO $$ BEGIN "
                    "CREATE TYPE work_category AS ENUM ('productive', 'non_productive'); "
                    "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS "
                    "work_category work_category NOT NULL DEFAULT 'productive'"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries ADD COLUMN IF NOT EXISTS "
                    "is_billable BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE timesheet_entries te
                    SET customer_id = p.customer_id
                    FROM projects p
                    WHERE te.project_id = p.id AND te.customer_id IS NULL
                    """
                )
            )
