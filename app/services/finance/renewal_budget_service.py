"""Renewals → budget forecast / annual plan helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FinancePlanSection
from app.models.finance import Expense, FinancePlan, FinancePlanLine
from app.services.finance.annual_plan_service import (
    QUARTER_FIELDS,
    apply_quarter_amount,
    get_plan,
)


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fy_quarter_index(renewal: date, *, fy_start: date) -> int | None:
    """Return 1–4 for an Indian Eng FY (Apr–Mar), or None if outside FY."""
    if renewal < fy_start:
        return None
    # fy spans fy_start.year Apr → fy_start.year+1 Mar
    fy_end_year = fy_start.year + 1
    if renewal.year == fy_start.year:
        if renewal.month in (4, 5, 6):
            return 1
        if renewal.month in (7, 8, 9):
            return 2
        if renewal.month in (10, 11, 12):
            return 3
        return None
    if renewal.year == fy_end_year and renewal.month in (1, 2, 3):
        return 4
    return None


def fy_quarter_date_bounds(today: date, *, fy_start: date) -> tuple[date, date] | None:
    """Inclusive start/end dates for the FY quarter containing today."""
    idx = fy_quarter_index(today, fy_start=fy_start)
    if idx is None:
        return None
    y = fy_start.year
    if idx == 1:
        return date(y, 4, 1), date(y, 6, 30)
    if idx == 2:
        return date(y, 7, 1), date(y, 9, 30)
    if idx == 3:
        return date(y, 10, 1), date(y, 12, 31)
    return date(y + 1, 1, 1), date(y + 1, 3, 31)


def months_elapsed_in_period(today: date, start: date, end: date) -> int:
    """Calendar months from start through min(today, end), inclusive (0 if before start)."""
    if today < start:
        return 0
    last = min(today, end)
    return (last.year - start.year) * 12 + (last.month - start.month) + 1


def list_renewals_in_fy(
    db: Session,
    *,
    fy_start: date,
    team_id: UUID | None = None,
) -> list[Expense]:
    fy_end = date(fy_start.year + 1, 3, 31)
    stmt = select(Expense).where(
        Expense.is_active.is_(True),
        Expense.next_renewal_date.is_not(None),
        Expense.next_renewal_date >= fy_start,
        Expense.next_renewal_date <= fy_end,
    )
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    return list(db.scalars(stmt.order_by(Expense.next_renewal_date)).all())


def renewals_by_quarter_inr(
    db: Session,
    *,
    fy_start: date,
    team_id: UUID | None = None,
) -> dict[str, Decimal]:
    totals = {q: Decimal("0.00") for q in QUARTER_FIELDS}
    for expense in list_renewals_in_fy(db, fy_start=fy_start, team_id=team_id):
        assert expense.next_renewal_date is not None
        idx = fy_quarter_index(expense.next_renewal_date, fy_start=fy_start)
        if idx is None:
            continue
        totals[f"q{idx}"] += _q(expense.base_amount_inr)
    return totals


def sync_renewals_into_plan(
    db: Session,
    plan_id: UUID,
    *,
    team_id: UUID | None = None,
) -> FinancePlan:
    """Upsert expense lines for known renewals into the correct FY quarter."""
    plan = get_plan(db, plan_id)
    fy_start = plan.fy_start_date
    renewals = list_renewals_in_fy(db, fy_start=fy_start, team_id=team_id)
    if not renewals:
        return plan

    # Group by vendor/name into one line per expense.
    for expense in renewals:
        assert expense.next_renewal_date is not None
        idx = fy_quarter_index(expense.next_renewal_date, fy_start=fy_start)
        if idx is None:
            continue
        code = f"renewal_{str(expense.id).replace('-', '')[:12]}"
        line = next(
            (
                row
                for row in plan.lines
                if row.section == FinancePlanSection.expenses and row.code == code
            ),
            None,
        )
        label = f"Renewal: {expense.name}"
        if line is None:
            max_sort = max(
                (row.sort_order for row in plan.lines if row.section == FinancePlanSection.expenses),
                default=100,
            )
            line = FinancePlanLine(
                plan_id=plan.id,
                section=FinancePlanSection.expenses,
                code=code,
                label=label[:200],
                sort_order=max_sort + 10,
                month_01=Decimal("0"),
                month_02=Decimal("0"),
                month_03=Decimal("0"),
                month_04=Decimal("0"),
                month_05=Decimal("0"),
                month_06=Decimal("0"),
                month_07=Decimal("0"),
                month_08=Decimal("0"),
                month_09=Decimal("0"),
                month_10=Decimal("0"),
                month_11=Decimal("0"),
                month_12=Decimal("0"),
            )
            db.add(line)
            plan.lines.append(line)
            db.flush()
        else:
            line.label = label[:200]
        # Clear all quarters then set the renewal quarter.
        for q in QUARTER_FIELDS:
            apply_quarter_amount(line, q, Decimal("0"))
        apply_quarter_amount(line, f"q{idx}", _q(expense.base_amount_inr))
        line.notes = (
            f"Auto from expense renewal on {expense.next_renewal_date.isoformat()} "
            f"({expense.currency_code})"
        )
    db.flush()
    return plan


def apply_renewals_to_budget_forecast_quarters(
    *,
    q_allocated: dict[str, Decimal],
    renewals: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Forecast = allocated quarter + known renewals in that quarter."""
    return {q: _q(q_allocated.get(q, 0) + renewals.get(q, 0)) for q in QUARTER_FIELDS}


def even_split_four(total: Decimal) -> dict[str, Decimal]:
    total = _q(total)
    part = _q(total / Decimal("4"))
    return {
        "q1": part,
        "q2": part,
        "q3": part,
        "q4": _q(total - part - part - part),
    }
