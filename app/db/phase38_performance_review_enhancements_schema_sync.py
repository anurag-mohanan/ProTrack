"""Phase 38 — performance review competency guidance and section notes."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase38_performance_review_enhancements(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "performance_review_items", "guidance"):
                connection.execute(
                    text("ALTER TABLE performance_review_items ADD COLUMN guidance TEXT NULL")
                )
            if not _sqlite_has_column(engine, "performance_review_sections", "employee_notes"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sections ADD COLUMN employee_notes TEXT NULL"
                    )
                )
            if not _sqlite_has_column(engine, "performance_review_sections", "reviewer_notes"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sections ADD COLUMN reviewer_notes TEXT NULL"
                    )
                )
            if not _sqlite_has_column(engine, "performance_review_sheets", "total_experience"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sheets ADD COLUMN total_experience VARCHAR(120) NULL"
                    )
                )
            return

        connection.execute(
            text(
                "ALTER TABLE performance_review_items ADD COLUMN IF NOT EXISTS guidance TEXT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_sections "
                "ADD COLUMN IF NOT EXISTS employee_notes TEXT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_sections "
                "ADD COLUMN IF NOT EXISTS reviewer_notes TEXT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_sheets "
                "ADD COLUMN IF NOT EXISTS total_experience VARCHAR(120) NULL"
            )
        )
