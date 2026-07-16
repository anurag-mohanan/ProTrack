"""Plan vs Actual + rolling forecast for annual finance plans (FP&A Phase A)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import CostNature, ExpensePaidBy
from app.models.finance import FinancePlan
from app.services.finance import annual_plan_service
from app.services.finance.annual_plan_service import MONTH_FIELDS, QUARTER_FIELDS


def _q(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fy_months_elapsed(fy_start: date, fy_end: date, as_of: date | None = None) -> int:
    """Inclusive count of FY months from fy_start through as_of (0–12)."""
    today = as_of or date.today()
    if today < fy_start:
        return 0
    if today > fy_end:
        return 12
    return (today.year - fy_start.year) * 12 + (today.month - fy_start.month) + 1


def _sum_first_n_months(month_totals: dict[str, Decimal], n: int) -> Decimal:
    if n <= 0:
        return Decimal("0.00")
    fields = MONTH_FIELDS[: min(n, 12)]
    return _q(sum((month_totals.get(field) or Decimal("0")) for field in fields))


def _monthly_run_rates(db: Session) -> tuple[Decimal, Decimal]:
    """Match Overview convention: sales = quotes + fees; expenses = salary + Prosohm opex."""
    from app.services.finance.dashboard_service import (
        _expense_sum,
        _quote_revenue_cost,
        _salary_for_users,
        _team_fee_monthly,
    )

    today = date.today()
    revenue, _ = _quote_revenue_cost(db, team_id=None)
    fee = _team_fee_monthly(db, team_id=None, today=today)
    salary = _salary_for_users(db, None, as_of=today)
    opex = _expense_sum(
        db, team_id=None, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex, as_of=today
    )
    sales_monthly = _q(revenue + fee)
    expenses_monthly = _q(salary + opex)
    return sales_monthly, expenses_monthly


def compute_plan_vs_actual(
    db: Session, plan: FinancePlan, *, as_of: date | None = None
) -> dict:
    today = as_of or date.today()
    n = fy_months_elapsed(plan.fy_start_date, plan.fy_end_date, today)
    summary = annual_plan_service.compute_plan_summary(plan)
    sales_months = {k: Decimal(str(v)) for k, v in summary["sales_by_month"].items()}
    expense_months = {k: Decimal(str(v)) for k, v in summary["expenses_by_month"].items()}

    plan_sales_fy = _q(Decimal(str(summary["sales_fy"])))
    plan_expenses_fy = _q(Decimal(str(summary["expenses_fy"])))
    plan_gain_fy = _q(plan_sales_fy - plan_expenses_fy)

    plan_sales_ytd = _sum_first_n_months(sales_months, n)
    plan_expenses_ytd = _sum_first_n_months(expense_months, n)
    plan_gain_ytd = _q(plan_sales_ytd - plan_expenses_ytd)

    sales_monthly, expenses_monthly = _monthly_run_rates(db)
    actual_sales_ytd = _q(sales_monthly * Decimal(n))
    actual_expenses_ytd = _q(expenses_monthly * Decimal(n))
    actual_gain_ytd = _q(actual_sales_ytd - actual_expenses_ytd)

    remaining_sales = _q(plan_sales_fy - plan_sales_ytd)
    remaining_expenses = _q(plan_expenses_fy - plan_expenses_ytd)
    forecast_sales_fy = _q(actual_sales_ytd + remaining_sales)
    forecast_expenses_fy = _q(actual_expenses_ytd + remaining_expenses)
    forecast_gain_fy = _q(forecast_sales_fy - forecast_expenses_fy)

    sales_var = _q(actual_sales_ytd - plan_sales_ytd)
    expenses_var = _q(plan_expenses_ytd - actual_expenses_ytd)  # positive = under budget
    gain_var = _q(actual_gain_ytd - plan_gain_ytd)

    def _pct(numerator: Decimal, denominator: Decimal) -> str:
        if denominator == 0:
            return "0.00"
        return str(_q(numerator / denominator * Decimal("100")))

    return {
        "plan_id": plan.id,
        "fiscal_year_label": plan.fiscal_year_label,
        "as_of": today.isoformat(),
        "months_elapsed": n,
        "months_remaining": max(0, 12 - n),
        "currency_code": plan.currency_code,
        "sales_monthly_run_rate": str(sales_monthly),
        "expenses_monthly_run_rate": str(expenses_monthly),
        "plan_sales_ytd": str(plan_sales_ytd),
        "actual_sales_ytd": str(actual_sales_ytd),
        "sales_variance_ytd": str(sales_var),
        "sales_variance_pct": _pct(sales_var, plan_sales_ytd),
        "plan_expenses_ytd": str(plan_expenses_ytd),
        "actual_expenses_ytd": str(actual_expenses_ytd),
        "expenses_variance_ytd": str(expenses_var),
        "expenses_variance_pct": _pct(expenses_var, plan_expenses_ytd),
        "plan_gain_loss_ytd": str(plan_gain_ytd),
        "actual_gain_loss_ytd": str(actual_gain_ytd),
        "gain_loss_variance_ytd": str(gain_var),
        "plan_sales_fy": str(plan_sales_fy),
        "plan_expenses_fy": str(plan_expenses_fy),
        "plan_gain_loss_fy": str(plan_gain_fy),
        "rolling_forecast_sales_fy": str(forecast_sales_fy),
        "rolling_forecast_expenses_fy": str(forecast_expenses_fy),
        "rolling_forecast_gain_loss_fy": str(forecast_gain_fy),
        "remaining_plan_sales": str(remaining_sales),
        "remaining_plan_expenses": str(remaining_expenses),
        "methodology": (
            "YTD actual = Overview monthly run-rate × months elapsed; "
            "rolling FY forecast = actual YTD + remaining plan months"
        ),
    }


def seed_plan_from_live(db: Session, plan_id: UUID) -> FinancePlan:
    """Fill wages + overhead lines from live salary and overhead pool (even quarterly split)."""
    from app.services.finance.dashboard_service import (
        _overhead_metrics,
        _salary_for_users,
    )

    plan = annual_plan_service.get_plan(db, plan_id)
    today = date.today()
    salary_monthly = _salary_for_users(db, None, as_of=today)
    overhead = _overhead_metrics(db, fy_start=plan.fy_start_date, team_id=None)
    overhead_monthly = Decimal(str(overhead.get("overhead_pool_monthly_inr") or 0))

    wages_fy = _q(salary_monthly * Decimal("12"))
    overhead_fy = _q(overhead_monthly * Decimal("12"))
    wages_q = _q(wages_fy / Decimal("4"))
    overhead_q = _q(overhead_fy / Decimal("4"))

    for line in plan.lines:
        if line.code == "wages":
            for q in QUARTER_FIELDS:
                annual_plan_service.apply_quarter_amount(line, q, wages_q)
        elif line.code == "overhead":
            for q in QUARTER_FIELDS:
                annual_plan_service.apply_quarter_amount(line, q, overhead_q)
    db.flush()
    return plan
