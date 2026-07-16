"""Annual Plan AI Assist — insights + apply actions."""

from decimal import Decimal

from tests.conftest import DEFAULT_PASSWORD


def _auth(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_plan_ai_insights_and_apply_actions(client, auth_headers):
    create = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY AI Studio",
            "fiscal_year_start_year": 2033,
            "tax_percent": 30,
            "provision_percent": 20,
        },
    )
    assert create.status_code == 201, create.text
    plan = create.json()
    plan_id = plan["id"]
    sales = next(row for row in plan["lines"] if row["code"] == "abc_mold")

    # Q1 only — should suggest fill empty quarters
    upd = client.put(
        f"/api/v1/finance/plans/{plan_id}/lines/{sales['id']}",
        headers=auth_headers,
        json={"q1": "900"},
    )
    assert upd.status_code == 200, upd.text

    insights = client.get(
        f"/api/v1/finance/plans/{plan_id}/ai-insights",
        headers=auth_headers,
    )
    assert insights.status_code == 200, insights.text
    body = insights.json()
    assert body["engine"] == "deterministic_rules_v1"
    assert body["confidence_percent"] >= 35
    codes = {row.get("action_code") for row in body["insights"]}
    assert "seed_from_live" in codes or "fill_empty_quarters_from_q1" in codes

    fill = client.post(
        f"/api/v1/finance/plans/{plan_id}/ai-apply",
        headers=auth_headers,
        json={"action_code": "fill_empty_quarters_from_q1"},
    )
    assert fill.status_code == 200, fill.text
    filled_sales = next(row for row in fill.json()["lines"] if row["code"] == "abc_mold")
    assert Decimal(str(filled_sales["q2"])) == Decimal("900")
    assert Decimal(str(filled_sales["q3"])) == Decimal("900")
    assert Decimal(str(filled_sales["q4"])) == Decimal("900")

    seed = client.post(
        f"/api/v1/finance/plans/{plan_id}/ai-apply",
        headers=auth_headers,
        json={"action_code": "seed_from_live"},
    )
    assert seed.status_code == 200, seed.text
    wages = next(row for row in seed.json()["lines"] if row["code"] == "wages")
    assert Decimal(str(wages["q1"])) >= 0

    uplift = client.post(
        f"/api/v1/finance/plans/{plan_id}/ai-apply",
        headers=auth_headers,
        json={"action_code": "uplift_remaining_sales"},
    )
    assert uplift.status_code == 200, uplift.text

    bad = client.post(
        f"/api/v1/finance/plans/{plan_id}/ai-apply",
        headers=auth_headers,
        json={"action_code": "not_a_real_action"},
    )
    assert bad.status_code == 400


def test_plan_ai_requires_auth(client):
    response = client.get(
        "/api/v1/finance/plans/00000000-0000-0000-0000-000000000001/ai-insights"
    )
    assert response.status_code in (401, 403)
