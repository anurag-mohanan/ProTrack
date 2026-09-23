"""Phase 101 — customer commercial profile + payment milestone schedules."""

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


def ensure_phase101_customer_commercial_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        customer_cols = {
            "default_payment_model": "VARCHAR(40)",
            "default_payment_terms_description": "VARCHAR(500)",
            "country": "VARCHAR(100)",
            "state": "VARCHAR(100)",
            "city": "VARCHAR(100)",
            "website": "VARCHAR(255)",
            "tax_registration_number": "VARCHAR(100)",
        }
        quote_cols = {
            "payment_model": "VARCHAR(40)",
            "payment_terms": "VARCHAR(100)",
            "payment_terms_days": "INTEGER",
            "payment_schedule_source": "VARCHAR(40)",
        }
        invoice_cols = {
            "payment_model": "VARCHAR(40)",
            "payment_milestone_id": "CHAR(36)",
            "payment_milestone_name": "VARCHAR(200)",
            "payment_milestone_percent": "NUMERIC(8, 4)",
            "payment_milestone_amount": "NUMERIC(14, 2)",
            "trigger_event": "VARCHAR(60)",
            "due_date_source": "VARCHAR(40)",
        }

        if dialect == "sqlite":
            for col, ddl in customer_cols.items():
                if not _sqlite_has_column(engine, "customers", col):
                    connection.execute(text(f"ALTER TABLE customers ADD COLUMN {col} {ddl}"))
            for col, ddl in quote_cols.items():
                if not _sqlite_has_column(engine, "quotes", col):
                    connection.execute(text(f"ALTER TABLE quotes ADD COLUMN {col} {ddl}"))
            for col, ddl in invoice_cols.items():
                if not _sqlite_has_column(engine, "quote_invoice_lines", col):
                    connection.execute(
                        text(f"ALTER TABLE quote_invoice_lines ADD COLUMN {col} {ddl}")
                    )

            if not _sqlite_has_table(engine, "customer_payment_milestones"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE customer_payment_milestones (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            customer_id CHAR(36) NOT NULL,
                            sequence INTEGER NOT NULL DEFAULT 1,
                            name VARCHAR(200) NOT NULL,
                            percentage NUMERIC(8, 4),
                            fixed_amount NUMERIC(14, 2),
                            trigger_type VARCHAR(60) NOT NULL DEFAULT 'CUSTOM_EVENT',
                            trigger_description VARCHAR(500),
                            invoice_timing VARCHAR(40) NOT NULL DEFAULT 'ON_TRIGGER',
                            payment_timing VARCHAR(40) NOT NULL DEFAULT 'NET_DAYS',
                            payment_terms_days INTEGER,
                            due_date_rule VARCHAR(200),
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_customer_payment_milestones_customer "
                        "ON customer_payment_milestones (customer_id)"
                    )
                )

            if not _sqlite_has_table(engine, "quote_payment_milestones"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE quote_payment_milestones (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            quote_id CHAR(36) NOT NULL,
                            sequence INTEGER NOT NULL DEFAULT 1,
                            name VARCHAR(200) NOT NULL,
                            percentage NUMERIC(8, 4),
                            fixed_amount NUMERIC(14, 2),
                            trigger_type VARCHAR(60) NOT NULL DEFAULT 'CUSTOM_EVENT',
                            trigger_description VARCHAR(500),
                            invoice_timing VARCHAR(40) NOT NULL DEFAULT 'ON_TRIGGER',
                            payment_timing VARCHAR(40) NOT NULL DEFAULT 'NET_DAYS',
                            payment_terms_days INTEGER,
                            due_date_rule VARCHAR(200),
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            trigger_status VARCHAR(40) NOT NULL DEFAULT 'NOT_YET_TRIGGERED',
                            triggered_at DATETIME,
                            triggered_by_id CHAR(36),
                            fulfilled_invoice_line_id CHAR(36),
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(quote_id) REFERENCES quotes(id) ON DELETE CASCADE,
                            FOREIGN KEY(triggered_by_id) REFERENCES users(id),
                            FOREIGN KEY(fulfilled_invoice_line_id) REFERENCES quote_invoice_lines(id)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_quote_payment_milestones_quote "
                        "ON quote_payment_milestones (quote_id)"
                    )
                )
        else:
            for col, ddl in customer_cols.items():
                connection.execute(
                    text(f"ALTER TABLE customers ADD COLUMN IF NOT EXISTS {col} {ddl}")
                )
            for col, ddl in quote_cols.items():
                connection.execute(
                    text(f"ALTER TABLE quotes ADD COLUMN IF NOT EXISTS {col} {ddl}")
                )
            for col, ddl in invoice_cols.items():
                connection.execute(
                    text(
                        f"ALTER TABLE quote_invoice_lines "
                        f"ADD COLUMN IF NOT EXISTS {col} {ddl}"
                    )
                )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS customer_payment_milestones (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                        sequence INTEGER NOT NULL DEFAULT 1,
                        name VARCHAR(200) NOT NULL,
                        percentage NUMERIC(8, 4),
                        fixed_amount NUMERIC(14, 2),
                        trigger_type VARCHAR(60) NOT NULL DEFAULT 'CUSTOM_EVENT',
                        trigger_description VARCHAR(500),
                        invoice_timing VARCHAR(40) NOT NULL DEFAULT 'ON_TRIGGER',
                        payment_timing VARCHAR(40) NOT NULL DEFAULT 'NET_DAYS',
                        payment_terms_days INTEGER,
                        due_date_rule VARCHAR(200),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_customer_payment_milestones_customer "
                    "ON customer_payment_milestones (customer_id)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_payment_milestones (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
                        sequence INTEGER NOT NULL DEFAULT 1,
                        name VARCHAR(200) NOT NULL,
                        percentage NUMERIC(8, 4),
                        fixed_amount NUMERIC(14, 2),
                        trigger_type VARCHAR(60) NOT NULL DEFAULT 'CUSTOM_EVENT',
                        trigger_description VARCHAR(500),
                        invoice_timing VARCHAR(40) NOT NULL DEFAULT 'ON_TRIGGER',
                        payment_timing VARCHAR(40) NOT NULL DEFAULT 'NET_DAYS',
                        payment_terms_days INTEGER,
                        due_date_rule VARCHAR(200),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        trigger_status VARCHAR(40) NOT NULL DEFAULT 'NOT_YET_TRIGGERED',
                        triggered_at TIMESTAMP,
                        triggered_by_id UUID REFERENCES users(id),
                        fulfilled_invoice_line_id UUID REFERENCES quote_invoice_lines(id),
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_payment_milestones_quote "
                    "ON quote_payment_milestones (quote_id)"
                )
            )
