"""Phase 41 — first-job date + review project complexity snapshot."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase41_performance_review_experience_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "users", "first_job_date"):
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN first_job_date DATE NULL")
                )
            if not _sqlite_has_column(engine, "performance_review_projects", "complexity"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_projects "
                        "ADD COLUMN complexity VARCHAR(20) NULL"
                    )
                )
            return

        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_job_date DATE NULL")
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_projects "
                "ADD COLUMN IF NOT EXISTS complexity VARCHAR(20) NULL"
            )
        )
