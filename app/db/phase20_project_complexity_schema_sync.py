"""Ensure projects.complexity column exists for skill/complexity matching."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_project_complexity(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "complexity"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN complexity "
                        "VARCHAR(32) NOT NULL DEFAULT 'medium'"
                    )
                )
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS complexity "
                "VARCHAR(32) NOT NULL DEFAULT 'medium'"
            )
        )
