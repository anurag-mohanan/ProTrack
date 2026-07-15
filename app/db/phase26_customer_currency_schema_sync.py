"""Phase 26 — Customer default currency for multi-country Finance."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase26_customer_currency_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "customers", "default_currency_code"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE customers ADD COLUMN default_currency_code "
                        "VARCHAR(3) NOT NULL DEFAULT 'INR'"
                    )
                )
    else:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS default_currency_code "
                    "VARCHAR(3) NOT NULL DEFAULT 'INR'"
                )
            )
