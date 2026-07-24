"""Period helpers and team cost-vs-revenue rollup fields for Finance Overview."""

from datetime import date
from decimal import Decimal

from app.services.finance.renewal_budget_service import (
    fy_half_date_bounds,
    fy_year_date_bounds,
    months_elapsed_in_period,
)


def test_fy_half_and_year_bounds():
    fy_start = date(2026, 4, 1)
    assert fy_half_date_bounds(date(2026, 5, 15), fy_start=fy_start) == (
        date(2026, 4, 1),
        date(2026, 9, 30),
    )
    assert fy_half_date_bounds(date(2026, 11, 1), fy_start=fy_start) == (
        date(2026, 10, 1),
        date(2027, 3, 31),
    )
    assert fy_year_date_bounds(fy_start=fy_start) == (date(2026, 4, 1), date(2027, 3, 31))
    assert months_elapsed_in_period(date(2026, 6, 10), date(2026, 4, 1), date(2026, 9, 30)) == 3


def test_dashboard_team_rows_expose_period_revenue_and_salary(client, auth_headers):
    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert "period_context" in body
    assert body["period_context"].get("months_month") == 1
    assert "half_year_revenue" in body["revenue"]
    rows = body.get("by_team") or []
    if not rows:
        return
    sample = rows[0]
    for key in (
        "salary_cost_inr",
        "other_operating_cost_inr",
        "planning_revenue_signal_inr",
        "half_year_revenue_signal_inr",
        "year_revenue_signal_inr",
        "quarter_salary_cost_inr",
        "year_operating_cost_inr",
    ):
        assert key in sample
    # Salary is part of fully loaded op cost (may be zero for empty teams).
    salary = Decimal(str(sample["salary_cost_inr"]))
    operating = Decimal(str(sample["monthly_operating_cost_inr"]))
    other = Decimal(str(sample["other_operating_cost_inr"]))
    assert operating == (salary + other).quantize(Decimal("0.01")) or operating == salary + other
