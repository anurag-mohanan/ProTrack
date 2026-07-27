"""Pure finance scenario calculator — mirrors frontend/src/utils/financeScenarios.ts."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _r2(n: float | Decimal | int) -> Decimal:
    return Decimal(str(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def yearly_to_monthly(amount: float | Decimal) -> Decimal:
    return _r2(Decimal(str(amount)) / Decimal("12"))


def after_tax_net(pre_tax: float | Decimal, tax_percent: float | Decimal) -> Decimal:
    factor = (Decimal("100") - Decimal(str(tax_percent))) / Decimal("100")
    return _r2(Decimal(str(pre_tax)) * factor)


def simulated_cpr(pool: float | Decimal, billable_fte: float | Decimal) -> Decimal:
    if Decimal(str(billable_fte)) <= 0:
        return Decimal("0.00")
    return _r2(Decimal(str(pool)) / Decimal(str(billable_fte)))


def _num(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
        return n if n == n else default  # NaN guard
    except (TypeError, ValueError):
        return default


def _monthly_amount(amount: float, yearly: bool) -> float:
    if yearly:
        return float(yearly_to_monthly(amount))
    return amount


def normalize_fixed_fee_monthly(amount: float, period: str) -> float:
    period_key = (period or "monthly").lower()
    if period_key == "quarterly":
        return float(_r2(Decimal(str(amount)) / Decimal("3")))
    if period_key == "annual":
        return float(yearly_to_monthly(amount))
    return amount


def revenue_fx_multiplier(row: dict[str, Any]) -> float:
    rate = _num(row.get("revenue_fx_rate_to_base"), 0.0)
    if rate > 0:
        return rate
    code = str(row.get("revenue_currency_code") or "INR").upper()
    return 1.0 if code == "INR" else 1.0


def new_team_monthly_revenue_native(row: dict[str, Any]) -> float:
    code = str(row.get("working_model_code") or "project_based").lower()
    if code == "overheads":
        return 0.0
    mode = str(row.get("revenue_mode") or "expected_revenue").lower()
    if mode == "fixed_fee":
        return normalize_fixed_fee_monthly(
            _num(row.get("fixed_fee_amount")),
            str(row.get("fixed_fee_period") or "monthly"),
        )
    if mode == "pipeline":
        pipeline = _num(row.get("pipeline_monthly"))
        win_rate = _num(row.get("win_rate_percent"), 100.0)
        return float(_r2(Decimal(str(pipeline)) * Decimal(str(win_rate)) / Decimal("100")))
    explicit = _num(row.get("expected_monthly_revenue"))
    if explicit > 0:
        return explicit
    return normalize_fixed_fee_monthly(
        _num(row.get("fixed_fee_amount")),
        str(row.get("fixed_fee_period") or "monthly"),
    )


def new_team_monthly_revenue(row: dict[str, Any]) -> float:
    """Monthly revenue in company base currency (INR after FX)."""
    return float(
        _r2(Decimal(str(new_team_monthly_revenue_native(row))) * Decimal(str(revenue_fx_multiplier(row))))
    )


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "overhead": {
            "extra_hq_salary_monthly": 0,
            "extra_shared_opex_monthly": 0,
            "extra_shared_capex_monthly": 0,
            "opex_yearly": False,
            "capex_yearly": False,
        },
        "new_teams": [],
        "management_hires": [],
        "facility_lines": [],
        "expansion": {"hires": [], "software": []},
        "opex_yearly": False,
        "capex_yearly": False,
    }


def _hire_deltas(hires: list[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    hq = Decimal("0")
    by_team: dict[str, Decimal] = {}
    for row in hires:
        n = max(0, _num(row.get("headcount")))
        sal = max(0, _num(row.get("salary_monthly_each")))
        amount = Decimal(str(n * sal))
        if str(row.get("attribution") or "team") == "hq":
            hq += amount
        else:
            team_id = str(row.get("team_id") or "")
            if team_id:
                by_team[team_id] = by_team.get(team_id, Decimal("0")) + amount
    return float(_r2(hq)), {k: float(_r2(v)) for k, v in by_team.items()}


def _team_hire_salary_delta(hires: list[dict[str, Any]], team_id: str) -> float:
    _, by_team = _hire_deltas(hires)
    return by_team.get(team_id, 0.0)


def _hq_hire_salary_delta(hires: list[dict[str, Any]]) -> float:
    hq, _ = _hire_deltas(hires)
    return hq


def _team_software_delta(software: list[dict[str, Any]], team_id: str) -> float:
    total = Decimal("0")
    for row in software:
        if str(row.get("attribution") or "team") == "hq":
            continue
        if str(row.get("team_id")) != team_id:
            continue
        amt = max(0, _num(row.get("amount_monthly")))
        if row.get("yearly"):
            amt = float(yearly_to_monthly(amt))
        total += Decimal(str(amt))
    return float(_r2(total))


def _team_extra_billable_fte(hires: list[dict[str, Any]], team_id: str) -> float:
    total = 0.0
    for row in hires:
        if str(row.get("team_id")) != team_id or not row.get("billable"):
            continue
        if str(row.get("attribution") or "team") == "hq":
            continue
        total += max(0, _num(row.get("headcount")))
    return total


def _hq_software_deltas(software: list[dict[str, Any]]) -> tuple[float, float]:
    opex = Decimal("0")
    capex = Decimal("0")
    for row in software:
        if str(row.get("attribution") or "team") != "hq":
            continue
        amt = max(0, _num(row.get("amount_monthly")))
        if row.get("yearly"):
            amt = float(yearly_to_monthly(amt))
        kind = str(row.get("expense_kind") or "opex").lower()
        if kind == "capex":
            capex += Decimal(str(amt))
        else:
            opex += Decimal(str(amt))
    return float(_r2(opex)), float(_r2(capex))


def _management_deltas(
    rows: list[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    hq = Decimal("0")
    by_team: dict[str, Decimal] = {}
    for row in rows:
        n = max(0, _num(row.get("headcount")))
        sal = max(0, _num(row.get("salary_monthly_each")))
        amount = Decimal(str(n * sal))
        if str(row.get("attribution") or "hq") == "hq":
            hq += amount
        else:
            team_id = str(row.get("team_id") or "")
            if team_id:
                by_team[team_id] = by_team.get(team_id, Decimal("0")) + amount
    return float(_r2(hq)), {k: float(_r2(v)) for k, v in by_team.items()}


def _facility_deltas(
    rows: list[dict[str, Any]],
) -> tuple[float, float, dict[str, float]]:
    hq_opex = Decimal("0")
    hq_capex = Decimal("0")
    by_team: dict[str, Decimal] = {}
    for row in rows:
        amt = max(0, _num(row.get("amount_monthly")))
        if row.get("yearly"):
            amt = float(yearly_to_monthly(amt))
        category = str(row.get("category") or "other").lower()
        is_capex = category == "capex"
        if str(row.get("attribution") or "hq") == "hq":
            if is_capex:
                hq_capex += Decimal(str(amt))
            else:
                hq_opex += Decimal(str(amt))
        else:
            team_id = str(row.get("team_id") or "")
            if team_id:
                by_team[team_id] = by_team.get(team_id, Decimal("0")) + Decimal(str(amt))
    return (
        float(_r2(hq_opex)),
        float(_r2(hq_capex)),
        {k: float(_r2(v)) for k, v in by_team.items()},
    )


def _new_team_opex_monthly(row: dict[str, Any]) -> float:
    lines = list(row.get("opex_lines") or [])
    total = Decimal("0")
    for line in lines:
        total += Decimal(str(max(0, _num(line.get("amount_monthly")))))
    if total > 0:
        return float(_r2(total))
    return _num(row.get("expected_monthly_cost"))


def compute_scenario(baseline: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    overhead = payload.get("overhead") or {}
    expansion = payload.get("expansion") or {}
    hires = list(expansion.get("hires") or [])
    software = list(expansion.get("software") or [])
    new_teams = list(payload.get("new_teams") or [])
    mgmt_rows = list(payload.get("management_hires") or [])
    facility_rows = list(payload.get("facility_lines") or [])

    opex_yearly = bool(payload.get("opex_yearly") or overhead.get("opex_yearly"))
    capex_yearly = bool(payload.get("capex_yearly") or overhead.get("capex_yearly"))

    extra_opex = _monthly_amount(
        _num(overhead.get("extra_shared_opex_monthly")),
        opex_yearly,
    )
    extra_capex = _monthly_amount(
        _num(overhead.get("extra_shared_capex_monthly")),
        capex_yearly,
    )

    hq_mgmt, mgmt_by_team = _management_deltas(mgmt_rows)
    fac_hq_opex, fac_hq_capex, fac_by_team = _facility_deltas(facility_rows)
    sw_hq_opex, sw_hq_capex = _hq_software_deltas(software)
    hq_hires = _hq_hire_salary_delta(hires)

    extra_salary = _num(overhead.get("extra_hq_salary_monthly"))
    scenario_additions = float(
        _r2(
            Decimal(str(extra_salary))
            + Decimal(str(extra_opex + fac_hq_opex + sw_hq_opex))
            + Decimal(str(extra_capex + fac_hq_capex + sw_hq_capex))
            + Decimal(str(hq_mgmt + hq_hires))
        )
    )

    pool = float(
        _r2(
            Decimal(str(_num(baseline.get("overhead_pool"))))
            + Decimal(str(scenario_additions))
        )
    )

    extra_fte = sum(
        max(0, _num(row.get("headcount")))
        for row in hires
        if row.get("billable") and str(row.get("attribution") or "team") != "hq"
    )
    for row in new_teams:
        if row.get("billable"):
            extra_fte += max(0, _num(row.get("delivery_headcount")))

    fte = _num(baseline.get("billable_fte")) + extra_fte
    cpr = float(simulated_cpr(pool, fte))
    tax = _num(baseline.get("corporate_tax_percent"), 30.0)

    company_direct_delta = Decimal("0")
    teams_out: list[dict[str, Any]] = []

    for team in baseline.get("teams") or []:
        if team.get("is_overhead_home"):
            continue
        team_id = str(team.get("team_id"))
        hire_sal = _team_hire_salary_delta(hires, team_id)
        soft = _team_software_delta(software, team_id)
        mgmt = mgmt_by_team.get(team_id, 0.0)
        fac = fac_by_team.get(team_id, 0.0)
        simulated_direct = float(
            _r2(
                Decimal(str(_num(team.get("direct_operating"))))
                + Decimal(str(hire_sal + soft + mgmt + fac))
            )
        )
        extra_team_fte = _team_extra_billable_fte(hires, team_id)
        simulated_fte = _num(team.get("billable_fte")) + extra_team_fte
        simulated_allocated = float(_r2(Decimal(str(cpr)) * Decimal(str(simulated_fte))))
        simulated_operating = float(_r2(Decimal(str(simulated_direct + simulated_allocated))))
        revenue = _num(team.get("revenue"))
        estimated_cost = _num(team.get("estimated_cost"))
        simulated_net = float(_r2(Decimal(str(revenue - estimated_cost - simulated_operating))))
        simulated_after_tax = float(after_tax_net(simulated_net, tax))
        current_operating = _num(team.get("operating"))
        delta_op = float(_r2(Decimal(str(simulated_operating - current_operating))))
        break_even = simulated_operating
        break_even_after_tax = float(_r2(Decimal(str(simulated_operating + estimated_cost))))

        company_direct_delta += Decimal(str(hire_sal + soft + mgmt + fac))

        teams_out.append(
            {
                "team_id": team_id,
                "team_name": team.get("team_name"),
                "revenue": revenue,
                "current_net": _num(team.get("net_profit")),
                "current_operating": current_operating,
                "simulated_direct": simulated_direct,
                "simulated_allocated": simulated_allocated,
                "simulated_operating": simulated_operating,
                "simulated_net": simulated_net,
                "simulated_after_tax": simulated_after_tax,
                "delta_operating": delta_op,
                "break_even_revenue": break_even,
                "break_even_revenue_after_tax": break_even_after_tax,
                "is_new_team": False,
            }
        )

    for row in new_teams:
        team_id = str(row.get("id"))
        headcount = max(0, _num(row.get("delivery_headcount")))
        salary_each = max(0, _num(row.get("salary_monthly_each")))
        direct = float(_r2(Decimal(str(headcount * salary_each))))
        opex = _new_team_opex_monthly(row)
        soft = _team_software_delta(software, team_id)
        mgmt = mgmt_by_team.get(team_id, 0.0)
        fac = fac_by_team.get(team_id, 0.0)
        simulated_direct = float(_r2(Decimal(str(direct + opex + soft + mgmt + fac))))
        simulated_fte = headcount if row.get("billable") else 0.0
        simulated_allocated = float(_r2(Decimal(str(cpr)) * Decimal(str(simulated_fte))))
        simulated_operating = float(_r2(Decimal(str(simulated_direct + simulated_allocated))))
        revenue = new_team_monthly_revenue(row)
        simulated_net = float(_r2(Decimal(str(revenue - simulated_operating))))
        simulated_after_tax = float(after_tax_net(simulated_net, tax))
        break_even = simulated_operating
        break_even_after_tax = simulated_operating

        company_direct_delta += Decimal(str(direct + opex + soft + mgmt + fac))

        teams_out.append(
            {
                "team_id": team_id,
                "team_name": row.get("name") or "New team",
                "revenue": revenue,
                "current_net": 0.0,
                "current_operating": 0.0,
                "simulated_direct": simulated_direct,
                "simulated_allocated": simulated_allocated,
                "simulated_operating": simulated_operating,
                "simulated_net": simulated_net,
                "simulated_after_tax": simulated_after_tax,
                "delta_operating": simulated_operating,
                "break_even_revenue": break_even,
                "break_even_revenue_after_tax": break_even_after_tax,
                "is_new_team": True,
            }
        )

    baseline_pool = _num(baseline.get("overhead_pool"))
    company_base = _num(baseline.get("company_operating"))
    company_sim = float(_r2(company_direct_delta + Decimal(str(company_base + (pool - baseline_pool)))))

    return {
        "simulated_pool": pool,
        "delta_pool": float(_r2(Decimal(str(pool - baseline_pool)))),
        "simulated_billable_fte": fte,
        "simulated_cpr": cpr,
        "delta_cpr": float(_r2(Decimal(str(cpr - _num(baseline.get("cpr")))))),
        "company_direct_delta": float(_r2(company_direct_delta)),
        "company_simulated_operating": company_sim,
        "delta_company_operating": float(_r2(Decimal(str(company_sim - company_base)))),
        "shared_overhead": {
            "live_management_salary": _num(
                (baseline.get("overhead_breakdown") or {}).get("management_salary"),
                _num(baseline.get("overhead_pool")),
            ),
            "live_shared_opex": _num((baseline.get("overhead_breakdown") or {}).get("shared_opex")),
            "live_shared_capex": _num((baseline.get("overhead_breakdown") or {}).get("shared_capex")),
            "live_pool": baseline_pool,
            "scenario_extra_salary": extra_salary,
            "scenario_extra_opex": extra_opex,
            "scenario_extra_capex": extra_capex,
            "scenario_management_hq": hq_mgmt,
            "scenario_hires_hq": hq_hires,
            "scenario_facility_hq_opex": fac_hq_opex,
            "scenario_facility_hq_capex": fac_hq_capex,
            "scenario_software_hq_opex": sw_hq_opex,
            "scenario_software_hq_capex": sw_hq_capex,
            "scenario_additions_total": scenario_additions,
            "simulated_pool": pool,
        },
        "teams": teams_out,
    }


def baseline_from_dashboard(dashboard: dict[str, Any]) -> dict[str, Any]:
    teams = []
    for row in dashboard.get("by_team") or []:
        revenue = _num(row.get("monthly_revenue_signal_inr")) or _num(
            row.get("planning_revenue_signal_inr")
        )
        teams.append(
            {
                "team_id": str(row.get("team_id")),
                "team_name": row.get("team_name"),
                "is_overhead_home": bool(row.get("is_overhead_home")),
                "revenue": revenue,
                "direct_operating": _num(row.get("direct_operating_cost_inr")),
                "allocated_overhead": _num(row.get("allocated_overhead_inr")),
                "operating": _num(row.get("monthly_operating_cost_inr")),
                "net_profit": _num(row.get("net_profit_inr")),
                "billable_fte": _num(row.get("billable_resource_count")),
                "estimated_cost": _num(row.get("month_estimated_cost_inr"))
                or _num(row.get("estimated_cost_inr")),
            }
        )

    overhead = dashboard.get("overhead") or {}
    cost = dashboard.get("cost") or {}
    profitability = dashboard.get("profitability") or {}

    return {
        "overhead_pool": _num(overhead.get("overhead_pool_monthly_inr"))
        or _num(cost.get("overhead_pool_monthly_inr")),
        "billable_fte": _num(overhead.get("billable_resource_count")),
        "cpr": _num(overhead.get("overhead_cost_per_resource_inr"))
        or _num(cost.get("overhead_cost_per_resource_inr")),
        "company_operating": _num(cost.get("monthly_operating_cost")),
        "corporate_tax_percent": _num(profitability.get("corporate_tax_percent"), 30.0),
        "teams": teams,
        "overhead_breakdown": {
            "management_salary": _num(overhead.get("overhead_management_salary_inr"))
            or _num(overhead.get("overhead_salary_inr")),
            "shared_opex": _num(overhead.get("overhead_opex_inr")),
            "shared_capex": _num(overhead.get("overhead_capex_inr")),
            "management_team_name": overhead.get("management_team_name")
            or overhead.get("corporate_team_name"),
        },
    }
