"""Ensure project workorder / tooling metadata columns exist for searchable Overview details."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("work_order_number", "VARCHAR(100)"),
    ("press_tonnage", "VARCHAR(50)"),
    ("plastic_material", "VARCHAR(150)"),
    ("cavity_count", "INTEGER"),
    ("tool_type", "VARCHAR(100)"),
    ("customer_specs", "TEXT"),
)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_project_workorder_metadata(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        for column_name, ddl in _COLUMNS:
            if not _sqlite_has_column(engine, "projects", column_name):
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE projects ADD COLUMN {column_name} {ddl}")
                    )
        return

    with engine.begin() as connection:
        for column_name, ddl in _COLUMNS:
            connection.execute(
                text(
                    f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {column_name} {ddl}"
                )
            )
