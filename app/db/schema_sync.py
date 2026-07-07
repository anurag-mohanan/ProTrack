"""Apply lightweight schema updates for databases created before MVP columns."""

from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.permissions import JUNIOR_DESIGNER, SENIOR_DESIGNER
from app.core.security import hash_password
from app.db.design_team import ensure_design_team_users
from app.models.enums import NonProductiveCodeCategory
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


PERFORMANCE_INDEXES = (
    ("idx_timesheet_entries_project_id", "timesheet_entries", "project_id"),
    ("idx_timesheet_entries_timesheet_id", "timesheet_entries", "timesheet_id"),
    ("idx_timesheet_entries_entry_date", "timesheet_entries", "entry_date"),
    ("idx_projects_designer_id", "projects", "designer_id"),
    ("idx_projects_customer_id", "projects", "customer_id"),
    ("idx_projects_team_id", "projects", "team_id"),
    ("idx_projects_execution_status", "projects", "execution_status"),
    ("idx_milestones_project_id", "milestones", "project_id"),
    ("idx_activities_project_id", "activities", "project_id"),
    ("idx_timesheets_user_id", "timesheets", "user_id"),
    ("idx_timesheets_week_start", "timesheets", "week_start"),
)


def ensure_performance_indexes(engine: Engine) -> None:
    with engine.begin() as connection:
        for index_name, table_name, column_name in PERFORMANCE_INDEXES:
            if not _sqlite_has_column(engine, table_name, column_name):
                continue
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table_name} ({column_name})"
                )
            )


def ensure_production_roles(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        read_only = session.scalar(select(Role).where(Role.name == "Read Only"))
        if read_only is None:
            session.add(
                Role(
                    name="Read Only",
                    description="View-only access to projects, reports, and planning",
                )
            )

        engineering_manager = session.scalar(
            select(Role).where(Role.name == "Engineering Manager")
        )
        project_manager = session.scalar(select(Role).where(Role.name == "Project Manager"))
        if engineering_manager is None and project_manager is not None:
            project_manager.name = "Engineering Manager"
            if not project_manager.description:
                project_manager.description = "Manage projects and engineering operations"

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
        _ensure_column_sqlite("users", "last_login", "last_login DATETIME")
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
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")
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
def ensure_project_stage_and_execution_status(engine: Engine) -> None:
    """Add project_stage and migrate legacy status values to execution status."""
    dialect = engine.dialect.name
    legacy_status_map = (
        ("not_started", "currently_being_worked_on"),
        ("in_progress", "currently_being_worked_on"),
        ("waiting_for_customer", "on_hold"),
        ("completed", "completed"),
    )

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "project_stage"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN project_stage "
                        "VARCHAR(32) NOT NULL DEFAULT 'preliminary'"
                    )
                )
        with engine.begin() as connection:
            for old_value, new_value in legacy_status_map:
                connection.execute(
                    text(
                        "UPDATE projects SET status = :new_value WHERE status = :old_value"
                    ),
                    {"old_value": old_value, "new_value": new_value},
                )
            connection.execute(
                text(
                    "UPDATE projects SET project_stage = 'preliminary' "
                    "WHERE project_stage IS NULL OR project_stage = ''"
                )
            )
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_stage "
                    "VARCHAR(32) NOT NULL DEFAULT 'preliminary'"
                )
            )
            for old_value, new_value in legacy_status_map:
                connection.execute(
                    text(
                        "UPDATE projects SET status = :new_value WHERE status = :old_value"
                    ),
                    {"old_value": old_value, "new_value": new_value},
                )
            connection.execute(
                text(
                    "UPDATE projects SET project_stage = 'preliminary' "
                    "WHERE project_stage IS NULL OR project_stage = ''"
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


def ensure_user_auth_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    auth_columns = (
        ("is_locked", "is_locked BOOLEAN NOT NULL DEFAULT 0"),
        ("failed_login_count", "failed_login_count INTEGER NOT NULL DEFAULT 0"),
    )

    if dialect == "sqlite":
        for column_name, ddl in auth_columns:
            if not _sqlite_has_column(engine, "users", column_name):
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {ddl}"))
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_locked "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )


def ensure_user_access_schema(engine: Engine) -> None:
    dialect = engine.dialect.name
    access_columns = (
        ("module_access", "module_access TEXT"),
        ("special_permissions", "special_permissions TEXT"),
    )

    if dialect == "sqlite":
        for column_name, ddl in access_columns:
            if not _sqlite_has_column(engine, "users", column_name):
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {ddl}"))
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS module_access TEXT"))
            connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS special_permissions TEXT")
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


NP_CODE_SEED: tuple[tuple[str, str, int, NonProductiveCodeCategory], ...] = (
    ("C500", "Leave", 1, NonProductiveCodeCategory.leave),
    ("C501", "IT Issues", 2, NonProductiveCodeCategory.non_productive),
    ("C502", "Meetings", 3, NonProductiveCodeCategory.non_productive),
    ("C503", "Upload / Download", 4, NonProductiveCodeCategory.non_productive),
    ("C504", "Training", 5, NonProductiveCodeCategory.non_productive),
    ("C505", "Infra Issues", 6, NonProductiveCodeCategory.non_productive),
    ("C506", "Internal Work", 7, NonProductiveCodeCategory.non_productive),
    ("EST001", "Estimation", 8, NonProductiveCodeCategory.non_productive),
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
        if engine.dialect.name == "sqlite":
            with engine.begin() as connection:
                columns = {
                    row[1]
                    for row in connection.execute(text("PRAGMA table_info(non_productive_codes)")).fetchall()
                }
                if "is_archived" not in columns:
                    connection.execute(
                        text(
                            "ALTER TABLE non_productive_codes "
                            "ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"
                        )
                    )
                if "category" not in columns:
                    connection.execute(
                        text(
                            "ALTER TABLE non_productive_codes "
                            "ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'non_productive'"
                        )
                    )
        elif engine.dialect.name == "postgresql":
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "DO $$ BEGIN "
                        "CREATE TYPE non_productive_code_category AS ENUM "
                        "('non_productive', 'leave'); "
                        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
                    )
                )
                connection.execute(
                    text(
                        "ALTER TABLE non_productive_codes "
                        "ADD COLUMN IF NOT EXISTS category "
                        "non_productive_code_category NOT NULL DEFAULT 'non_productive'"
                    )
                )
        existing_by_code = {
            row.code: row
            for row in session.scalars(select(NonProductiveCode)).all()
        }
        changed = False
        for code, description, sort_order, category in NP_CODE_SEED:
            row = existing_by_code.get(code)
            if row is None:
                session.add(
                    NonProductiveCode(
                        code=code,
                        description=description,
                        category=category,
                        sort_order=sort_order,
                        is_active=True,
                        is_archived=False,
                    )
                )
                changed = True
            elif (
                row.description != description
                or row.sort_order != sort_order
                or row.category != category
            ):
                row.description = description
                row.sort_order = sort_order
                row.category = category
                changed = True
        if changed:
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


def ensure_timesheet_entry_leave_count(engine: Engine) -> None:
    """Add leave_count and backfill leave entries from configured leave NP codes."""
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "timesheet_entries", "leave_count"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE timesheet_entries ADD COLUMN leave_count INTEGER")
                )
    elif dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS leave_count INTEGER"
                )
            )

    session = sessionmaker(bind=engine)()
    try:
        leave_code_ids = session.scalars(
            select(NonProductiveCode.id).where(
                NonProductiveCode.category == NonProductiveCodeCategory.leave
            )
        ).all()
        if not leave_code_ids:
            return
        entries = session.scalars(
            select(TimesheetEntry).where(
                TimesheetEntry.non_productive_code_id.in_(leave_code_ids),
                TimesheetEntry.leave_count.is_(None),
            )
        ).all()
        if not entries:
            return
        for entry in entries:
            entry.leave_count = 1
            entry.is_billable = False
        session.commit()
    finally:
        session.close()


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


def ensure_timesheet_entry_timestamps(engine: Engine) -> None:
    """Backfill NULL created_at/updated_at on imported timesheet entries."""
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE timesheet_entries
                SET created_at = COALESCE(created_at, datetime(entry_date)),
                    updated_at = COALESCE(updated_at, COALESCE(created_at, datetime(entry_date)))
                WHERE created_at IS NULL OR updated_at IS NULL
                """
            )
        )


def ensure_timesheet_entry_soft_delete(engine: Engine) -> None:
    """Add soft-delete columns to timesheet entries."""
    dialect = engine.dialect.name
    columns_sqlite = [
        ("is_deleted", "is_deleted BOOLEAN NOT NULL DEFAULT 0"),
        ("deleted_at", "deleted_at DATETIME"),
        ("deleted_by_id", "deleted_by_id BLOB"),
        ("delete_reason", "delete_reason VARCHAR(100)"),
    ]
    if dialect == "sqlite":
        for column_name, ddl in columns_sqlite:
            if not _sqlite_has_column(engine, "timesheet_entries", column_name):
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE timesheet_entries ADD COLUMN {ddl}")
                    )
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS deleted_by_id UUID REFERENCES users(id)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS delete_reason VARCHAR(100)"
                )
            )


def ensure_team_schema(engine: Engine) -> None:
    """Add team tables and project/template team foreign keys."""
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "team_id"):
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE projects ADD COLUMN team_id BLOB"))
        if not _sqlite_has_column(engine, "project_templates", "default_team_id"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE project_templates ADD COLUMN default_team_id BLOB")
                )
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES teams(id)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE project_templates "
                    "ADD COLUMN IF NOT EXISTS default_team_id UUID REFERENCES teams(id)"
                )
            )


def ensure_user_team_schema(engine: Engine) -> None:
    """Add primary team assignment column on users."""
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "users", "team_id"):
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN team_id BLOB"))
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES teams(id)"
                )
            )


def _sqlite_column_is_not_null(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    column = next((row for row in rows if row[1] == column_name), None)
    return column is not None and column[3] == 1


def _sqlite_rebuild_projects_for_placeholder_support(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(
            text(
                """
                CREATE TABLE projects_placeholder_new (
                    id BLOB PRIMARY KEY,
                    tool_number VARCHAR(50) NOT NULL UNIQUE,
                    part_description VARCHAR(255) NOT NULL,
                    customer_id BLOB NOT NULL REFERENCES customers(id),
                    customer_contact_id BLOB REFERENCES contacts(id),
                    design_leader_id BLOB REFERENCES users(id),
                    designer_id BLOB REFERENCES users(id),
                    surfacer_id BLOB REFERENCES users(id),
                    stream_id BLOB REFERENCES streams(id),
                    team_id BLOB REFERENCES teams(id),
                    project_type_id BLOB REFERENCES project_types(id),
                    project_template_id BLOB REFERENCES project_templates(id),
                    code VARCHAR(50) UNIQUE,
                    quoted_hours NUMERIC(8, 2) NOT NULL DEFAULT 0,
                    actual_hours NUMERIC(8, 2) NOT NULL DEFAULT 0,
                    due_date DATE,
                    status VARCHAR(32) NOT NULL DEFAULT 'planning',
                    project_stage VARCHAR(32) NOT NULL DEFAULT 'preliminary',
                    health VARCHAR(10) NOT NULL DEFAULT 'green',
                    priority VARCHAR(32) NOT NULL DEFAULT 'medium',
                    notes TEXT,
                    completed_at DATETIME,
                    is_archived BOOLEAN NOT NULL DEFAULT 0,
                    archived_at DATETIME,
                    archived_by_id BLOB REFERENCES users(id),
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    deleted_at DATETIME,
                    deleted_by_id BLOB REFERENCES users(id),
                    project_folder_path VARCHAR(500),
                    cad_folder_path VARCHAR(500),
                    released_folder_path VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO projects_placeholder_new (
                    id, tool_number, part_description, customer_id, customer_contact_id,
                    design_leader_id, designer_id, surfacer_id, stream_id, team_id,
                    project_type_id, project_template_id, code, quoted_hours, actual_hours,
                    due_date, status, project_stage, health, priority, notes,
                    completed_at, is_archived, archived_at, archived_by_id, is_deleted,
                    deleted_at, deleted_by_id, project_folder_path, cad_folder_path,
                    released_folder_path, created_at, updated_at
                )
                SELECT
                    id, tool_number, part_description, customer_id, customer_contact_id,
                    design_leader_id, designer_id, surfacer_id, stream_id, team_id,
                    project_type_id, project_template_id, code, quoted_hours, actual_hours,
                    due_date, status, project_stage, health, priority, notes,
                    completed_at, is_archived, archived_at, archived_by_id, is_deleted,
                    deleted_at, deleted_by_id, project_folder_path, cad_folder_path,
                    released_folder_path,
                    COALESCE(created_at, CURRENT_TIMESTAMP),
                    COALESCE(updated_at, CURRENT_TIMESTAMP)
                FROM projects
                """
            )
        )
        connection.execute(text("DROP TABLE projects"))
        connection.execute(
            text("ALTER TABLE projects_placeholder_new RENAME TO projects")
        )
        connection.execute(text("PRAGMA foreign_keys=ON"))


def _sqlite_column_default_value(
    engine: Engine, table_name: str, column_name: str
) -> str | None:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    column = next((row for row in rows if row[1] == column_name), None)
    if column is None:
        return None
    return column[4]


def _sqlite_projects_timestamps_need_fix(engine: Engine) -> bool:
    if not _sqlite_has_column(engine, "projects", "created_at"):
        return False
    if not _sqlite_column_is_not_null(engine, "projects", "created_at"):
        return True
    if not _sqlite_column_is_not_null(engine, "projects", "updated_at"):
        return True
    return _sqlite_column_default_value(engine, "projects", "created_at") is None


def _backfill_project_timestamps(connection, *, dialect: str) -> None:
    if dialect == "sqlite":
        connection.execute(
            text(
                """
                UPDATE projects
                SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                    updated_at = COALESCE(
                        updated_at,
                        COALESCE(created_at, CURRENT_TIMESTAMP)
                    )
                WHERE created_at IS NULL OR updated_at IS NULL
                """
            )
        )
        return

    if dialect == "postgresql":
        connection.execute(
            text(
                """
                UPDATE projects
                SET created_at = COALESCE(created_at, NOW()),
                    updated_at = COALESCE(
                        updated_at,
                        COALESCE(created_at, NOW())
                    )
                WHERE created_at IS NULL OR updated_at IS NULL
                """
            )
        )


def ensure_project_timestamps(engine: Engine) -> None:
    """Backfill and enforce NOT NULL timestamp columns on projects.

    The placeholder-project SQLite rebuild originally recreated ``created_at`` and
    ``updated_at`` without defaults, so ORM inserts stored NULL despite
    TimestampMixin server defaults on the model.
    """
    dialect = engine.dialect.name

    with engine.begin() as connection:
        _backfill_project_timestamps(connection, dialect=dialect)

    if dialect == "sqlite" and _sqlite_projects_timestamps_need_fix(engine):
        _sqlite_rebuild_projects_for_placeholder_support(engine)
        with engine.begin() as connection:
            _backfill_project_timestamps(connection, dialect=dialect)
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN created_at SET DEFAULT NOW()"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN updated_at SET DEFAULT NOW()"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN created_at SET NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN updated_at SET NOT NULL"
                )
            )


def ensure_placeholder_project_schema(engine: Engine) -> None:
    """Allow nullable planning fields on projects for placeholder creation."""
    dialect = engine.dialect.name

    if dialect == "sqlite":
        needs_rebuild = (
            _sqlite_column_is_not_null(engine, "projects", "design_leader_id")
            or _sqlite_column_is_not_null(engine, "projects", "code")
        )
        if needs_rebuild:
            _sqlite_rebuild_projects_for_placeholder_support(engine)
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN customer_contact_id DROP NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN design_leader_id DROP NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN stream_id DROP NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN due_date DROP NOT NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN quoted_hours SET DEFAULT 0"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ALTER COLUMN code DROP NOT NULL"
                )
            )
