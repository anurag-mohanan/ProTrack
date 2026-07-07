"""Phase 10 — project milestone workspace fields and planned hours."""

from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import Milestone, Project, ProjectTemplateMilestone


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


def ensure_phase10_milestone_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    milestone_columns = [
        ("planned_hours", "NUMERIC(8, 2) NOT NULL DEFAULT 0"),
        ("progress_percent", "INTEGER NOT NULL DEFAULT 0"),
        ("assigned_user_id", "BLOB" if dialect == "sqlite" else "UUID"),
        ("completed_date", "DATE"),
    ]
    project_columns = [
        ("current_planned_hours", "NUMERIC(8, 2) NOT NULL DEFAULT 0"),
    ]

    if dialect == "sqlite":
        for column, definition in milestone_columns:
            _sqlite_add_column(engine, "milestones", column, definition)
        for column, definition in project_columns:
            _sqlite_add_column(engine, "projects", column, definition)
    elif dialect == "postgresql":
        for column, definition in milestone_columns:
            _pg_add_column(engine, "milestones", column, definition)
        for column, definition in project_columns:
            _pg_add_column(engine, "projects", column, definition)


def _backfill_milestone_planned_hours(session: Session) -> None:
    milestones = session.scalars(select(Milestone)).all()
    for row in milestones:
        if row.planned_hours and row.planned_hours > 0:
            continue
        template_hours = session.scalar(
            select(ProjectTemplateMilestone.estimated_hours)
            .join(Project, Project.project_template_id == ProjectTemplateMilestone.project_template_id)
            .where(
                Project.id == row.project_id,
                ProjectTemplateMilestone.milestone_name == row.name,
            )
            .limit(1)
        )
        if template_hours is not None:
            row.planned_hours = Decimal(str(template_hours))
            session.add(row)
    session.commit()


def _backfill_project_planned_hours(session: Session) -> None:
    projects = session.scalars(select(Project)).all()
    for project in projects:
        total = session.scalar(
            select(func.coalesce(func.sum(Milestone.planned_hours), 0)).where(
                Milestone.project_id == project.id
            )
        )
        planned = Decimal(str(total or 0))
        if project.current_planned_hours != planned:
            project.current_planned_hours = planned
            session.add(project)
    session.commit()


def ensure_phase10_milestone_foundation(engine: Engine) -> None:
    ensure_phase10_milestone_columns(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        _backfill_milestone_planned_hours(session)
        _backfill_project_planned_hours(session)
    finally:
        session.close()
