"""Phase 61 — quote partial invoice / payment ledger tables + legacy backfill."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _table_exists(connection, table_name: str) -> bool:
    dialect = connection.engine.dialect.name
    if dialect == "sqlite":
        row = connection.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"
            ),
            {"name": table_name},
        ).fetchone()
        return row is not None
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :name"
        ),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _create_tables(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_invoice_lines (
                        id CHAR(36) NOT NULL PRIMARY KEY,
                        quote_id CHAR(36) NOT NULL,
                        amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        line_date DATE NOT NULL,
                        notes TEXT,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(quote_id) REFERENCES quotes(id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_quote_id "
                    "ON quote_invoice_lines (quote_id)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_payment_lines (
                        id CHAR(36) NOT NULL PRIMARY KEY,
                        quote_id CHAR(36) NOT NULL,
                        amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        line_date DATE NOT NULL,
                        reference VARCHAR(200),
                        notes TEXT,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(quote_id) REFERENCES quotes(id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_payment_lines_quote_id "
                    "ON quote_payment_lines (quote_id)"
                )
            )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_invoice_lines (
                        id UUID PRIMARY KEY,
                        quote_id UUID NOT NULL REFERENCES quotes(id),
                        amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        line_date DATE NOT NULL,
                        notes TEXT,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_invoice_lines_quote_id "
                    "ON quote_invoice_lines (quote_id)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quote_payment_lines (
                        id UUID PRIMARY KEY,
                        quote_id UUID NOT NULL REFERENCES quotes(id),
                        amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                        line_date DATE NOT NULL,
                        reference VARCHAR(200),
                        notes TEXT,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_quote_payment_lines_quote_id "
                    "ON quote_payment_lines (quote_id)"
                )
            )


def backfill_legacy_quote_cash_lines(db: Session) -> int:
    """Create ledger lines from legacy is_invoiced / is_paid when none exist."""
    from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision
    from sqlalchemy import select

    created = 0
    quotes = list(db.scalars(select(Quote).where(Quote.is_active.is_(True))).all())
    for quote in quotes:
        inv_count = db.scalar(
            select(QuoteInvoiceLine.id).where(QuoteInvoiceLine.quote_id == quote.id).limit(1)
        )
        if inv_count is not None:
            continue
        if not quote.is_invoiced:
            continue

        revision = db.scalar(
            select(QuoteRevision).where(
                QuoteRevision.quote_id == quote.id,
                QuoteRevision.version == quote.current_version,
                QuoteRevision.revision == quote.current_revision,
            )
        )
        amount = Decimal(str(revision.quoted_revenue)) if revision else Decimal("0")
        if amount <= 0:
            continue
        line_date = quote.invoiced_date or quote.quoted_date or date.today()
        db.add(
            QuoteInvoiceLine(
                id=uuid.uuid4(),
                quote_id=quote.id,
                amount=amount,
                line_date=line_date,
                notes="Backfilled from legacy invoiced flag",
                sort_order=0,
            )
        )
        created += 1
        if quote.is_paid:
            pay_count = db.scalar(
                select(QuotePaymentLine.id)
                .where(QuotePaymentLine.quote_id == quote.id)
                .limit(1)
            )
            if pay_count is None:
                db.add(
                    QuotePaymentLine(
                        id=uuid.uuid4(),
                        quote_id=quote.id,
                        amount=amount,
                        line_date=quote.paid_date or line_date,
                        reference="Backfilled from legacy paid flag",
                        sort_order=0,
                    )
                )
                created += 1
    if created:
        db.commit()
    return created


def ensure_phase61_quote_partial_payments_foundation(engine: Engine) -> None:
    _create_tables(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        backfill_legacy_quote_cash_lines(session)
    finally:
        session.close()
