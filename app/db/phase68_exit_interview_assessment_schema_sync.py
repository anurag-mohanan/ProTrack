"""Phase 68 — exit interview TA assessment + complete→offboard fields."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase68_exit_interview_assessment_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    columns = (
        ("attitude_was_good", "BOOLEAN", "BOOLEAN"),
        ("skillset_rating", "INTEGER", "INTEGER"),
        ("eligible_for_rehire", "VARCHAR(20)", "VARCHAR(20)"),
    )
    with engine.begin() as connection:
        if dialect == "sqlite":
            for name, sqlite_type, _pg in columns:
                if not _sqlite_has_column(engine, "exit_interviews", name):
                    connection.execute(
                        text(f"ALTER TABLE exit_interviews ADD COLUMN {name} {sqlite_type}")
                    )
        else:
            for name, _sqlite, pg_type in columns:
                connection.execute(
                    text(
                        f"ALTER TABLE exit_interviews "
                        f"ADD COLUMN IF NOT EXISTS {name} {pg_type}"
                    )
                )
