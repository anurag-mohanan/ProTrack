"""Budgets & Reports cockpit API tests."""

from decimal import Decimal


def test_budget_cockpit_and_sync_spent(client, auth_headers):
    create = client.post(
        "/api/v1/finance/budgets",
        headers=auth_headers,
        json={
            "name": "Cockpit Test Budget",
            "scope_type": "department",
            "allocated": "120000",
            "currency_code": "INR",
            "fiscal_year": 2034,
            "spent": "0",
            "forecast": "0",
        },
    )
    assert create.status_code == 201, create.text
    budget = create.json()
    budget_id = budget["id"]
    assert Decimal(str(budget["allocated"])) == Decimal("120000.00")
    assert Decimal(str(budget["q1_allocated"])) > 0

    cockpit = client.get("/api/v1/finance/budgets/cockpit", headers=auth_headers)
    assert cockpit.status_code == 200, cockpit.text
    body = cockpit.json()
    assert body["totals"]["budget_count"] >= 1
    assert "quarters" in body
    assert len(body["insights"]) >= 1
    names = {row["name"] for row in body["budgets"]}
    assert "Cockpit Test Budget" in names

    sync = client.post(
        f"/api/v1/finance/budgets/{budget_id}/sync-spent",
        headers=auth_headers,
    )
    assert sync.status_code == 200, sync.text
    synced = sync.json()
    assert Decimal(str(synced["spent"])) >= 0
    assert Decimal(str(synced["remaining"])) == Decimal(str(synced["allocated"])) - Decimal(
        str(synced["spent"])
    )

    approve = client.patch(
        f"/api/v1/finance/budgets/{budget_id}/status",
        headers=auth_headers,
        json={"approval_status": "approved"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["approval_status"] == "approved"


def test_budget_cockpit_requires_auth(client):
    response = client.get("/api/v1/finance/budgets/cockpit")
    assert response.status_code in (401, 403)
