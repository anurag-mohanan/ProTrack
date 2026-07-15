"""Phase 30 — quotes.external_quote_number for Prosohm QT# audit."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase30_quote_external_number_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quotes", "external_quote_number"):
                connection.execute(
                    text(
                        "ALTER TABLE quotes ADD COLUMN external_quote_number VARCHAR(100)"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS "
                    "external_quote_number VARCHAR(100)"
                )
            )
