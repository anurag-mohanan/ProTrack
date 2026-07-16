"""Phase 39 — performance review project accomplishments + review period bounds."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchall()
    return bool(rows)


def ensure_phase39_performance_review_projects_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "performance_review_sheets", "review_period_start"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sheets "
                        "ADD COLUMN review_period_start DATE NULL"
                    )
                )
            if not _sqlite_has_column(engine, "performance_review_sheets", "review_period_end"):
                connection.execute(
                    text(
                        "ALTER TABLE performance_review_sheets "
                        "ADD COLUMN review_period_end DATE NULL"
                    )
                )
            if not _sqlite_has_table(engine, "performance_review_projects"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS performance_review_projects (
                            id CHAR(32) PRIMARY KEY,
                            sheet_id CHAR(32) NOT NULL,
                            project_id CHAR(32) NULL,
                            tool_number VARCHAR(80) NOT NULL DEFAULT '',
                            part_description VARCHAR(255) NULL,
                            customer_name VARCHAR(200) NULL,
                            assignment_role VARCHAR(80) NULL,
                            hours_logged NUMERIC(10, 2) NULL,
                            execution_status VARCHAR(40) NULL,
                            project_stage VARCHAR(40) NULL,
                            completed_at DATE NULL,
                            contribution_summary TEXT NULL,
                            achievement_notes TEXT NULL,
                            is_auto_imported BOOLEAN NOT NULL DEFAULT 0,
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            created_at DATETIME NULL,
                            updated_at DATETIME NULL
                        )
                        """
                    )
                )
            return

        connection.execute(
            text(
                "ALTER TABLE performance_review_sheets "
                "ADD COLUMN IF NOT EXISTS review_period_start DATE NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE performance_review_sheets "
                "ADD COLUMN IF NOT EXISTS review_period_end DATE NULL"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS performance_review_projects (
                    id UUID PRIMARY KEY,
                    sheet_id UUID NOT NULL REFERENCES performance_review_sheets(id) ON DELETE CASCADE,
                    project_id UUID NULL REFERENCES projects(id),
                    tool_number VARCHAR(80) NOT NULL DEFAULT '',
                    part_description VARCHAR(255) NULL,
                    customer_name VARCHAR(200) NULL,
                    assignment_role VARCHAR(80) NULL,
                    hours_logged NUMERIC(10, 2) NULL,
                    execution_status VARCHAR(40) NULL,
                    project_stage VARCHAR(40) NULL,
                    completed_at DATE NULL,
                    contribution_summary TEXT NULL,
                    achievement_notes TEXT NULL,
                    is_auto_imported BOOLEAN NOT NULL DEFAULT FALSE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NULL,
                    updated_at TIMESTAMPTZ NULL
                )
                """
            )
        )
