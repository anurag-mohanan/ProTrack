"""Phase 98 — enrich quote invoice/payment lines for PDF import + allocation."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _add_column_sqlite(connection, table: str, column: str, ddl: str) -> None:
    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def ensure_phase98_quote_invoice_enrichment_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            invoice_cols = {
                "invoice_number": "VARCHAR(100)",
                "due_date": "DATE",
                "tax_amount": "NUMERIC(14, 2)",
                "subtotal_amount": "NUMERIC(14, 2)",
                "content_sha256": "VARCHAR(64)",
            }
            for col, ddl in invoice_cols.items():
                if not _sqlite_has_column(engine, "quote_invoice_lines", col):
                    _add_column_sqlite(connection, "quote_invoice_lines", col, ddl)
            if not _sqlite_has_column(engine, "quote_payment_lines", "invoice_line_id"):
                _add_column_sqlite(
                    connection, "quote_payment_lines", "invoice_line_id", "CHAR(36)"
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_invoice_number "
                    "ON quote_invoice_lines (invoice_number)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_content_sha256 "
                    "ON quote_invoice_lines (content_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_payment_lines_invoice_line_id "
                    "ON quote_payment_lines (invoice_line_id)"
                )
            )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(100)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS due_date DATE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(14, 2)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS subtotal_amount NUMERIC(14, 2)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE quote_payment_lines "
                    "ADD COLUMN IF NOT EXISTS invoice_line_id UUID"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_invoice_number "
                    "ON quote_invoice_lines (invoice_number)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_content_sha256 "
                    "ON quote_invoice_lines (content_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_payment_lines_invoice_line_id "
                    "ON quote_payment_lines (invoice_line_id)"
                )
            )
