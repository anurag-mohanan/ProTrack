"""Phase 19 — per-team timesheet report inclusion flag on team_members."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


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


def ensure_phase19_timesheet_report_inclusion_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    column = ("include_in_timesheet_reports", "BOOLEAN NOT NULL DEFAULT 1")
    if dialect == "sqlite":
        _sqlite_add_column(engine, "team_members", column[0], column[1])
    elif dialect == "postgresql":
        _pg_add_column(engine, "team_members", column[0], column[1])
