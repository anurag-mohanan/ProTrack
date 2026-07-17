"""Phase 44 — quotes.is_invoiced + invoicing reminder tracking."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase44_quote_invoicing_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quotes", "is_invoiced"):
                connection.execute(
                    text(
                        "ALTER TABLE quotes ADD COLUMN is_invoiced BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if not _sqlite_has_column(engine, "quotes", "last_invoicing_reminder_at"):
                connection.execute(
                    text("ALTER TABLE quotes ADD COLUMN last_invoicing_reminder_at DATE")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS is_invoiced BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS last_invoicing_reminder_at DATE"
                )
            )
