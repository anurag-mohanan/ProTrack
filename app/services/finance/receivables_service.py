"""Receivables aging from quote invoice/payment lines (no duplicate invoice store).

Ages by invoice Due Date (not invoice date). Uses FIFO payment allocation onto
invoice lines so partial payments age only the unpaid remainder.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Quote
from app.models.models import Customer, Project
from app.services.finance.customer_financial_service import allocate_invoice_outstanding
from app.services.finance.payment_terms_service import (
    DEFAULT_DUE_SOON_DAYS,
    payment_timing_status,
)
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def build_receivables_aging(
    db: Session,
    *,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
    today: date | None = None,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
) -> dict:
    """
    Age outstanding invoice balances by Due Date.

    Outstanding per invoice line = FIFO(invoice amounts − quote payments).
    Buckets: not_yet_due, due_today, 1–30 / 31–60 / 61–90 / 90+ overdue,
    aging_unavailable (no due date). Fully paid lines are excluded from outstanding.
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
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)

    buckets = {
        "not_yet_due": Decimal("0.00"),
        "due_soon": Decimal("0.00"),
        "due_today": Decimal("0.00"),
        "1_30_overdue": Decimal("0.00"),
        "31_60_overdue": Decimal("0.00"),
        "61_90_overdue": Decimal("0.00"),
        "90_plus_overdue": Decimal("0.00"),
        "aging_unavailable": Decimal("0.00"),
        # Legacy aliases (invoice-date aging) kept for older UI clients
        "0_30": Decimal("0.00"),
        "31_60": Decimal("0.00"),
        "61_90": Decimal("0.00"),
        "90_plus": Decimal("0.00"),
    }
    rows_out: list[dict] = []
    total_outstanding = Decimal("0.00")
    overdue_total = Decimal("0.00")
    not_yet_due_total = Decimal("0.00")
    due_soon_total = Decimal("0.00")
    due_today_total = Decimal("0.00")

    for quote in db.scalars(stmt).all():
        cash = summarize_quote_cash(db, quote)
        if _d(cash["balance_due"]) <= 0:
            continue
        customer = db.get(Customer, quote.customer_id) if quote.customer_id else None
        project = db.get(Project, quote.project_id) if quote.project_id else None
        allocations = allocate_invoice_outstanding(
            list(quote.invoice_lines or []), _d(cash["total_paid"])
        )

        # Legacy fallback when no invoice lines but quote shows outstanding
        if not allocations and quote.invoiced_date:
            timing = payment_timing_status(
                due_date=None,
                outstanding=_d(cash["balance_due"]),
                invoiced=_d(cash["total_invoiced"]),
                paid=_d(cash["total_paid"]),
                today=today,
                due_soon_days=due_soon_days,
            )
            ostand = _d(cash["balance_due"])
            total_outstanding += ostand
            buckets["aging_unavailable"] += ostand
            buckets["0_30"] += ostand  # unknown due date → legacy catch-all
            rows_out.append(
                {
                    "quote_id": str(quote.id),
                    "customer_id": str(quote.customer_id) if quote.customer_id else None,
                    "customer_name": customer.name if customer else None,
                    "project_id": str(quote.project_id) if quote.project_id else None,
                    "project_name": project.name if project else None,
                    "tool_number": quote.tool_number,
                    "invoice_number": None,
                    "invoice_date": quote.invoiced_date.isoformat(),
                    "due_date": None,
                    "payment_terms": None,
                    "payment_terms_days": None,
                    "invoice_amount": _d(cash["total_invoiced"]),
                    "paid_amount": _d(cash["total_paid"]),
                    "outstanding": ostand,
                    "payment_status": cash.get("payment_status"),
                    "days_outstanding": max(0, (today - quote.invoiced_date).days),
                    "days_overdue": timing.get("days_overdue"),
                    "days_until_due": timing.get("days_until_due"),
                    "payment_timing_status": timing.get("payment_timing_status"),
                    "aging_bucket": "aging_unavailable",
                }
            )
            continue

        for alloc in allocations:
            ostand = alloc["outstanding"]
            if ostand <= 0:
                continue
            line = alloc["invoice_line"]
            timing = payment_timing_status(
                due_date=getattr(line, "due_date", None),
                outstanding=ostand,
                invoiced=alloc["invoice_amount"],
                paid=alloc["paid_amount"],
                today=today,
                due_soon_days=due_soon_days,
            )
            bucket = timing["aging_bucket"]
            if bucket in buckets:
                buckets[bucket] += ostand
            pts = timing["payment_timing_status"]
            if pts == "DUE_SOON":
                due_soon_total += ostand
                not_yet_due_total += ostand  # still future-dated
                buckets["0_30"] += ostand
            elif pts == "NOT_YET_DUE":
                not_yet_due_total += ostand
                buckets["0_30"] += ostand
            elif pts == "DUE_TODAY":
                due_today_total += ostand
                buckets["0_30"] += ostand
            elif pts == "OVERDUE" or bucket.endswith("_overdue"):
                overdue_total += ostand
                if bucket == "1_30_overdue":
                    buckets["0_30"] += ostand
                elif bucket == "31_60_overdue":
                    buckets["31_60"] += ostand
                elif bucket == "61_90_overdue":
                    buckets["61_90"] += ostand
                elif bucket == "90_plus_overdue":
                    buckets["90_plus"] += ostand
            elif bucket == "aging_unavailable":
                buckets["aging_unavailable"] += ostand
                buckets["0_30"] += ostand

            total_outstanding += ostand
            invoice_date = line.line_date
            rows_out.append(
                {
                    "quote_id": str(quote.id),
                    "invoice_line_id": str(line.id),
                    "customer_id": str(quote.customer_id) if quote.customer_id else None,
                    "customer_name": customer.name if customer else None,
                    "project_id": str(quote.project_id) if quote.project_id else None,
                    "project_name": project.name if project else None,
                    "tool_number": quote.tool_number,
                    "invoice_number": getattr(line, "invoice_number", None),
                    "invoice_date": invoice_date.isoformat() if invoice_date else None,
                    "due_date": line.due_date.isoformat() if getattr(line, "due_date", None) else None,
                    "payment_terms": getattr(line, "payment_terms", None),
                    "payment_terms_days": getattr(line, "payment_terms_days", None),
                    "payment_terms_source": getattr(line, "payment_terms_source", None),
                    "invoice_amount": alloc["invoice_amount"],
                    "paid_amount": alloc["paid_amount"],
                    "outstanding": ostand,
                    "payment_status": cash.get("payment_status"),
                    "days_outstanding": (
                        max(0, (today - invoice_date).days) if invoice_date else None
                    ),
                    "days_overdue": timing.get("days_overdue"),
                    "days_until_due": timing.get("days_until_due"),
                    "payment_timing_status": timing.get("payment_timing_status"),
                    "aging_bucket": bucket,
                }
            )

    rows_out.sort(
        key=lambda r: (
            -(r.get("days_overdue") or 0),
            -float(r["outstanding"]),
        )
    )

    return {
        "as_of": today.isoformat(),
        "due_soon_days": due_soon_days,
        "total_outstanding": total_outstanding.quantize(Decimal("0.01")),
        "not_yet_due": not_yet_due_total.quantize(Decimal("0.01")),
        "due_soon": due_soon_total.quantize(Decimal("0.01")),
        "due_today": due_today_total.quantize(Decimal("0.01")),
        "overdue": overdue_total.quantize(Decimal("0.01")),
        "buckets": {
            "not_yet_due": buckets["not_yet_due"].quantize(Decimal("0.01")),
            "due_soon": due_soon_total.quantize(Decimal("0.01")),
            "due_today": buckets["due_today"].quantize(Decimal("0.01")),
            "1_30_overdue": buckets["1_30_overdue"].quantize(Decimal("0.01")),
            "31_60_overdue": buckets["31_60_overdue"].quantize(Decimal("0.01")),
            "61_90_overdue": buckets["61_90_overdue"].quantize(Decimal("0.01")),
            "90_plus_overdue": buckets["90_plus_overdue"].quantize(Decimal("0.01")),
            "aging_unavailable": buckets["aging_unavailable"].quantize(Decimal("0.01")),
            # Legacy (invoice-date style keys) for existing FinanceReceivablesSection
            "0_30": buckets["0_30"].quantize(Decimal("0.01")),
            "31_60": buckets["31_60"].quantize(Decimal("0.01")),
            "61_90": buckets["61_90"].quantize(Decimal("0.01")),
            "90_plus": buckets["90_plus"].quantize(Decimal("0.01")),
        },
        "rows": rows_out,
        "method_notes": {
            "aging": (
                "Outstanding = FIFO(invoice line amounts − quote payments). "
                "Aged by invoice Due Date. Fully paid lines excluded. "
                "No Due Date → AGING NOT AVAILABLE."
            ),
            "payment_terms": (
                "payment_terms / payment_terms_days / due_date are invoice snapshots; "
                "customer defaults do not rewrite historical invoices."
            ),
        },
    }
