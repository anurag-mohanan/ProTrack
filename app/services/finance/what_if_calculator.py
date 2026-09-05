"""Transparent business what-if calculator — mirrors frontend/src/utils/financeWhatIf.ts."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _r2(n: float | Decimal | int) -> float:
    return float(Decimal(str(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _n(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
        return n if n == n else default
    except (TypeError, ValueError):
        return default


def compute_what_if(inputs: dict[str, Any]) -> dict[str, Any]:
    headcount = max(
        0.0,
        _n(inputs.get("headcount"))
        + _n(inputs.get("planned_hires"))
        - _n(inputs.get("expected_attrition")),
    )
    available = _r2(
        _n(inputs.get("working_days")) * _n(inputs.get("hours_per_day")) * headcount
    )
    productive = _r2(available * (_n(inputs.get("utilization_percent")) / 100.0))
    use_pipeline = bool(inputs.get("use_pipeline"))
    if use_pipeline:
        expected_revenue = _r2(
            _n(inputs.get("pipeline_value")) * (_n(inputs.get("win_rate_percent")) / 100.0)
        )
        avg = _n(inputs.get("average_project_value"))
        expected_projects_won = _r2(expected_revenue / avg) if avg > 0 else 0.0
    else:
        expected_projects_won = _n(inputs.get("expected_projects"))
        expected_revenue = _r2(
            expected_projects_won * _n(inputs.get("average_project_value"))
        )
    required_hours = _r2(expected_projects_won * _n(inputs.get("average_hours_per_project")))
    labor = _r2(productive * _n(inputs.get("average_cost_per_hour")))
    other = _r2(
        _n(inputs.get("other_costs")) * (1.0 + _n(inputs.get("cost_increase_percent")) / 100.0)
    )
    total_cost = _r2(labor + other)
    profit = _r2(expected_revenue - total_cost)
    margin = _r2((profit / expected_revenue) * 100.0) if expected_revenue > 0 else 0.0
    capacity_gap = _r2(productive - required_hours)
    productive_per_person = (
        productive / headcount
        if headcount > 0
        else _n(inputs.get("working_days"))
        * _n(inputs.get("hours_per_day"))
        * (_n(inputs.get("utilization_percent")) / 100.0)
    )
    headcount_required = (
        _r2(required_hours / productive_per_person) if productive_per_person > 0 else 0.0
    )
    contribution = (
        (expected_revenue - labor) / expected_revenue if expected_revenue > 0 else 0.0
    )
    break_even_revenue = _r2(other / contribution) if contribution > 0 else 0.0
    avg_val = _n(inputs.get("average_project_value"))
    break_even_projects = _r2(break_even_revenue / avg_val) if avg_val > 0 else 0.0
    warnings: list[str] = []
    if capacity_gap < 0:
        warnings.append(
            f"Required project hours ({required_hours}) exceed productive capacity ({productive})."
        )
    if headcount_required > headcount + 0.1:
        warnings.append(
            f"Workload implies about {headcount_required} people; scenario headcount is {headcount}."
        )
    if _n(inputs.get("utilization_percent")) > 95:
        warnings.append("Utilization above 95% is unusually high.")
    if margin < _n(inputs.get("margin_target_percent")):
        warnings.append(
            f"Gross margin {margin}% is below the {_n(inputs.get('margin_target_percent'))}% target."
        )
    if use_pipeline and _n(inputs.get("pipeline_value")) <= 0:
        warnings.append("Pipeline mode is on but pipeline value is zero.")

    realization = min(100.0, max(0.0, _n(inputs.get("collections_realization_percent"), 80.0)))
    expected_collections = _r2(expected_revenue * (realization / 100.0))
    cash_in = _r2(expected_collections + _n(inputs.get("investment_income_monthly")))
    cash_out = _r2(
        total_cost
        + _n(inputs.get("extra_loan_emi_monthly"))
        + _n(inputs.get("od_interest_monthly"))
        + _n(inputs.get("one_time_capex_cash"))
    )
    net_cash = _r2(cash_in - cash_out)
    opening_cash = _n(inputs.get("opening_cash"))
    ending_cash = _r2(opening_cash + net_cash)
    runway_months: float | None
    if opening_cash <= 0 and _n(inputs.get("minimum_cash_reserve")) <= 0:
        cash_status = "missing_opening_cash"
        runway_months = None
        warnings.append(
            "Opening cash is zero — set a Treasury cash position or enter opening cash for runway."
        )
    elif net_cash >= 0:
        cash_status = "cash_generative"
        runway_months = None
    else:
        cash_status = "burning"
        runway_months = _r2(opening_cash / abs(net_cash)) if opening_cash > 0 else 0.0
        if runway_months is not None and runway_months < 3:
            warnings.append(
                f"Projected cash runway is only {runway_months} months at this net burn."
            )

    if ending_cash < _n(inputs.get("minimum_cash_reserve")):
        warnings.append(
            f"Ending cash {ending_cash} falls below the minimum reserve "
            f"{_n(inputs.get('minimum_cash_reserve'))}."
        )
    if _n(inputs.get("extra_loan_emi_monthly")) > cash_in * 0.4 and cash_in > 0:
        warnings.append("Loan repayments are high relative to expected collections.")

    return {
        "scenario_headcount": headcount,
        "available_hours": available,
        "productive_hours": productive,
        "expected_projects_won": expected_projects_won,
        "expected_revenue": expected_revenue,
        "required_project_hours": required_hours,
        "labor_cost": labor,
        "other_costs_adjusted": other,
        "total_cost": total_cost,
        "gross_profit": profit,
        "gross_margin_percent": margin,
        "capacity_gap": capacity_gap,
        "headcount_required": headcount_required,
        "break_even_revenue": break_even_revenue,
        "break_even_projects": break_even_projects,
        "revenue_per_employee": _r2(expected_revenue / headcount) if headcount > 0 else 0.0,
        "profit_per_employee": _r2(profit / headcount) if headcount > 0 else 0.0,
        "expected_collections": expected_collections,
        "cash_inflows": cash_in,
        "cash_outflows": cash_out,
        "net_cash_flow": net_cash,
        "ending_cash": ending_cash,
        "scenario_runway_months": runway_months,
        "cash_status": cash_status,
        "warnings": warnings,
    }
