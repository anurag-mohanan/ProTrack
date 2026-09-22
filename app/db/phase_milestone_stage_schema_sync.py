"""Milestone stage mapping + project stage history for milestone-driven sync."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import ProjectStage
from app.models.models import Milestone, Project, ProjectTemplateMilestone


# Common milestone name → stage mapping used when template stage is unset.
STAGE_NAME_HINTS: dict[str, ProjectStage] = {
    "feasibility": ProjectStage.feasibility,
    "blockout": ProjectStage.preliminary,
    "roughing": ProjectStage.preliminary,
    "intermediate review": ProjectStage.intermediate,
    "final review": ProjectStage.final,
}


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


def _sqlite_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    if not _sqlite_has_column(engine, table, column):
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def _pg_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        )


def ensure_milestone_stage_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    columns = [
        ("is_required", "BOOLEAN NOT NULL DEFAULT 1"),
        ("project_stage", "VARCHAR(32)"),
    ]
    if dialect == "sqlite":
        for column, definition in columns:
            _sqlite_add_column(engine, "milestones", column, definition)
    elif dialect == "postgresql":
        for column, definition in columns:
            _pg_add_column(engine, "milestones", column, definition)


def ensure_project_stage_history_table(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if _sqlite_has_table(engine, "project_stage_history"):
            return
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE project_stage_history (
                        id BLOB NOT NULL PRIMARY KEY,
                        tenant_id BLOB,
                        project_id BLOB NOT NULL,
                        previous_stage VARCHAR(32),
                        new_stage VARCHAR(32) NOT NULL,
                        changed_at DATETIME NOT NULL,
                        trigger VARCHAR(40) NOT NULL,
                        triggered_by_user_id BLOB,
                        related_milestone_id BLOB,
                        reason TEXT,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                        FOREIGN KEY(triggered_by_user_id) REFERENCES users(id),
                        FOREIGN KEY(related_milestone_id) REFERENCES milestones(id)
                    )
                    """
                )
            )
    elif dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS project_stage_history (
                        id UUID NOT NULL PRIMARY KEY,
                        tenant_id UUID,
                        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        previous_stage VARCHAR(32),
                        new_stage VARCHAR(32) NOT NULL,
                        changed_at TIMESTAMPTZ NOT NULL,
                        trigger VARCHAR(40) NOT NULL,
                        triggered_by_user_id UUID REFERENCES users(id),
                        related_milestone_id UUID REFERENCES milestones(id),
                        reason TEXT,
                        created_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ
                    )
                    """
                )
            )


def _infer_stage_from_name(name: str | None) -> ProjectStage | None:
    if not name:
        return None
    return STAGE_NAME_HINTS.get(name.strip().lower())


def backfill_milestone_stage_fields(session: Session) -> None:
    """Copy is_required / project_stage from template by name; fall back to hints."""
    milestones = session.query(Milestone).all()
    for row in milestones:
        changed = False
        project = session.get(Project, row.project_id)
        template_row = None
        if project is not None and project.project_template_id is not None:
            template_row = (
                session.query(ProjectTemplateMilestone)
                .filter(
                    ProjectTemplateMilestone.project_template_id == project.project_template_id,
                    ProjectTemplateMilestone.milestone_name == row.name,
                )
                .first()
            )
        if template_row is not None:
            if getattr(row, "is_required", True) != bool(template_row.is_required):
                row.is_required = bool(template_row.is_required)
                changed = True
            if row.project_stage is None and template_row.project_stage is not None:
                row.project_stage = template_row.project_stage
                changed = True
        elif not hasattr(row, "is_required") or row.is_required is None:
            row.is_required = True
            changed = True
        if row.project_stage is None:
            inferred = _infer_stage_from_name(row.name)
            if inferred is not None:
                row.project_stage = inferred
                changed = True
        if changed:
            session.add(row)
    session.commit()


def ensure_phase_milestone_stage_foundation(engine: Engine) -> None:
    ensure_milestone_stage_columns(engine)
    ensure_project_stage_history_table(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        backfill_milestone_stage_fields(session)
    finally:
        session.close()
