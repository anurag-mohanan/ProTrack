"""Team expenses vs company overheads: scope filter + spend_category."""

from __future__ import annotations

import uuid


def _corporate_team_id(session) -> str:
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team

    team = ensure_corporate_shared_services_team(session)
    session.commit()
    return str(team.id)


def _centre_id(client, auth_headers, code: str) -> str:
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    match = next((c for c in centres if (c.get("code") or "").upper() == code.upper()), None)
    assert match is not None, f"Missing cost centre {code}"
    return match["id"]


def test_expense_scope_team_vs_overhead(client, auth_headers, session):
    from app.models.models import Team

    corporate_id = _corporate_team_id(session)
    delivery = Team(id=uuid.uuid4(), name="Scope Delivery", is_active=True)
    session.add(delivery)
    session.commit()

    sw_id = _centre_id(client, auth_headers, "SW_LICENSES")
    rent_id = _centre_id(client, auth_headers, "RENT")

    team_exp = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": sw_id,
            "team_id": str(delivery.id),
            "name": "Scope NX license",
            "amount": "9000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "prosohm",
        },
    )
    assert team_exp.status_code == 201, team_exp.text
    body = team_exp.json()
    assert body["is_common"] is False
    assert body["spend_category"] == "software"
    assert body["cost_centre_code"] == "SW_LICENSES"

    hq_exp = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": rent_id,
            "team_id": corporate_id,
            "name": "Scope HQ rent",
            "amount": "50000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "monthly",
            "paid_by": "prosohm",
        },
    )
    assert hq_exp.status_code == 201, hq_exp.text
    hq = hq_exp.json()
    assert hq["is_common"] is True
    assert hq["spend_category"] == "shared"
    assert hq["display_group"] == "Common"

    team_list = client.get(
        "/api/v1/finance/expenses?scope=team", headers=auth_headers
    ).json()
    team_names = {row["name"] for row in team_list}
    assert "Scope NX license" in team_names
    assert "Scope HQ rent" not in team_names

    overhead_list = client.get(
        "/api/v1/finance/expenses?scope=overhead", headers=auth_headers
    ).json()
    oh_names = {row["name"] for row in overhead_list}
    assert "Scope HQ rent" in oh_names
    assert "Scope NX license" not in oh_names


def test_hardware_spend_category(client, auth_headers, session):
    from app.models.models import Team

    delivery = Team(id=uuid.uuid4(), name="CapEx Delivery", is_active=True)
    session.add(delivery)
    session.commit()
    hw_id = _centre_id(client, auth_headers, "HARDWARE")

    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": hw_id,
            "team_id": str(delivery.id),
            "name": "Workstation batch",
            "amount": "250000",
            "purchase_date": "2026-07-10",
            "currency_code": "INR",
            "nature": "capex",
            "frequency": "one_time",
            "paid_by": "prosohm",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["spend_category"] == "hardware_capex"
