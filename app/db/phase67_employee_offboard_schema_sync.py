"""Phase 67 — employee soft-offboard tracking (offboard_applied_at)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase67_employee_offboard_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "users", "offboard_applied_at"):
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN offboard_applied_at DATETIME")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS offboard_applied_at TIMESTAMP WITHOUT TIME ZONE"
                )
            )
