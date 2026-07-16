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
