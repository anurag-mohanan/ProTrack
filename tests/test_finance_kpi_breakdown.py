"""Finance KPI breakdown drill-down API."""


def test_kpi_breakdown_overhead_opex_and_pool(client, auth_headers):
    opex = client.get(
        "/api/v1/finance/kpi-breakdown?metric=overhead_opex",
        headers=auth_headers,
    )
    assert opex.status_code == 200, opex.text
    body = opex.json()
    assert body["metric"] == "overhead_opex"
    assert "total_inr" in body
    assert isinstance(body["groups"], list)
    assert isinstance(body["empty_hints"], list)

    pool = client.get(
        "/api/v1/finance/kpi-breakdown?metric=overhead_pool",
        headers=auth_headers,
    )
    assert pool.status_code == 200, pool.text
    assert pool.json()["metric"] == "overhead_pool"
    labels = {g["label"] for g in pool.json()["groups"]}
    assert "Salaries" in labels
    assert "OpEx" in labels

    cpr = client.get(
        "/api/v1/finance/kpi-breakdown?metric=overhead_cpr",
        headers=auth_headers,
    )
    assert cpr.status_code == 200, cpr.text
    assert "billable_fte" in (cpr.json().get("meta") or {})


def test_kpi_breakdown_operating_and_unknown(client, auth_headers):
    operating = client.get(
        "/api/v1/finance/kpi-breakdown?metric=operating_cost",
        headers=auth_headers,
    )
    assert operating.status_code == 200, operating.text
    assert operating.json()["metric"] == "operating_cost"

    bad = client.get(
        "/api/v1/finance/kpi-breakdown?metric=not_a_metric",
        headers=auth_headers,
    )
    assert bad.status_code == 400


def test_kpi_breakdown_revenue_uses_contributor_bands_not_high_spend(client, auth_headers):
    revenue = client.get(
        "/api/v1/finance/kpi-breakdown?metric=revenue_quarter",
        headers=auth_headers,
    )
    assert revenue.status_code == 200, revenue.text
    body = revenue.json()
    bands = {
        line["band"]
        for group in body["groups"]
        for line in group["lines"]
    }
    assert "high" not in bands
    if bands:
        assert bands.issubset({"leading", "normal", "thin"})

    fees = client.get(
        "/api/v1/finance/kpi-breakdown?metric=team_fees",
        headers=auth_headers,
    )
    assert fees.status_code == 200, fees.text
    fee_bands = {
        line["band"]
        for group in fees.json()["groups"]
        for line in group["lines"]
    }
    assert "high" not in fee_bands


def test_finance_dashboard_by_team_includes_pnl_fields(client, auth_headers):
    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    rows = dash.json().get("by_team") or []
    if not rows:
        return
    sample = rows[0]
    for key in (
        "gross_profit_inr",
        "net_profit_inr",
        "gross_margin_percent",
        "net_margin_percent",
        "quarterly_revenue_signal_inr",
        "is_overhead_home",
    ):
        assert key in sample
