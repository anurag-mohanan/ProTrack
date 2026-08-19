"""Phase 79 — snapshot home team on timesheet entries (no historical rewrite)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase79_timesheet_home_team_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "timesheet_entries", "home_team_id"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE timesheet_entries ADD COLUMN home_team_id CHAR(36)")
                )
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS home_team_id UUID "
                    "REFERENCES teams(id)"
                )
            )
