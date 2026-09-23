"""Phase 100 — invoice payment terms + customer default payment terms."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase100_payment_terms_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        invoice_cols = {
            "payment_terms": "VARCHAR(100)",
            "payment_terms_days": "INTEGER",
            "payment_terms_source": "VARCHAR(40)",
        }
        customer_cols = {
            "default_payment_terms": "VARCHAR(100)",
            "default_payment_terms_days": "INTEGER",
        }
        if dialect == "sqlite":
            for col, ddl in invoice_cols.items():
                if not _sqlite_has_column(engine, "quote_invoice_lines", col):
                    connection.execute(
                        text(f"ALTER TABLE quote_invoice_lines ADD COLUMN {col} {ddl}")
                    )
            for col, ddl in customer_cols.items():
                if not _sqlite_has_column(engine, "customers", col):
                    connection.execute(
                        text(f"ALTER TABLE customers ADD COLUMN {col} {ddl}")
                    )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_due_date "
                    "ON quote_invoice_lines (due_date)"
                )
            )
        else:
            for col, ddl in invoice_cols.items():
                connection.execute(
                    text(
                        f"ALTER TABLE quote_invoice_lines "
                        f"ADD COLUMN IF NOT EXISTS {col} {ddl}"
                    )
                )
            for col, ddl in customer_cols.items():
                connection.execute(
                    text(f"ALTER TABLE customers ADD COLUMN IF NOT EXISTS {col} {ddl}")
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_due_date "
                    "ON quote_invoice_lines (due_date)"
                )
            )
