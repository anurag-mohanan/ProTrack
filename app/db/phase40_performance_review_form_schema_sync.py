"""Phase 40 — review form ownership/tasks + industry experience."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase40_performance_review_form_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "performance_review_sheets", "industry_experience"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sheets "
                        "ADD COLUMN industry_experience VARCHAR(120) NULL"
                    )
                )
            if not _sqlite_has_column(engine, "performance_review_projects", "ownership_type"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_projects "
                        "ADD COLUMN ownership_type VARCHAR(32) NOT NULL DEFAULT 'owned'"
                    )
                )
            if not _sqlite_has_column(engine, "performance_review_projects", "tasks_summary"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_projects "
                        "ADD COLUMN tasks_summary TEXT NULL"
                    )
                )
            return

        connection.execute(
            text(
                "ALTER TABLE performance_review_sheets "
                "ADD COLUMN IF NOT EXISTS industry_experience VARCHAR(120) NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_projects "
                "ADD COLUMN IF NOT EXISTS ownership_type VARCHAR(32) NOT NULL DEFAULT 'owned'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_projects "
                "ADD COLUMN IF NOT EXISTS tasks_summary TEXT NULL"
            )
        )
