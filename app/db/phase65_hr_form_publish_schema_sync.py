"""Phase 65 — publish lock for HR form documents (onboarding, exit, performance)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _add_publish_columns(engine: Engine, table_name: str) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, table_name, "is_published"):
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if not _sqlite_has_column(engine, table_name, "published_at"):
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN published_at DATETIME")
                )
            if not _sqlite_has_column(engine, table_name, "published_by_id"):
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN published_by_id CHAR(36)")
                )
        else:
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITHOUT TIME ZONE"
                )
            )
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN IF NOT EXISTS published_by_id UUID"
                )
            )


def ensure_phase65_hr_form_publish_foundation(engine: Engine) -> None:
    for table in (
        "onboarding_checklists",
        "exit_interviews",
        "performance_review_sheets",
    ):
        _add_publish_columns(engine, table)
