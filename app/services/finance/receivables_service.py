"""Receivables aging from quote invoice/payment lines (no duplicate invoice store)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Quote
from app.models.models import Customer, Project
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _bucket(days: int) -> str:
    if days <= 30:
        return "0_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_plus"


def build_receivables_aging(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
) -> dict:
    """
    Age outstanding balances by earliest unpaid invoice date on each quote.

    Outstanding = invoiced − paid (quote cash ledger). Days outstanding from
    earliest invoice line date (or legacy invoiced_date) to today.
    """
    today = today or date.today()
    stmt = (
        select(Quote)
        .where(Quote.is_active.is_(True))
        .options(
            selectinload(Quote.invoice_lines),
            selectinload(Quote.payment_lines),
        )
    )
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)

    buckets = {
        "0_30": Decimal("0.00"),
        "31_60": Decimal("0.00"),
        "61_90": Decimal("0.00"),
        "90_plus": Decimal("0.00"),
    }
    rows_out: list[dict] = []

    for quote in db.scalars(stmt).all():
        cash = summarize_quote_cash(db, quote)
        outstanding = _d(cash["balance_due"])
        if outstanding <= 0:
            continue
        invoices = list(quote.invoice_lines or [])
        if invoices:
            invoice_date = min(line.line_date for line in invoices if line.line_date)
            invoice_amount = sum((_d(line.amount) for line in invoices), Decimal("0.00"))
            invoice_notes = next(
                (line.notes for line in invoices if line.notes),
                None,
            )
        elif quote.invoiced_date:
            invoice_date = quote.invoiced_date
            invoice_amount = _d(cash["total_invoiced"])
            invoice_notes = None
        else:
            continue

        days = max(0, (today - invoice_date).days)
        bucket = _bucket(days)
        buckets[bucket] += outstanding

        customer = db.get(Customer, quote.customer_id) if quote.customer_id else None
        project = db.get(Project, quote.project_id) if quote.project_id else None
        payments = list(quote.payment_lines or [])
        last_payment = max((p.line_date for p in payments if p.line_date), default=None)

        rows_out.append(
            {
                "quote_id": str(quote.id),
                "customer_id": str(quote.customer_id) if quote.customer_id else None,
                "customer_name": customer.name if customer else None,
                "project_id": str(quote.project_id) if quote.project_id else None,
                "project_name": project.name if project else None,
                "tool_number": quote.tool_number,
                "invoice_number": invoice_notes,
                "invoice_date": invoice_date.isoformat(),
                "invoice_amount": invoice_amount,
                "paid_amount": _d(cash["total_paid"]),
                "outstanding": outstanding,
                "payment_status": cash.get("payment_status") or cash.get("invoice_status"),
                "last_payment_date": last_payment.isoformat() if last_payment else None,
                "days_outstanding": days,
                "aging_bucket": bucket,
            }
        )

    rows_out.sort(key=lambda r: (-r["days_outstanding"], -float(r["outstanding"])))
    total = sum(buckets.values(), Decimal("0.00")).quantize(Decimal("0.01"))

    return {
        "as_of": today.isoformat(),
        "total_outstanding": total,
        "buckets": {
            "0_30": buckets["0_30"].quantize(Decimal("0.01")),
            "31_60": buckets["31_60"].quantize(Decimal("0.01")),
            "61_90": buckets["61_90"].quantize(Decimal("0.01")),
            "90_plus": buckets["90_plus"].quantize(Decimal("0.01")),
        },
        "bucket_labels": {
            "0_30": "0–30 days",
            "31_60": "31–60 days",
            "61_90": "61–90 days",
            "90_plus": "90+ days",
        },
        "rows": rows_out,
        "method_notes": {
            "outstanding": "Invoiced amount minus payments on the quote cash ledger.",
            "aging": "Days from earliest invoice date (invoice line date) to as-of date.",
            "turnover": "Invoice date still drives P&L turnover; aging is a cash-risk view only.",
        },
    }
