"""Phase 84 — Project classification (Full Design / Small Task) and configurable task types."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.models import Project, ProjectSmallTaskType  # noqa: F401


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
            ),
            {"name": table_name},
        ).fetchone()
    return row is not None


def ensure_project_small_task_types_table(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[ProjectSmallTaskType.__table__],
        checkfirst=True,
    )


def ensure_project_classification_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "projects", "project_classification"):
                connection.execute(
                    text(
                        "ALTER TABLE projects "
                        "ADD COLUMN project_classification VARCHAR(32) "
                        "NOT NULL DEFAULT 'unclassified'"
                    )
                )
            if not _sqlite_has_column(engine, "projects", "small_task_type_id"):
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN small_task_type_id CHAR(36)")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS project_classification VARCHAR(32) "
                    "NOT NULL DEFAULT 'unclassified'"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS small_task_type_id UUID "
                    "REFERENCES project_small_task_types(id)"
                )
            )


def ensure_phase84_project_classification_foundation(engine: Engine) -> None:
    ensure_project_small_task_types_table(engine)
    ensure_project_classification_columns(engine)
