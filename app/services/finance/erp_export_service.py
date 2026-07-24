"""Generic ERP journal CSV export (R3 adapter stub — not live sync)."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Expense, Quote, QuoteRevision
from app.models.models import Customer, Team


def build_erp_journal_csv(
    db: Session,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> str:
    """Fixed-column CSV suitable for manual ERP import (generic layout)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "entry_date",
            "entry_type",
            "reference",
            "customer_or_vendor",
            "team",
            "business_unit",
            "currency",
            "amount",
            "amount_inr",
            "description",
        ]
    )

    quotes = list(db.scalars(select(Quote).where(Quote.is_invoiced.is_(True))).all())
    for quote in quotes:
        inv_date = quote.invoiced_date or quote.quoted_date
        if from_date and inv_date and inv_date < from_date:
            continue
        if to_date and inv_date and inv_date > to_date:
            continue
        customer = db.get(Customer, quote.customer_id)
        team = db.get(Team, quote.team_id) if quote.team_id else None
        revision = db.scalar(
            select(QuoteRevision)
            .where(
                QuoteRevision.quote_id == quote.id,
                QuoteRevision.version == quote.current_version,
            )
            .limit(1)
        )
        amount = revision.quoted_revenue if revision else Decimal("0")
        amount_inr = (
            revision.base_quoted_revenue_inr
            if revision and revision.base_quoted_revenue_inr is not None
            else amount
        )
        writer.writerow(
            [
                inv_date.isoformat() if inv_date else "",
                "invoice",
                quote.external_quote_number or quote.tool_number,
                customer.name if customer else "",
                team.name if team else "",
                getattr(team, "business_unit", None) or "",
                quote.currency_code or "INR",
                str(amount or 0),
                str(amount_inr or 0),
                f"Invoiced quote {quote.tool_number}",
            ]
        )

    expenses = list(db.scalars(select(Expense).where(Expense.is_active.is_(True))).all())
    for expense in expenses:
        exp_date = expense.purchase_date or expense.fx_date or expense.start_date
        if from_date and exp_date and exp_date < from_date:
            continue
        if to_date and exp_date and exp_date > to_date:
            continue
        team = db.get(Team, expense.team_id) if expense.team_id else None
        writer.writerow(
            [
                exp_date.isoformat() if exp_date else "",
                "expense",
                expense.name,
                expense.vendor_name or "",
                team.name if team else "",
                getattr(team, "business_unit", None) or "",
                expense.currency_code or "INR",
                str(expense.amount or 0),
                str(expense.base_amount_inr or expense.amount or 0),
                expense.description or expense.name,
            ]
        )

    return buffer.getvalue()
