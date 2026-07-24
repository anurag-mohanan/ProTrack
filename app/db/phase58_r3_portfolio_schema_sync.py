"""Phase 58 — R3 portfolio dimensions (team business_unit).

Idempotent for SQLite and PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _table_exists(engine: Engine, table_name: str) -> bool:
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": table_name},
            ).fetchone()
        return row is not None
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT to_regclass(:n)"), {"n": table_name}
        ).fetchone()
    return bool(row and row[0])


def ensure_phase58_r3_portfolio_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if _table_exists(engine, "teams") and not _sqlite_has_column(
                engine, "teams", "business_unit"
            ):
                connection.execute(
                    text("ALTER TABLE teams ADD COLUMN business_unit VARCHAR(100) NULL")
                )
        elif dialect == "postgresql":
            connection.execute(
                text(
                    "ALTER TABLE teams ADD COLUMN IF NOT EXISTS "
                    "business_unit VARCHAR(100) NULL"
                )
            )
