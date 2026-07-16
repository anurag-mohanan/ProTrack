"""Phase 37 — performance review cycles/sheets/sections/items."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_phase37_performance_reviews_foundation(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS performance_review_cycles (
                    id CHAR(32) PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    review_year INTEGER NOT NULL DEFAULT 0,
                    start_date DATE NULL,
                    end_date DATE NULL,
                    due_date DATE NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'draft',
                    created_by_id CHAR(32) NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS performance_review_sheets (
                    id CHAR(32) PRIMARY KEY,
                    cycle_id CHAR(32) NULL,
                    employee_id CHAR(32) NOT NULL,
                    reviewer_id CHAR(32) NOT NULL,
                    team_id CHAR(32) NULL,
                    period_label VARCHAR(120) NOT NULL DEFAULT '',
                    status VARCHAR(32) NOT NULL DEFAULT 'draft',
                    review_date DATE NULL,
                    due_date DATE NULL,
                    overall_score NUMERIC(5, 2) NULL,
                    employee_summary TEXT NULL,
                    manager_summary TEXT NULL,
                    strengths_summary TEXT NULL,
                    improvement_summary TEXT NULL,
                    career_goals TEXT NULL,
                    submitted_at DATETIME NULL,
                    acknowledged_at DATETIME NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS performance_review_sections (
                    id CHAR(32) PRIMARY KEY,
                    sheet_id CHAR(32) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    description TEXT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS performance_review_items (
                    id CHAR(32) PRIMARY KEY,
                    section_id CHAR(32) NOT NULL,
                    prompt TEXT NOT NULL,
                    rating NUMERIC(5, 2) NULL,
                    employee_comment TEXT NULL,
                    manager_comment TEXT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL
                )
                """
            )
        )
