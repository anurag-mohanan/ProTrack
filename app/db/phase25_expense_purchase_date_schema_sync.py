"""Phase 25 — Expense purchase_date + FY rollup backfill."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase25_expense_purchase_date_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "expenses", "purchase_date"):
                connection.execute(text("ALTER TABLE expenses ADD COLUMN purchase_date DATE"))
        else:
            connection.execute(
                text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS purchase_date DATE")
            )

        # Backfill: start_date → fx_date → date(created_at)
        if dialect == "sqlite":
            connection.execute(
                text(
                    """
                    UPDATE expenses
                    SET purchase_date = COALESCE(
                        start_date,
                        fx_date,
                        date(created_at)
                    )
                    WHERE purchase_date IS NULL
                    """
                )
            )
        else:
            connection.execute(
                text(
                    """
                    UPDATE expenses
                    SET purchase_date = COALESCE(
                        start_date,
                        fx_date,
                        CAST(created_at AS DATE)
                    )
                    WHERE purchase_date IS NULL
                    """
                )
            )
