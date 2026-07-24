"""Advanced team expenses: Common (corporate) vs delivery display_group fields."""

from __future__ import annotations

import uuid


def _corporate_team_id(session) -> str:
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team

    team = ensure_corporate_shared_services_team(session)
    session.commit()
    return str(team.id)


def test_expense_list_marks_common_vs_delivery(client, auth_headers, session):
    from app.models.models import Team

    corporate_id = _corporate_team_id(session)
    delivery = Team(id=uuid.uuid4(), name="Delivery Alpha", is_active=True)
    session.add(delivery)
    session.commit()

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    centre_id = centres[0]["id"]

    common_create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": corporate_id,
            "name": "HQ shared rent",
            "amount": "5000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "monthly",
            "paid_by": "prosohm",
        },
    )
    assert common_create.status_code == 201, common_create.text
    common_body = common_create.json()
    assert common_body["is_common"] is True
    assert common_body["display_group"] == "Common"
    assert common_body["team_name"]

    delivery_create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": str(delivery.id),
            "name": "Alpha tooling license",
            "amount": "1200",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "prosohm",
        },
    )
    assert delivery_create.status_code == 201, delivery_create.text
    delivery_body = delivery_create.json()
    assert delivery_body["is_common"] is False
    assert delivery_body["display_group"] == "Delivery Alpha"
    assert delivery_body["team_name"] == "Delivery Alpha"

    listed = client.get("/api/v1/finance/expenses", headers=auth_headers).json()
    by_name = {row["name"]: row for row in listed}
    assert by_name["HQ shared rent"]["is_common"] is True
    assert by_name["HQ shared rent"]["display_group"] == "Common"
    assert by_name["Alpha tooling license"]["is_common"] is False
    assert by_name["Alpha tooling license"]["display_group"] == "Delivery Alpha"


def test_expense_patch_keeps_display_group_fields(client, auth_headers, session):
    corporate_id = _corporate_team_id(session)
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": corporate_id,
            "name": "Common patch target",
            "amount": "100",
            "purchase_date": "2026-07-15",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "one_time",
            "paid_by": "prosohm",
        },
    )
    assert created.status_code == 201, created.text
    expense_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/finance/expenses/{expense_id}",
        headers=auth_headers,
        json={"amount": "150", "name": "Common patch target v2"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["name"] == "Common patch target v2"
    assert body["is_common"] is True
    assert body["display_group"] == "Common"
    assert float(body["amount"]) == 150.0
