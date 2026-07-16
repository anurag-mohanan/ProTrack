"""FP&A Phase A — plan vs actual, seed from live, scenario clone."""

from datetime import date
from decimal import Decimal

from app.services.finance.plan_vs_actual_service import fy_months_elapsed
from tests.conftest import DEFAULT_PASSWORD


def _auth(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_fy_months_elapsed_bounds():
    assert fy_months_elapsed(date(2026, 4, 1), date(2027, 3, 31), date(2026, 3, 15)) == 0
    assert fy_months_elapsed(date(2026, 4, 1), date(2027, 3, 31), date(2026, 4, 1)) == 1
    assert fy_months_elapsed(date(2026, 4, 1), date(2027, 3, 31), date(2026, 7, 15)) == 4
    assert fy_months_elapsed(date(2026, 4, 1), date(2027, 3, 31), date(2027, 4, 1)) == 12


def test_plan_vs_actual_and_seed_and_clone(client, auth_headers):
    create = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY PVA Base",
            "fiscal_year_start_year": 2032,
            "tax_percent": 30,
            "provision_percent": 20,
        },
    )
    assert create.status_code == 201, create.text
    plan = create.json()
    plan_id = plan["id"]
    sales_line = next(row for row in plan["lines"] if row["code"] == "abc_mold")

    updated = client.put(
        f"/api/v1/finance/plans/{plan_id}/lines/{sales_line['id']}",
        headers=auth_headers,
        json={"q1": "1200", "q2": "1200", "q3": "1200", "q4": "1200"},
    )
    assert updated.status_code == 200, updated.text

    pva = client.get(
        f"/api/v1/finance/plans/{plan_id}/plan-vs-actual",
        headers=auth_headers,
    )
    assert pva.status_code == 200, pva.text
    body = pva.json()
    assert body["fiscal_year_label"] == "2032-33"
    assert 0 <= body["months_elapsed"] <= 12
    assert "rolling_forecast_gain_loss_fy" in body
    assert Decimal(body["plan_sales_fy"]) == Decimal("4800.00")

    seed = client.post(
        f"/api/v1/finance/plans/{plan_id}/seed-from-live",
        headers=auth_headers,
    )
    assert seed.status_code == 200, seed.text
    seeded = seed.json()
    wages = next(row for row in seeded["lines"] if row["code"] == "wages")
    overhead = next(row for row in seeded["lines"] if row["code"] == "overhead")
    assert Decimal(str(wages["q1"])) >= 0
    assert Decimal(str(overhead["q1"])) >= 0
    # Sales customer line untouched by seed
    sales = next(row for row in seeded["lines"] if row["code"] == "abc_mold")
    assert Decimal(str(sales["q1"])) == Decimal("1200")

    clone = client.post(
        f"/api/v1/finance/plans/{plan_id}/clone",
        headers=auth_headers,
        json={"scenario_name": "Stretch"},
    )
    assert clone.status_code == 201, clone.text
    cloned = clone.json()
    assert cloned["fiscal_year_label"] == "2032-33"
    assert "Stretch" in cloned["name"]
    assert cloned["id"] != plan_id

    # Same FY allowed for scenario; duplicate scenario name rejected
    again = client.post(
        f"/api/v1/finance/plans/{plan_id}/clone",
        headers=auth_headers,
        json={"scenario_name": "Stretch"},
    )
    assert again.status_code == 400


def test_plan_vs_actual_requires_auth(client):
    response = client.get("/api/v1/finance/plans/00000000-0000-0000-0000-000000000001/plan-vs-actual")
    assert response.status_code in (401, 403)
