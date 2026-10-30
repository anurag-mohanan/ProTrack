"""Billing and collection forecast from the quote cash ledger. Read-only; never changes Finance records."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ExecutionStatus
from app.models.finance import Quote
from app.models.models import Customer, Project
from app.schemas.forecasting import (
    BillingItem,
    CollectionItem,
    CurrencyTotals,
    ExcludedQuote,
    FinanceForecastResponse,
    FinanceReconciliation,
    ForecastPeriod,
)
from app.services.delivery_variance_service import project_current_target
from app.services.finance.customer_financial_service import allocate_invoice_outstanding
from app.services.finance.payment_schedule_service import (
    STATUS_INVOICED,
    STATUS_READY_TO_INVOICE,
    STATUS_TRIGGERED,
    STATUS_WAIVED,
    matched_invoice_line,
    milestone_scheduled_amount,
)
from app.services.finance.quote_cash_ledger_service import (
    calculate_awarded_quote_financial_status,
)
from app.services.forecasting.definitions import (
    FINANCE_METHOD_VERSION,
    build_periods,
    metadata,
    period_key_for,
)

LATER = "later"
_TOLERANCE = Decimal("0.01")
_MONEY = Decimal("0.01")


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY)


def _key(day: date, periods: list[ForecastPeriod]) -> str | None:
    key = period_key_for(day, periods)
    if key is None and day > periods[-1].end_date:
        return LATER
    return key


def _billing_exclusion(project: Project | None) -> str | None:
    if project is None:
        return (
            "Not linked to a project. Quotes have no award status, so only quotes linked to a live "
            "project are treated as awarded."
        )
    if project.is_deleted:
        return "The linked project is deleted."
    if project.execution_status == ExecutionStatus.cancelled:
        return "The linked project is cancelled."
    return None


def _milestone_item(milestone, quote: Quote, project: Project, amount: Decimal, as_of: date,
                    periods: list[ForecastPeriod]) -> BillingItem:
    base = dict(
        quote_id=quote.id,
        tool_number=quote.tool_number,
        project_id=project.id,
        project_code=project.code,
        currency=quote.currency_code,
        kind="milestone",
        milestone_id=milestone.id,
        milestone_name=milestone.name,
        trigger_type=milestone.trigger_type,
        trigger_status=milestone.trigger_status,
        amount=amount,
    )
    if milestone.trigger_status in (STATUS_READY_TO_INVOICE, STATUS_TRIGGERED):
        return BillingItem(**base, date_status="ready_to_invoice",
                           reason="Triggered and ready to invoice; no invoice has been issued yet.")
    if milestone.invoice_timing == "IMMEDIATE":
        return BillingItem(**base, date_status="ready_to_invoice",
                           reason="Invoiced immediately under the schedule; no invoice has been issued yet.")
    if milestone.trigger_type == "PROJECT_COMPLETION" and milestone.invoice_timing == "ON_TRIGGER":
        if project.execution_status == ExecutionStatus.completed:
            return BillingItem(**base, date_status="undated",
                               reason="The project is completed but the billing milestone has not been marked triggered.")
        target = project_current_target(project)
        if target is None:
            return BillingItem(**base, date_status="undated", depends_on_delivery=True,
                               reason="Triggered on completion, but the project has no target date.")
        if target < as_of:
            return BillingItem(**base, date_status="undated", depends_on_delivery=True,
                               reason=f"Triggered on completion; the current target ({target}) has passed and no completion forecast exists.")
        return BillingItem(**base, date_status="dated_by_target", expected_invoice_date=target,
                           expected_period_key=_key(target, periods), depends_on_delivery=True,
                           reason="Dated by the project's current target date: a delivery commitment, not a completion forecast.")
    return BillingItem(**base, date_status="undated",
                       reason=f"Trigger '{milestone.trigger_type}' ({milestone.invoice_timing}) has no recorded date.")


def build_finance_forecast(
    db: Session,
    *,
    as_of: date | None = None,
    granularity: str = "month",
    periods: int = 6,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
) -> FinanceForecastResponse:
    as_of = as_of or date.today()
    period_rows = build_periods(as_of, granularity, periods)
    stmt = (
        select(Quote)
        .where(Quote.is_active.is_(True))
        .options(selectinload(Quote.payment_milestones))
        .order_by(Quote.tool_number)
    )
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)
    quotes = list(db.scalars(stmt).all())

    project_ids = {q.project_id for q in quotes if q.project_id}
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(project_ids))).all()} if project_ids else {}
    customer_ids = {q.customer_id for q in quotes if q.customer_id}
    customers = {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()} if customer_ids else {}

    totals: dict[str, CurrencyTotals] = {}
    collections: list[CollectionItem] = []
    billing: list[BillingItem] = []
    excluded: list[ExcludedQuote] = []
    warnings: list[str] = []
    outstanding_ok = billing_ok = True
    by_project: dict[UUID, list[str]] = defaultdict(list)

    for quote in quotes:
        cash = calculate_awarded_quote_financial_status(db, quote)
        cur = quote.currency_code
        acc = totals.setdefault(cur, CurrencyTotals(currency=cur))
        awarded = _d(cash["awarded_amount"])
        outstanding = _d(cash["outstanding_amount"])
        remaining = _d(cash["remaining_to_invoice"])
        acc.quotes += 1
        acc.awarded_value += awarded
        acc.invoiced += _d(cash["invoiced_amount"])
        acc.collected += _d(cash["paid_amount"])
        acc.outstanding += outstanding
        acc.remaining_to_invoice += remaining
        if cash.get("is_over_invoiced"):
            warnings.append(f"Quote {quote.tool_number}: invoiced more than the awarded value; Finance review required.")
        if quote.project_id:
            by_project[quote.project_id].append(quote.tool_number)

        lines = list(cash["invoice_lines"])
        collected_items = Decimal("0")
        for alloc in allocate_invoice_outstanding(lines, _d(cash["total_paid"])):
            owed = _d(alloc["outstanding"])
            if owed <= 0:
                continue
            line = alloc["invoice_line"]
            due = line.due_date
            if due is None:
                timing, key, overdue = "no_due_date", None, None
                acc.outstanding_no_due_date += owed
            elif due < as_of:
                timing, key, overdue = "overdue", None, (as_of - due).days
                acc.outstanding_overdue += owed
            else:
                timing, key, overdue = "scheduled", _key(due, period_rows), None
                acc.outstanding_scheduled += owed
                acc.collections_by_period[key] = acc.collections_by_period.get(key, Decimal("0")) + owed  # type: ignore[index]
            collected_items += owed
            collections.append(
                CollectionItem(
                    quote_id=quote.id,
                    tool_number=quote.tool_number,
                    customer_id=quote.customer_id,
                    customer_name=customers.get(quote.customer_id),
                    project_id=quote.project_id,
                    currency=cur,
                    invoice_line_id=line.id,
                    invoice_number=line.invoice_number,
                    invoice_date=line.line_date,
                    due_date=due,
                    due_date_source=line.due_date_source,
                    invoice_amount=_d(alloc["invoice_amount"]),
                    paid_amount=_d(alloc["paid_amount"]),
                    outstanding=owed,
                    timing=timing,  # type: ignore[arg-type]
                    expected_period_key=key,
                    days_overdue=overdue,
                )
            )
        if abs(collected_items - outstanding) > _TOLERANCE:
            outstanding_ok = False

        if remaining <= 0:
            continue
        project = projects.get(quote.project_id) if quote.project_id else None
        reason = _billing_exclusion(project)
        if reason:
            excluded.append(ExcludedQuote(quote_id=quote.id, tool_number=quote.tool_number,
                                          currency=cur, remaining_to_invoice=remaining, reason=reason))
            acc.excluded_remaining_to_invoice += remaining
            continue
        assert project is not None
        open_milestones = [
            m for m in quote.payment_milestones
            if m.is_active and m.trigger_status not in (STATUS_WAIVED, STATUS_INVOICED)
            and matched_invoice_line(m, lines) is None
        ]
        amounts = [milestone_scheduled_amount(m, awarded) for m in open_milestones]
        scheduled = sum(amounts, Decimal("0"))
        quote_items: list[BillingItem]
        if scheduled > remaining + _TOLERANCE:
            warnings.append(
                f"Quote {quote.tool_number}: unbilled milestones total {scheduled} {cur} but only "
                f"{remaining} {cur} remains to invoice; the schedule needs review and is not used."
            )
            quote_items = [_unscheduled(quote, project, remaining,
                                        "Billing milestones exceed the remaining value, so no date is assigned.")]
        else:
            quote_items = [
                _milestone_item(m, quote, project, amount, as_of, period_rows)
                for m, amount in zip(open_milestones, amounts)
                if amount > 0
            ]
            rest = remaining - scheduled
            if rest > _TOLERANCE:
                quote_items.append(_unscheduled(quote, project, rest, "Remaining value not covered by a billing milestone."))
        if abs(sum((i.amount for i in quote_items), Decimal("0")) - remaining) > _TOLERANCE:
            billing_ok = False
        for item in quote_items:
            if item.date_status == "ready_to_invoice":
                acc.billing_ready += item.amount
            elif item.date_status == "dated_by_target":
                acc.billing_dated += item.amount
                key = item.expected_period_key or LATER
                acc.billing_by_period[key] = acc.billing_by_period.get(key, Decimal("0")) + item.amount
            else:
                acc.billing_undated += item.amount
        billing.extend(quote_items)

    for project_id, tools in by_project.items():
        if len(tools) > 1:
            warnings.append(
                f"{len(tools)} active quotes ({', '.join(sorted(tools))}) are linked to one project; each is "
                "counted once on its own ledger, but check they are not duplicates."
            )
    for acc in totals.values():
        for key, value in list(acc.collections_by_period.items()):
            acc.collections_by_period[key] = value.quantize(_MONEY)
        for key, value in list(acc.billing_by_period.items()):
            acc.billing_by_period[key] = value.quantize(_MONEY)

    notes = [
        "Outstanding per quote = FIFO allocation of payments onto invoice lines; it equals invoiced − collected.",
        "Billing items per quote add up to remaining to invoice; excluded quotes are listed separately.",
    ]
    if len(totals) > 1:
        notes.append("Several currencies are present; totals are per currency and are never added together.")
    return FinanceForecastResponse(
        metadata=metadata(
            forecast_type="billing_and_collections",
            method_version=FINANCE_METHOD_VERSION,
            as_of=as_of,
            status="available" if quotes else "unavailable",
            status_reason=None if quotes else "No active quotes in scope.",
            period_start=period_rows[0].start_date,
            period_end=period_rows[-1].end_date,
            sources=[
                "Quote cash ledger: current revision awarded value, invoice lines, payment lines, closed balances",
                "Invoice-line due dates and payment terms (snapshots on each invoice)",
                "Quote billing milestones (trigger, timing, status)",
                "Project status and current target date",
            ],
            assumptions=[
                "An active quote linked to a live project is treated as awarded; ProTrack records no award status.",
                "Collections are expected on the contractual due date; no customer payment behaviour is modelled.",
                "A projected invoice is not revenue: P&L turnover is recognised on the invoice date by Finance.",
            ],
            limitations=[
                "Overdue and undated balances have no expected collection date.",
                "Billing milestones are dated only for completion-triggered milestones with a future project target date; that date is a commitment, not a completion forecast.",
                "Collections on invoices that have not been issued yet are not projected.",
                "Payment history is not used: there is no reliable, explainable payment-behaviour model.",
            ],
        ),
        granularity=granularity,  # type: ignore[arg-type]
        periods=period_rows,
        totals=sorted(totals.values(), key=lambda t: t.currency),
        collections=sorted(collections, key=lambda c: (c.due_date or date.max, c.tool_number)),
        billing=billing,
        excluded=excluded,
        warnings=warnings,
        reconciliation=FinanceReconciliation(
            quotes_considered=len(quotes),
            outstanding_matches_ledger=outstanding_ok,
            billing_matches_remaining=billing_ok,
            notes=notes,
        ),
    )


def _unscheduled(quote: Quote, project: Project, amount: Decimal, reason: str) -> BillingItem:
    return BillingItem(
        quote_id=quote.id,
        tool_number=quote.tool_number,
        project_id=project.id,
        project_code=project.code,
        currency=quote.currency_code,
        kind="unscheduled_remaining",
        amount=amount,
        date_status="undated",
        reason=reason,
    )
