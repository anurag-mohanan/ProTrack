"""Parity tests for frontend finance scenario calculator formulas.

Mirrors frontend/src/utils/financeScenarios.ts — keep in sync when changing math.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _r2(n: float | Decimal) -> Decimal:
    return Decimal(str(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def yearly_to_monthly(amount: float) -> Decimal:
    return _r2(Decimal(str(amount)) / Decimal("12"))


def after_tax_net(pre_tax: float, tax_percent: float) -> Decimal:
    factor = (Decimal("100") - Decimal(str(tax_percent))) / Decimal("100")
    return _r2(Decimal(str(pre_tax)) * factor)


def simulated_cpr(pool: float, billable_fte: float) -> Decimal:
    if billable_fte <= 0:
        return Decimal("0.00")
    return _r2(Decimal(str(pool)) / Decimal(str(billable_fte)))


def test_yearly_to_monthly():
    assert yearly_to_monthly(120000) == Decimal("10000.00")
    assert yearly_to_monthly(0) == Decimal("0.00")


def test_cpr_with_added_fte():
    pool = 100000.0
    assert simulated_cpr(pool, 10) == Decimal("10000.00")
    # Add 2 billable FTE → CPR drops
    assert simulated_cpr(pool, 12) == Decimal("8333.33")


def test_allocated_oh_and_break_even():
    cpr = float(simulated_cpr(120000, 10))  # 12000
    team_fte = 3
    allocated = _r2(cpr * team_fte)
    assert allocated == Decimal("36000.00")

    direct = 80000.0
    operating = float(_r2(direct + float(allocated)))
    assert _r2(operating) == Decimal("116000.00")
    # Break-even revenue ≈ fully loaded Op Cost (pre-tax)
    assert _r2(operating) == Decimal("116000.00")


def test_after_tax_net_30_percent():
    assert after_tax_net(100000, 30) == Decimal("70000.00")
    assert after_tax_net(100000, 0) == Decimal("100000.00")


def test_pool_delta_and_company_op_delta():
    baseline_pool = 50000.0
    extra_salary = 10000.0
    extra_opex = 6000.0  # yearly 72000 → monthly
    assert yearly_to_monthly(72000) == Decimal("6000.00")
    pool = _r2(baseline_pool + extra_salary + float(yearly_to_monthly(72000)))
    assert pool == Decimal("66000.00")
    # Company Op Cost rises by overhead extras when no hires
    company_base = 200000.0
    company_sim = _r2(Decimal(str(company_base)) + (pool - Decimal(str(baseline_pool))))
    assert company_sim == Decimal("216000.00")


def test_new_team_revenue_fx_to_base():
    from app.services.finance.scenario_calculator import new_team_monthly_revenue

    row = {
        "working_model_code": "retainer",
        "revenue_mode": "expected_revenue",
        "expected_monthly_revenue": 10000,
        "revenue_currency_code": "USD",
        "revenue_fx_rate_to_base": 83,
    }
    assert new_team_monthly_revenue(row) == 830000.0

    inr = {
        "working_model_code": "retainer",
        "revenue_mode": "expected_revenue",
        "expected_monthly_revenue": 10000,
        "revenue_currency_code": "INR",
        "revenue_fx_rate_to_base": 1,
    }
    assert new_team_monthly_revenue(inr) == 10000.0


def test_hq_hire_salary_goes_to_shared_pool():
    from app.services.finance.scenario_calculator import compute_scenario, empty_payload

    baseline = {
        "overhead_pool": 100000.0,
        "billable_fte": 10.0,
        "cpr": 10000.0,
        "company_operating": 500000.0,
        "corporate_tax_percent": 30.0,
        "teams": [
            {
                "team_id": "t1",
                "team_name": "Design",
                "is_overhead_home": False,
                "revenue": 200000.0,
                "direct_operating": 80000.0,
                "allocated_overhead": 30000.0,
                "operating": 110000.0,
                "net_profit": 50000.0,
                "billable_fte": 3.0,
                "estimated_cost": 40000.0,
            }
        ],
    }
    payload = empty_payload()
    payload["expansion"]["hires"] = [
        {
            "id": "h1",
            "team_id": "t1",
            "headcount": 1,
            "salary_monthly_each": 50000,
            "billable": False,
            "attribution": "hq",
        }
    ]
    result = compute_scenario(baseline, payload)
    assert result["simulated_pool"] == 150000.0
    assert result["shared_overhead"]["scenario_hires_hq"] == 50000.0
    design = next(t for t in result["teams"] if t["team_id"] == "t1")
    assert design["simulated_direct"] == 80000.0


def test_new_team_retainer_revenue_and_mgmt_pool():
    from app.services.finance.scenario_calculator import compute_scenario, empty_payload

    baseline = {
        "overhead_pool": 100000.0,
        "billable_fte": 10.0,
        "cpr": 10000.0,
        "company_operating": 500000.0,
        "corporate_tax_percent": 30.0,
        "teams": [
            {
                "team_id": "t1",
                "team_name": "Design",
                "is_overhead_home": False,
                "revenue": 200000.0,
                "direct_operating": 80000.0,
                "allocated_overhead": 30000.0,
                "operating": 110000.0,
                "net_profit": 50000.0,
                "billable_fte": 3.0,
                "estimated_cost": 40000.0,
            }
        ],
    }
    payload = empty_payload()
    payload["new_teams"] = [
        {
            "id": "new_iot",
            "name": "IoT",
            "working_model_code": "retainer",
            "revenue_mode": "expected_revenue",
            "expected_monthly_revenue": 500000,
            "opex_lines": [
                {
                    "id": "ox1",
                    "category": "software_license",
                    "label": "Tools",
                    "amount_monthly": 100000,
                }
            ],
            "delivery_headcount": 5,
            "salary_monthly_each": 80000,
            "billable": True,
        }
    ]
    payload["management_hires"] = [
        {
            "id": "m1",
            "label": "Mgr",
            "headcount": 1,
            "salary_monthly_each": 150000,
            "attribution": "hq",
            "team_id": None,
        }
    ]
    result = compute_scenario(baseline, payload)
  # pool +150k mgmt
    assert result["simulated_pool"] == 250000.0
    assert result["simulated_billable_fte"] == 15.0
    new_team = next(t for t in result["teams"] if t["team_id"] == "new_iot")
    assert new_team["is_new_team"] is True
    assert new_team["revenue"] == 500000.0
    assert new_team["simulated_direct"] == 500000.0  # 5 * 80000 + 100000 opex


def test_new_team_opex_categories_in_direct():
    from app.services.finance.scenario_calculator import compute_scenario, empty_payload

    baseline = {
        "overhead_pool": 100000.0,
        "billable_fte": 10.0,
        "cpr": 10000.0,
        "company_operating": 500000.0,
        "corporate_tax_percent": 0.0,
        "teams": [],
    }
    payload = empty_payload()
    payload["new_teams"] = [
        {
            "id": "new_iot",
            "name": "IoT",
            "working_model_code": "retainer",
            "revenue_mode": "expected_revenue",
            "expected_monthly_revenue": 800000,
            "opex_lines": [
                {"id": "a", "category": "software_license", "label": "Licenses", "amount_monthly": 20000},
                {"id": "b", "category": "other", "label": "Misc", "amount_monthly": 5000},
            ],
            "delivery_headcount": 2,
            "salary_monthly_each": 100000,
            "billable": True,
        }
    ]
    result = compute_scenario(baseline, payload)
    team = result["teams"][0]
    assert team["simulated_direct"] == 225000.0  # 2*100000 + 25000
    assert team["simulated_net"] == 800000.0 - team["simulated_operating"]


def test_facility_hq_and_team_split():
    from app.services.finance.scenario_calculator import compute_scenario, empty_payload

    baseline = {
        "overhead_pool": 50000.0,
        "billable_fte": 5.0,
        "cpr": 10000.0,
        "company_operating": 200000.0,
        "corporate_tax_percent": 0.0,
        "teams": [
            {
                "team_id": "t1",
                "team_name": "Design",
                "is_overhead_home": False,
                "revenue": 100000.0,
                "direct_operating": 50000.0,
                "allocated_overhead": 20000.0,
                "operating": 70000.0,
                "net_profit": 20000.0,
                "billable_fte": 2.0,
                "estimated_cost": 10000.0,
            }
        ],
    }
    payload = empty_payload()
    payload["facility_lines"] = [
        {
            "id": "f1",
            "category": "rent",
            "label": "HQ rent",
            "amount_monthly": 20000,
            "yearly": False,
            "attribution": "hq",
            "team_id": None,
        },
        {
            "id": "f2",
            "category": "utilities",
            "label": "Team utilities",
            "amount_monthly": 5000,
            "yearly": False,
            "attribution": "team",
            "team_id": "t1",
        },
    ]
    result = compute_scenario(baseline, payload)
    assert result["simulated_pool"] == 70000.0
    design = next(t for t in result["teams"] if t["team_id"] == "t1")
    assert design["simulated_direct"] == 55000.0
