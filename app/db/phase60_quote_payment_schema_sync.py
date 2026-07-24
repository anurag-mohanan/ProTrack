"""Phase 60 — quote customer PO + payment tracking / follow-up reminders."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _ensure_pg_enum_value(engine: Engine, enum_name: str, value: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :enum_name AND e.enumlabel = :value
                """
            ),
            {"enum_name": enum_name, "value": value},
        ).scalar()
        if exists:
            return
        connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def ensure_phase60_quote_payment_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quotes", "customer_po_number"):
                connection.execute(
                    text("ALTER TABLE quotes ADD COLUMN customer_po_number VARCHAR(100)")
                )
            if not _sqlite_has_column(engine, "quotes", "is_paid"):
                connection.execute(
                    text(
                        "ALTER TABLE quotes ADD COLUMN is_paid BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if not _sqlite_has_column(engine, "quotes", "paid_date"):
                connection.execute(text("ALTER TABLE quotes ADD COLUMN paid_date DATE"))
            if not _sqlite_has_column(engine, "quotes", "last_payment_reminder_at"):
                connection.execute(
                    text("ALTER TABLE quotes ADD COLUMN last_payment_reminder_at DATE")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS customer_po_number VARCHAR(100)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS is_paid BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS paid_date DATE")
            )
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS last_payment_reminder_at DATE"
                )
            )
    if dialect == "postgresql":
        _ensure_pg_enum_value(engine, "notification_type", "quote_payment_follow_up")
