"""Team P&L allocates HQ overhead (CPR × billable FTE) into delivery Op Cost."""

from __future__ import annotations

from decimal import Decimal


def test_delivery_team_op_cost_includes_allocated_overhead(client, auth_headers):
    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    overhead = body["overhead"]
    cpr = Decimal(str(overhead.get("overhead_cost_per_resource_inr") or 0))

    delivery = [row for row in (body.get("by_team") or []) if not row.get("is_overhead_home")]
    if not delivery:
        return

    for row in delivery:
        allocated = Decimal(str(row.get("allocated_overhead_inr") or 0))
        direct = Decimal(str(row.get("direct_operating_cost_inr") or 0))
        operating = Decimal(str(row["monthly_operating_cost_inr"]))
        assert operating == (direct + allocated).quantize(Decimal("0.01"))

        n = int(row.get("billable_resource_count") or 0)
        expected = (cpr * Decimal(n)).quantize(Decimal("0.01")) if cpr > 0 and n > 0 else Decimal("0.00")
        assert allocated == expected

        # Net uses fully loaded Op Cost (includes allocated overhead).
        revenue = Decimal(str(row["planning_revenue_signal_inr"]))
        estimated = Decimal(str(row["estimated_cost_inr"]))
        net = Decimal(str(row["net_profit_inr"]))
        assert net == (revenue - estimated - operating).quantize(Decimal("0.01"))


def test_overhead_home_does_not_receive_cpr_allocation(client, auth_headers):
    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    homes = [row for row in (dash.get("by_team") or []) if row.get("is_overhead_home")]
    for row in homes:
        assert Decimal(str(row.get("allocated_overhead_inr") or 0)) == Decimal("0.00")
        assert Decimal(str(row["monthly_operating_cost_inr"])) == Decimal(
            str(row.get("direct_operating_cost_inr") or row["monthly_operating_cost_inr"])
        )
