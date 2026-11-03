"""Business performance: invoiced revenue, collections, awarded value and receivables.

Reads the Finance ledger through ``fy_turnover_service.quote_ledger_inr`` (the FY turnover rules) and
the dated FIFO payment allocation used by Phase 7. No revenue-recognition rule is introduced here:
invoiced revenue is invoice-line dated, collections are payment-line dated, receivables are invoiced
minus paid, awarded value is the active quote revision value. All amounts are INR at each quote's
locked revision rate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Quote
from app.models.models import Customer
from app.services.finance.fy_turnover_service import quote_ledger_inr
from app.services.management.access import ManagementAccess
from app.services.management.filters import CockpitFilters, quote_statement
from app.services.management.metrics import LIMITED, UNAVAILABLE, metric, number, pct
from app.services.predictive.finance import paid_allocations
from app.services.reporting.periods import financial_year_start

ZERO = Decimal("0")
FINANCE_DENIED = "Finance figures need Finance view access."


@dataclass
class QuoteLedger:
    quote: Quote
    invoices: list[tuple[date, Decimal]]
    payments: list[tuple[date, Decimal]]
    outstanding: Decimal
    awarded: Decimal
    awarded_on: date | None


def load_ledgers(db: Session, stmt) -> list[QuoteLedger]:
    quotes = db.scalars(
        stmt.options(selectinload(Quote.invoice_lines), selectinload(Quote.payment_lines))
    ).all()
    out = []
    for quote in quotes:
        ledger = quote_ledger_inr(db, quote)
        out.append(QuoteLedger(quote, ledger["invoices"], ledger["payments"], ledger["outstanding_inr"],
                               ledger["awarded_inr"], ledger["awarded_on"]))
    return out


def _sum(pairs, start: date, end: date) -> Decimal:
    return sum((amount for when, amount in pairs if start <= when <= end), ZERO)


def payment_lead_times(ledgers: list[QuoteLedger], start: date, end: date) -> list[tuple[UUID, int, int | None]]:
    """(customer, invoice→full payment days, due→full payment days) for lines fully paid in the window."""
    out = []
    for item in ledgers:
        lines = list(item.quote.invoice_lines or [])
        allocations = paid_allocations(lines, list(item.quote.payment_lines or []))
        for line in lines:
            paid = allocations.get(line.id, [])
            amount = Decimal(str(line.amount or 0))
            if not paid or line.line_date is None or amount <= 0 or sum(a for _, a in paid) < amount:
                continue
            settled = paid[-1][0]
            if start <= settled <= end:
                late = (settled - line.due_date).days if line.due_date else None
                out.append((item.quote.customer_id, (settled - line.line_date).days, late))
    return out


def customer_names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    return {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_(ids))).all()}


def first_invoice_dates(db: Session, customer_ids: set[UUID]) -> dict[UUID, date]:
    """Earliest recorded invoice per customer over all their active quotes (filters do not apply)."""
    if not customer_ids:
        return {}
    firsts: dict[UUID, date] = {}
    stmt = select(Quote).where(Quote.is_active.is_(True), Quote.customer_id.in_(customer_ids))
    for item in load_ledgers(db, stmt):
        for when, _ in item.invoices:
            cid = item.quote.customer_id
            if cid not in firsts or when < firsts[cid]:
                firsts[cid] = when
    return firsts


def history_start(db: Session) -> date | None:
    stmt = select(Quote).where(Quote.is_active.is_(True))
    dates = [when for item in load_ledgers(db, stmt) for when, _ in item.invoices]
    return min(dates) if dates else None


def build_business(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date | None = None) -> dict:
    if not access.finance:
        return {"visible": False, "reason": FINANCE_DENIED}
    today = today or date.today()
    period = filters.period
    ledgers = load_ledgers(db, quote_statement(db, filters, access))
    invoices = [(when, amount, item.quote.customer_id) for item in ledgers for when, amount in item.invoices]
    payments = [(when, amount, item.quote.customer_id) for item in ledgers for when, amount in item.payments]

    def total(rows, start, end) -> Decimal:
        return sum((a for when, a, _ in rows if start <= when <= end), ZERO)

    invoiced = total(invoices, period.start, period.end)
    collected = total(payments, period.start, period.end)
    awarded_rows = [item for item in ledgers if item.awarded_on and period.start <= item.awarded_on <= period.end]
    awarded = sum((item.awarded for item in awarded_rows), ZERO)
    undated_awards = sum(1 for item in ledgers if item.awarded_on is None)
    outstanding = sum((item.outstanding for item in ledgers), ZERO)

    reference = min(period.end, today)
    fy_start = financial_year_start(reference, period.fy_start_month)
    fy_invoiced = total(invoices, fy_start, reference)

    monthly = []
    previous_amount: Decimal | None = None
    for start, end, label in period.months():
        month_start = date(start.year, start.month, 1)
        prev_end = month_start - timedelta(days=1)
        prev_amount = total(invoices, date(prev_end.year, prev_end.month, 1), prev_end) if previous_amount is None else previous_amount
        amount = total(invoices, start, end)
        monthly.append({
            "month": label, "start": start.isoformat(), "end": end.isoformat(),
            "invoiced": number(amount), "collected": number(total(payments, start, end)),
            "mom_growth_percent": pct(amount - prev_amount, prev_amount) if prev_amount > 0 else None,
            "elapsed": start <= today,
        })
        previous_amount = amount
    elapsed = [row for row in monthly if row["elapsed"]]
    latest = elapsed[-1] if elapsed else None

    by_customer: dict[UUID, dict] = defaultdict(lambda: {"invoiced": ZERO, "collected": ZERO, "outstanding": ZERO,
                                                       "awarded": ZERO})
    for when, amount, cid in invoices:
        if period.start <= when <= period.end:
            by_customer[cid]["invoiced"] += amount
    for when, amount, cid in payments:
        if period.start <= when <= period.end:
            by_customer[cid]["collected"] += amount
    for item in ledgers:
        by_customer[item.quote.customer_id]["outstanding"] += item.outstanding
    for item in awarded_rows:
        by_customer[item.quote.customer_id]["awarded"] += item.awarded
    names = customer_names(db, set(by_customer))
    firsts = first_invoice_dates(db, set(by_customer))
    started = history_start(db)
    history_ok = started is not None and started <= period.start - timedelta(days=365)
    new_revenue = repeat_revenue = ZERO
    new_customers = repeat_customers = 0
    contribution = []
    for cid, values in by_customer.items():
        first = firsts.get(cid)
        segment = None
        if values["invoiced"] > 0 and first is not None:
            segment = "new" if first >= period.start else "repeat"
            if segment == "new":
                new_revenue += values["invoiced"]
                new_customers += 1
            else:
                repeat_revenue += values["invoiced"]
                repeat_customers += 1
        contribution.append({
            "customer_id": str(cid), "customer": names.get(cid, "Unknown customer"),
            "invoiced": number(values["invoiced"]), "share_percent": pct(values["invoiced"], invoiced),
            "collected": number(values["collected"]), "awarded": number(values["awarded"]),
            "outstanding": number(values["outstanding"]), "segment": segment,
        })
    contribution.sort(key=lambda row: (-(row["invoiced"] or 0), -(row["outstanding"] or 0), row["customer"].lower()))

    leads = payment_lead_times(ledgers, period.start, period.end)
    lead_avg = sum(d for _, d, _ in leads) / len(leads) if leads else None
    repeat_note = (
        f"Invoice history in ProTrack starts {started:%d %b %Y}; customers first invoiced near that date may be "
        "repeat customers whose earlier business predates ProTrack." if started else "No invoices are recorded."
    )
    kpis = [
        metric("invoiced_revenue", invoiced if invoices else None, note=None if invoices else "No invoices recorded in scope."),
        metric("fy_invoiced_revenue", fy_invoiced if invoices else None,
               label=f"Invoiced revenue {fy_start:%b %Y} – {reference:%b %Y}"),
        metric("collections", collected if payments else None, note=None if payments else "No payments recorded in scope."),
        metric("awarded_value", awarded if ledgers else None,
               note=(f"{undated_awards} quote(s) have no quoted date and are not in any period." if undated_awards else None),
               sample=len(awarded_rows)),
        metric("outstanding_receivables", outstanding if ledgers else None, note=f"As of {today:%d %b %Y}."),
        metric("mom_growth", latest["mom_growth_percent"] if latest else None,
               note=f"{latest['month']} against the month before." if latest else None),
        metric("repeat_revenue_share", pct(repeat_revenue, new_revenue + repeat_revenue) if (new_revenue + repeat_revenue) else None,
               status=None if not (new_revenue + repeat_revenue) else (None if history_ok else LIMITED), note=repeat_note),
        metric("payment_lead_days", lead_avg, sample=len(leads),
               note=None if leads else "No invoice line was fully paid in the period."),
    ]
    return {
        "visible": True,
        "currency": "INR",
        "as_of": today.isoformat(),
        "quotes_in_scope": len(ledgers),
        "kpis": kpis,
        "monthly": monthly,
        "customers": contribution,
        "new_vs_repeat": {
            "status": UNAVAILABLE if not (new_revenue + repeat_revenue) else ("available" if history_ok else LIMITED),
            "new_customers": new_customers, "repeat_customers": repeat_customers,
            "new_revenue": number(new_revenue), "repeat_revenue": number(repeat_revenue),
            "history_start": started.isoformat() if started else None, "note": repeat_note,
        },
        "notes": [
            "Quoted value is not shown separately: ProTrack records no award status, so active quotes are the awarded value.",
            "Amounts are converted to INR at each quote's locked revision rate (the FY turnover rule).",
            "Filters by classification or project manager keep only quotes linked to matching projects.",
        ],
    }
