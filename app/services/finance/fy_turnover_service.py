"""
FY turnover / cash collection control metrics.

Turnover (P&L): recognized by invoice line_date (or legacy quote.invoiced_date).
Cash collected: recognized by payment line_date (or legacy quote.paid_date).

Average monthly billing = FYTD turnover ÷ elapsed months (zero-billing months count).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Quote, QuoteRevision
from app.services.finance.fy_calendar_service import (
    elapsed_fy_months,
    fy_month_windows,
    month_index_for_date,
    resolve_fy_context,
)
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _current_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    current = db.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
    )
    if current is not None:
        return current
    return db.scalar(
        select(QuoteRevision)
        .where(QuoteRevision.quote_id == quote.id)
        .order_by(QuoteRevision.version.desc())
        .limit(1)
    )


def _quote_fx_to_inr(revision: QuoteRevision | None) -> Decimal:
    if revision is None:
        return Decimal("1")
    quoted = _d(revision.quoted_revenue)
    base = _d(revision.base_quoted_revenue_inr)
    if quoted > 0 and base > 0:
        return (base / quoted).quantize(Decimal("0.00000001"))
    return Decimal("1")


def quote_ledger_inr(db: Session, quote: Quote) -> dict:
    """Dated INR invoice and payment amounts for one quote, using the turnover rules above.

    Shared by the FY turnover control and management reporting so both read the same ledger:
    ``invoices`` and ``payments`` are ``(date, amount_inr)`` pairs, ``outstanding_inr`` is the
    current balance due, ``awarded_inr`` the current revision value in INR (as the Finance
    dashboard counts it) and ``awarded_on`` its effective quoted date (``None`` when undated).
    """
    from app.services.finance.plan_sales_from_quotes_service import effective_quoted_date

    revision = _current_revision(db, quote)
    fx = _quote_fx_to_inr(revision)
    invoices: list[tuple[date, Decimal]] = []
    payments: list[tuple[date, Decimal]] = []
    cash: dict | None = None

    def summary() -> dict:
        nonlocal cash
        if cash is None:
            cash = summarize_quote_cash(db, quote, revision=revision)
        return cash

    invoice_lines = list(quote.invoice_lines or [])
    payment_lines = list(quote.payment_lines or [])
    if invoice_lines:
        invoices = [(line.line_date, _d(line.amount) * fx) for line in invoice_lines if line.line_date]
    elif quote.is_invoiced and quote.invoiced_date is not None:
        # Legacy flag-only invoice: recognize full contracted revenue on invoiced_date.
        amount = _d(summary()["total_invoiced"])
        if amount <= 0 and revision is not None:
            amount = _d(revision.quoted_revenue)
        if amount > 0:
            invoices = [(quote.invoiced_date, amount * fx)]
    if payment_lines:
        payments = [(line.line_date, _d(line.amount) * fx) for line in payment_lines if line.line_date]
    elif quote.is_paid and quote.paid_date is not None:
        amount = _d(summary()["total_paid"])
        if amount <= 0 and revision is not None:
            amount = _d(revision.quoted_revenue)
        if amount > 0:
            payments = [(quote.paid_date, amount * fx)]

    base = _d(revision.base_quoted_revenue_inr) if revision else Decimal("0")
    quoted = _d(revision.quoted_revenue) if revision else Decimal("0")
    return {
        "invoices": invoices,
        "payments": payments,
        "outstanding_inr": _d(summary()["balance_due"]) * fx,
        "awarded_inr": base if base > 0 else quoted,
        "awarded_on": effective_quoted_date(quote, revision),
        "currency_code": quote.currency_code,
    }


def build_fy_turnover_control(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
    fy_start_year: int | None = None,
) -> dict:
    """Month-on-month turnover, cash collection, and average monthly billing for a FY."""
    ctx = resolve_fy_context(db, today=today, fy_start_year=fy_start_year)
    fy_start: date = ctx["fy_start"]
    fy_end: date = ctx["fy_end"]
    as_of: date = ctx["today"]
    windows = fy_month_windows(fy_start)
    elapsed = elapsed_fy_months(fy_start, as_of, fy_end)

    turnover_by_month = [Decimal("0.00") for _ in range(12)]
    cash_by_month = [Decimal("0.00") for _ in range(12)]

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

    outstanding = Decimal("0.00")
    for quote in db.scalars(stmt).all():
        ledger = quote_ledger_inr(db, quote)
        for when, amount in ledger["invoices"]:
            idx = month_index_for_date(fy_start, when)
            if idx is not None:
                turnover_by_month[idx] += amount
        for when, amount in ledger["payments"]:
            idx = month_index_for_date(fy_start, when)
            if idx is not None:
                cash_by_month[idx] += amount
        outstanding += ledger["outstanding_inr"]

    months_out: list[dict] = []
    for i, window in enumerate(windows):
        turnover = turnover_by_month[i].quantize(Decimal("0.01"))
        cash = cash_by_month[i].quantize(Decimal("0.01"))
        is_elapsed = i < elapsed
        months_out.append(
            {
                "index": i,
                "label": window["label"],
                "short_label": window["short_label"],
                "month_start": window["month_start"].isoformat(),
                "month_end": window["month_end"].isoformat(),
                "turnover_inr": turnover,
                "cash_collected_inr": cash,
                "is_elapsed": is_elapsed,
                "is_current_month": (
                    window["calendar_year"] == as_of.year
                    and window["calendar_month"] == as_of.month
                ),
                "has_billing": turnover > 0,
            }
        )

    fytd_turnover = sum(
        (row["turnover_inr"] for row in months_out if row["is_elapsed"]),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    fytd_cash = sum(
        (row["cash_collected_inr"] for row in months_out if row["is_elapsed"]),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    average_monthly = (
        (fytd_turnover / Decimal(elapsed)).quantize(Decimal("0.01"))
        if elapsed > 0
        else Decimal("0.00")
    )

    current_idx = month_index_for_date(fy_start, as_of)
    current_turnover = (
        months_out[current_idx]["turnover_inr"] if current_idx is not None else Decimal("0.00")
    )
    previous_idx = current_idx - 1 if current_idx is not None and current_idx > 0 else None
    previous_turnover = (
        months_out[previous_idx]["turnover_inr"] if previous_idx is not None else Decimal("0.00")
    )
    mom_change_percent: Decimal | None = None
    if previous_idx is not None and previous_turnover > 0:
        mom_change_percent = (
            (current_turnover - previous_turnover) / previous_turnover * Decimal("100")
        ).quantize(Decimal("0.01"))
    elif previous_idx is not None and previous_turnover == 0 and current_turnover > 0:
        mom_change_percent = Decimal("100.00")

    elapsed_rows = [row for row in months_out if row["is_elapsed"]]
    billing_months = sum(1 for row in elapsed_rows if row["has_billing"])
    zero_billing_months = max(0, elapsed - billing_months)

    highest = None
    lowest = None
    if elapsed_rows:
        highest = max(elapsed_rows, key=lambda r: r["turnover_inr"])
        lowest = min(elapsed_rows, key=lambda r: r["turnover_inr"])

    return {
        "fy_label": ctx["fy_label"],
        "fy_short_label": ctx["fy_short_label"],
        "fy_start": fy_start.isoformat(),
        "fy_end": fy_end.isoformat(),
        "fy_start_month": ctx["fy_start_month"],
        "fy_start_year": ctx["fy_start_year"],
        "is_current_fy": ctx["is_current_fy"],
        "as_of": as_of.isoformat(),
        "elapsed_months": elapsed,
        "months_with_billing": billing_months,
        "zero_billing_months": zero_billing_months,
        "fytd_turnover_inr": fytd_turnover,
        "fytd_cash_collected_inr": fytd_cash,
        "average_monthly_billing_inr": average_monthly,
        "current_month_turnover_inr": current_turnover,
        "previous_month_turnover_inr": previous_turnover,
        "mom_change_percent": mom_change_percent,
        "highest_billing_month": (
            {
                "label": highest["label"],
                "turnover_inr": highest["turnover_inr"],
            }
            if highest
            else None
        ),
        "lowest_billing_month": (
            {
                "label": lowest["label"],
                "turnover_inr": lowest["turnover_inr"],
            }
            if lowest
            else None
        ),
        "outstanding_receivables_inr": outstanding.quantize(Decimal("0.01")),
        "months": months_out,
        "method_notes": {
            "turnover": (
                "Turnover is recognized by invoice date (quote_invoice_lines.line_date). "
                "Payment date does not move turnover between months."
            ),
            "cash_collected": (
                "Cash collected is recognized by payment date "
                "(quote_payment_lines.line_date)."
            ),
            "average_monthly_billing": (
                "FYTD turnover ÷ elapsed months in the financial year, "
                "including months with zero billing."
            ),
        },
    }
