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
        "warnings": warnings,
    }
