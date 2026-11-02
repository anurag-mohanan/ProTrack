"""Billing and collection predictions (billing-1, collections-1). Never changes Finance records.

Both start from the Phase 3 forecast items, which already separate awarded, invoiced, collected
and outstanding amounts from the cash ledger. A prediction only moves an item in time:

* a collection from its contractual due date by the customer's (else the company's) median
  payment delay, conditioned on how long it is already overdue;
* a completion-triggered billing milestone to the actual or predicted completion plus the
  historical completion-to-invoice lag, conditioned on how long it has already waited.

Completion alone is never treated as an invoice: without lag history nothing is dated.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ExecutionStatus
from app.models.finance import Quote
from app.models.models import Project
from app.models.prediction import PREDICTED
from app.schemas.forecasting import FinanceForecastResponse
from app.services.finance.payment_schedule_service import matched_invoice_line
from app.services.finance.quote_cash_ledger_service import calculate_awarded_quote_financial_status
from app.services.forecasting.definitions import build_periods, period_key_for
from app.services.predictive.stats import MIN_SAMPLE, central
from app.services.predictive.types import CALCULATION, Outcome, factor

BILLING = "finance_billing"
COLLECTIONS = "finance_collections"
BILLING_VERSION = "billing-1"
COLLECTIONS_VERSION = "collections-1"
PERIODS = 6
COMPLETION_TRIGGER = "PROJECT_COMPLETION"
_MONEY = Decimal("0.01")


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY)


@dataclass
class Ledger:
    quote: Quote
    project: Project | None
    lines: list
    payments: list


def load_ledgers(db: Session) -> list[Ledger]:
    quotes = list(db.scalars(select(Quote).where(Quote.is_active.is_(True)).options(selectinload(Quote.payment_milestones))))
    project_ids = {q.project_id for q in quotes if q.project_id}
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(project_ids)))} if project_ids else {}
    out = []
    for quote in quotes:
        cash = calculate_awarded_quote_financial_status(db, quote)
        out.append(Ledger(quote, projects.get(quote.project_id), list(cash["invoice_lines"]), list(cash.get("payment_lines") or [])))
    return out


def paid_allocations(lines: list, payments: list, until: date | None = None) -> dict[UUID, list[tuple[date, Decimal]]]:
    """Dated FIFO allocation of payments onto invoice lines, in the Phase 3 aging order."""
    ordered = sorted(lines, key=lambda line: (line.line_date or date.min, line.sort_order or 0))
    owed = [[line.id, _d(line.amount)] for line in ordered]
    out: dict[UUID, list[tuple[date, Decimal]]] = defaultdict(list)
    index = 0
    for payment in sorted(payments, key=lambda p: (p.line_date or date.min, p.sort_order or 0)):
        if payment.line_date is None or (until is not None and payment.line_date > until):
            continue
        left = _d(payment.amount)
        while left > 0 and index < len(owed):
            line_id, remaining = owed[index]
            applied = min(left, remaining)
            if applied > 0:
                out[line_id].append((payment.line_date, applied))
            owed[index][1] -= applied
            left -= applied
            if owed[index][1] <= 0:
                index += 1
    return out


def payment_delays(ledgers: list[Ledger], as_of: date) -> list[tuple[UUID | None, int]]:
    """(customer, days from due date to full payment) for invoice lines fully paid by ``as_of``."""
    out = []
    for ledger in ledgers:
        allocations = paid_allocations(ledger.lines, ledger.payments, until=as_of)
        for line in ledger.lines:
            if line.due_date is None or line.line_date is None or line.line_date > as_of:
                continue
            paid = allocations.get(line.id, [])
            if paid and sum(a for _, a in paid) >= _d(line.amount) > 0:
                out.append((ledger.quote.customer_id, (paid[-1][0] - line.due_date).days))
    return out


def invoice_lags(ledgers: list[Ledger], as_of: date) -> list[tuple[UUID | None, int]]:
    """(customer, days from project completion to the invoice) for invoiced completion-triggered milestones."""
    out = []
    for ledger in ledgers:
        project = ledger.project
        if project is None or project.completed_at is None:
            continue
        completed = project.completed_at.date()
        for milestone in ledger.quote.payment_milestones:
            if not milestone.is_active or milestone.trigger_type != COMPLETION_TRIGGER:
                continue
            line = matched_invoice_line(milestone, ledger.lines)
            if line is not None and line.line_date is not None and line.line_date <= as_of:
                out.append((ledger.quote.customer_id, (line.line_date - completed).days))
    return out


def _history(samples: list[tuple[UUID | None, int]], customer_id: UUID | None, elapsed: int | None = None
             ) -> tuple[list[int], str] | tuple[None, str]:
    """Customer history when it has enough cases, else company history; optionally only cases longer than ``elapsed``."""
    def keep(values: list[int]) -> list[int]:
        return [v for v in values if elapsed is None or v > elapsed]

    own = keep([v for c, v in samples if c == customer_id and customer_id is not None])
    if len(own) >= MIN_SAMPLE:
        return own, f"this customer's {len(own)} cases"
    company = keep([v for _, v in samples])
    if len(company) >= MIN_SAMPLE:
        return company, f"{len(company)} company-wide cases"
    return None, f"{len(company)} comparable case(s); {MIN_SAMPLE} needed"


def _currency_totals(forecast: FinanceForecastResponse, currency: str) -> dict:
    t = next((t for t in forecast.totals if t.currency == currency), None)
    if t is None:
        return {}
    return {k: str(getattr(t, k)) for k in ("awarded_value", "invoiced", "collected", "outstanding", "remaining_to_invoice")}


def _period_outcomes(prediction_type: str, currency: str, as_of: date, dated: list[dict], baseline: dict[str, Decimal],
                     forecast: FinanceForecastResponse, *, undated: list[dict], basis_label: str,
                     insufficient: str | None, population: list[str]) -> list[Outcome]:
    periods = build_periods(as_of, "month", PERIODS)
    out = []
    for period in periods:
        items = [i for i in dated if period_key_for(i["expected"], periods) == period.key]
        o = Outcome(
            prediction_type=prediction_type,
            subject_type="currency_period",
            subject_key=f"{currency}:{period.key}",
            subject_label=f"{currency} {period.label}",
            unit="amount",
            currency=currency,
            horizon_start=max(period.start_date, as_of),
            horizon_end=period.end_date,
            baseline_label=basis_label,
            baseline_value=_d(baseline.get(period.key, 0)),
            data_used={
                "ledger_totals": _currency_totals(forecast, currency),
                "items": [{**i, "expected": i["expected"].isoformat(), "amount": str(i["amount"])} for i in items],
                "not_dated": [{**i, "amount": str(i["amount"])} for i in undated],
                # Everything open at the prediction date, so the outcome is checked like for like.
                "population": population,
            },
            warnings=[
                "A forecast invoice or collection is not an actual one; awarded, invoiced, collected and outstanding "
                "amounts are the ledger figures in data used.",
            ],
        )
        if undated:
            o.warnings.append(f"{_d(sum(i['amount'] for i in undated))} {currency} cannot be dated and is not in any month.")
        if insufficient:
            out.append(o.insufficient(insufficient))
            continue
        total = _d(sum((i["amount"] for i in items), Decimal(0)))
        o.status = PREDICTED
        o.predicted_value = total
        o.variance_value = total - o.baseline_value
        o.sample_size = len(items)
        o.factors = [factor("Items expected in this month", len(items), role=CALCULATION),
                     factor(basis_label, str(o.baseline_value), detail="The Phase 3 contractual or committed dating, for comparison.")]
        out.append(o)
    return out


def _reasons(undated: list[dict]) -> str:
    return " ".join(sorted({u["reason"] for u in undated if u["reason"]})) or "No reason was recorded."


def predict_collections(forecast: FinanceForecastResponse, delays: list[tuple[UUID | None, int]], as_of: date) -> list[Outcome]:
    by_currency: dict[str, list] = defaultdict(list)
    for item in forecast.collections:
        by_currency[item.currency].append(item)
    outcomes = []
    for currency in sorted({t.currency for t in forecast.totals}):
        dated, undated = [], []
        for item in by_currency.get(currency, []):
            base = {"invoice_line_id": str(item.invoice_line_id), "invoice": item.invoice_number, "tool_number": item.tool_number,
                    "amount": item.outstanding, "due_date": item.due_date.isoformat() if item.due_date else None}
            if item.due_date is None:
                undated.append({**base, "reason": "The invoice has no due date."})
                continue
            overdue = (as_of - item.due_date).days if item.due_date < as_of else None
            values, basis = _history(delays, item.customer_id, elapsed=overdue)
            if values is None:
                undated.append({**base, "reason": f"Payment history too small ({basis})."})
                continue
            delay = round(central(values))
            expected = max(item.due_date + timedelta(days=delay), as_of + timedelta(days=1))
            dated.append({**base, "expected": expected, "median_delay_days": delay, "basis": basis,
                          "already_overdue_days": overdue})
        insufficient = None
        if not dated and undated:
            insufficient = "No outstanding invoice can be dated: " + _reasons(undated)
        baseline = {k: v for k, v in next((t.collections_by_period for t in forecast.totals if t.currency == currency), {}).items()}
        population = [str(i.invoice_line_id) for i in by_currency.get(currency, [])]
        outcomes.extend(_period_outcomes(COLLECTIONS, currency, as_of, dated, baseline, forecast, undated=undated,
                                         basis_label="Collections on contractual due dates", insufficient=insufficient,
                                         population=population))
    return outcomes


def predict_billing(forecast: FinanceForecastResponse, lags: list[tuple[UUID | None, int]], as_of: date,
                    completions: dict[UUID, tuple[date | None, str]], customers: dict[UUID, UUID | None]) -> list[Outcome]:
    """``completions``: project id → (actual or predicted completion, basis)."""
    outcomes = []
    for currency in sorted({t.currency for t in forecast.totals}):
        dated, undated = [], []
        ready = Decimal(0)
        population = [str(b.milestone_id) for b in forecast.billing if b.currency == currency and b.milestone_id]
        for item in (b for b in forecast.billing if b.currency == currency):
            base = {"milestone_id": str(item.milestone_id) if item.milestone_id else None, "tool_number": item.tool_number,
                    "project_id": str(item.project_id) if item.project_id else None, "amount": item.amount,
                    "milestone": item.milestone_name}
            if item.date_status == "ready_to_invoice":
                ready += item.amount
                continue
            if item.kind != "milestone" or item.trigger_type != COMPLETION_TRIGGER:
                undated.append({**base, "reason": item.reason})
                continue
            completion, completion_basis = completions.get(item.project_id, (None, "no completion prediction"))
            if completion is None:
                undated.append({**base, "reason": f"Invoiced on completion, but there is {completion_basis}."})
                continue
            elapsed = (as_of - completion).days if completion < as_of else None
            values, basis = _history(lags, customers.get(item.quote_id), elapsed=elapsed)
            if values is None:
                undated.append({**base, "reason": f"Completion-to-invoice history too small ({basis})."})
                continue
            lag = round(central(values))
            expected = max(completion + timedelta(days=lag), as_of + timedelta(days=1))
            dated.append({**base, "expected": expected, "completion": completion.isoformat(), "completion_basis": completion_basis,
                          "median_lag_days": lag, "basis": basis})
        insufficient = None
        if not dated and undated:
            insufficient = "No unbilled amount can be dated: " + _reasons(undated)
        baseline = next((t.billing_by_period for t in forecast.totals if t.currency == currency), {})
        period_outcomes = _period_outcomes(BILLING, currency, as_of, dated, baseline, forecast, undated=undated,
                                           basis_label="Billing dated by current target dates", insufficient=insufficient,
                                           population=population)
        for o in period_outcomes:
            if ready:
                o.warnings.append(f"{_d(ready)} {currency} is ready to invoice now and is reported separately, not in a month.")
                o.data_used["ready_to_invoice"] = str(_d(ready))
        outcomes.extend(period_outcomes)
    return outcomes


def collected_in(ledgers: list[Ledger], line_ids: set[str], start: date, end: date) -> Decimal:
    total = Decimal(0)
    for ledger in ledgers:
        for line_id, paid in paid_allocations(ledger.lines, ledger.payments).items():
            if str(line_id) in line_ids:
                total += sum((a for d, a in paid if start <= d <= end), Decimal(0))
    return _d(total)


def invoiced_in(ledgers: list[Ledger], milestone_ids: set[str], start: date, end: date) -> Decimal:
    total = Decimal(0)
    for ledger in ledgers:
        for milestone in ledger.quote.payment_milestones:
            if str(milestone.id) not in milestone_ids:
                continue
            line = matched_invoice_line(milestone, ledger.lines)
            if line is not None and line.line_date is not None and start <= line.line_date <= end:
                total += _d(line.amount)
    return _d(total)


def completions_for(ledgers: list[Ledger], delivery: dict[UUID, Outcome]) -> dict[UUID, tuple[date | None, str]]:
    out: dict[UUID, tuple[date | None, str]] = {}
    for ledger in ledgers:
        project = ledger.project
        if project is None:
            continue
        if project.execution_status == ExecutionStatus.completed and project.completed_at:
            out[project.id] = (project.completed_at.date(), "actual completion")
            continue
        prediction = delivery.get(project.id)
        if prediction is not None and prediction.status == PREDICTED:
            out[project.id] = (prediction.predicted_date, "predicted completion")
        else:
            out[project.id] = (None, "no completion prediction" + (f" ({prediction.reason})" if prediction and prediction.reason else ""))
    return out
