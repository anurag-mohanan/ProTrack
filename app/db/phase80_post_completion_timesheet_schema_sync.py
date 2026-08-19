"""Phase 80 — post-completion timesheet classification (no historical rewrite)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase80_post_completion_timesheet_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        with engine.begin() as connection:
            if not _sqlite_has_column(engine, "timesheet_entries", "post_completion_type"):
                connection.execute(
                    text(
                        "ALTER TABLE timesheet_entries "
                        "ADD COLUMN post_completion_type VARCHAR(40)"
                    )
                )
            if not _sqlite_has_column(engine, "teams", "allow_post_completion_timesheet"):
                connection.execute(
                    text(
                        "ALTER TABLE teams "
                        "ADD COLUMN allow_post_completion_timesheet BOOLEAN "
                        "NOT NULL DEFAULT 1"
                    )
                )
            if not _sqlite_has_column(engine, "streams", "allow_post_completion_timesheet"):
                connection.execute(
                    text(
                        "ALTER TABLE streams "
                        "ADD COLUMN allow_post_completion_timesheet BOOLEAN "
                        "NOT NULL DEFAULT 1"
                    )
                )
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS post_completion_type VARCHAR(40)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE teams "
                    "ADD COLUMN IF NOT EXISTS allow_post_completion_timesheet "
                    "BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS allow_post_completion_timesheet "
                    "BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
