"""Phase 99 — commercial invoice hours + quote remaining-balance closures."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
    return row is not None


def ensure_phase99_quote_hours_balance_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quote_invoice_lines", "quantity_hours"):
                connection.execute(
                    text(
                        "ALTER TABLE quote_invoice_lines "
                        "ADD COLUMN quantity_hours NUMERIC(12, 2)"
                    )
                )
            if not _sqlite_has_table(engine, "quote_balance_closures"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE quote_balance_closures (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            quote_id CHAR(36) NOT NULL,
                            related_invoice_line_id CHAR(36),
                            closed_hours NUMERIC(12, 2) NOT NULL DEFAULT 0,
                            closed_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                            quoted_hours_snapshot NUMERIC(12, 2),
                            invoiced_hours_snapshot NUMERIC(12, 2),
                            quoted_amount_snapshot NUMERIC(14, 2),
                            invoiced_amount_snapshot NUMERIC(14, 2),
                            reason TEXT,
                            closed_by_id CHAR(36),
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            tenant_id CHAR(36),
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_quote_balance_closures_quote_id "
                        "ON quote_balance_closures (quote_id)"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quote_invoice_lines "
                    "ADD COLUMN IF NOT EXISTS quantity_hours NUMERIC(12, 2)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_balance_closures (
                        id UUID PRIMARY KEY,
                        quote_id UUID NOT NULL REFERENCES quotes(id),
                        related_invoice_line_id UUID REFERENCES quote_invoice_lines(id),
                        closed_hours NUMERIC(12, 2) NOT NULL DEFAULT 0,
                        closed_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        quoted_hours_snapshot NUMERIC(12, 2),
                        invoiced_hours_snapshot NUMERIC(12, 2),
                        quoted_amount_snapshot NUMERIC(14, 2),
                        invoiced_amount_snapshot NUMERIC(14, 2),
                        reason TEXT,
                        closed_by_id UUID REFERENCES users(id),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        tenant_id UUID,
                        created_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_balance_closures_quote_id "
                    "ON quote_balance_closures (quote_id)"
                )
            )
