"""What-if calculator mirrors frontend financeWhatIf.ts."""

from app.services.finance.what_if_calculator import compute_what_if


def test_what_if_basic_profit_and_capacity():
    result = compute_what_if(
        {
            "expected_projects": 10,
            "average_project_value": 100000,
            "win_rate_percent": 70,
            "pipeline_value": 0,
            "use_pipeline": False,
            "headcount": 10,
            "planned_hires": 0,
            "expected_attrition": 0,
            "working_days": 21,
            "hours_per_day": 8,
            "utilization_percent": 80,
            "average_cost_per_hour": 1000,
            "other_costs": 50000,
            "cost_increase_percent": 0,
            "average_hours_per_project": 100,
            "margin_target_percent": 25,
        }
    )
    # 21*8*10 = 1680 available; *80% = 1344 productive
    assert result["available_hours"] == 1680.0
    assert result["productive_hours"] == 1344.0
    assert result["expected_revenue"] == 1000000.0
    assert result["labor_cost"] == 1344000.0
    assert result["total_cost"] == 1394000.0
    assert result["gross_profit"] == -394000.0
    assert result["required_project_hours"] == 1000.0
    assert result["capacity_gap"] == 344.0
    assert any("margin" in w.lower() for w in result["warnings"])


def test_what_if_pipeline_mode():
    result = compute_what_if(
        {
            "expected_projects": 0,
            "average_project_value": 50000,
            "win_rate_percent": 50,
            "pipeline_value": 400000,
            "use_pipeline": True,
            "headcount": 5,
            "planned_hires": 1,
            "expected_attrition": 0,
            "working_days": 20,
            "hours_per_day": 8,
            "utilization_percent": 75,
            "average_cost_per_hour": 500,
            "other_costs": 10000,
            "cost_increase_percent": 10,
            "average_hours_per_project": 80,
            "margin_target_percent": 10,
        }
    )
    assert result["scenario_headcount"] == 6.0
    assert result["expected_revenue"] == 200000.0
    assert result["other_costs_adjusted"] == 11000.0
