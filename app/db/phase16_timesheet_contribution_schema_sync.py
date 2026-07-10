"""Phase 16 — optional contribution reason on timesheet entries."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase16_timesheet_contribution_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "timesheet_entries", "contribution_reason"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE timesheet_entries "
                        "ADD COLUMN contribution_reason VARCHAR(40)"
                    )
                )
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE timesheet_entries "
                    "ADD COLUMN IF NOT EXISTS contribution_reason VARCHAR(40)"
                )
            )
