"""Annual finance plan API tests."""

from decimal import Decimal
from io import BytesIO

from tests.conftest import DEFAULT_PASSWORD


def _auth(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_plan_seeds_sales_and_expenses(client, auth_headers):
    response = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY Test Plan",
            "fiscal_year_start_year": 2030,
            "fy_start_month": 4,
            "tax_percent": 30,
            "provision_percent": 20,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["fiscal_year_label"] == "2030-31"
    sections = {row["section"] for row in body["lines"]}
    assert "sales" in sections
    assert "expenses" in sections
    labels = {row["label"] for row in body["lines"]}
    assert "ABC-mold" in labels
    assert "Wages" in labels
    assert body["summary"]["gain_loss"] == "0"


def test_plan_pnl_math(client, auth_headers):
    create = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY Math",
            "fiscal_year_start_year": 2031,
            "tax_percent": 30,
            "provision_percent": 20,
        },
    )
    assert create.status_code == 201, create.text
    plan = create.json()
    plan_id = plan["id"]
    sales_line = next(row for row in plan["lines"] if row["code"] == "abc_mold")
    expense_line = next(row for row in plan["lines"] if row["code"] == "wages")

    updated = client.put(
        f"/api/v1/finance/plans/{plan_id}/lines/{sales_line['id']}",
        headers=auth_headers,
        json={"month_01": "1000"},
    )
    assert updated.status_code == 200, updated.text

    updated_exp = client.put(
        f"/api/v1/finance/plans/{plan_id}/lines/{expense_line['id']}",
        headers=auth_headers,
        json={"month_01": "200"},
    )
    assert updated_exp.status_code == 200, updated_exp.text

    detail = client.get(f"/api/v1/finance/plans/{plan_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    summary = detail.json()["summary"]
    assert Decimal(summary["sales_fy"]) == Decimal("1000")
    assert Decimal(summary["expenses_fy"]) == Decimal("200")
    assert Decimal(summary["gain_loss"]) == Decimal("800")
    # 800 * 0.7 = 560; provision 20% of 560 = 112; after = 448
    assert Decimal(summary["after_tax"]) == Decimal("560.00")
    assert Decimal(summary["provision_amount"]) == Decimal("112.00")
    assert Decimal(summary["gain_loss_after_provision"]) == Decimal("448.00")


def test_designer_forbidden_from_plans(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/finance/plans", headers=headers)
    assert response.status_code == 403
