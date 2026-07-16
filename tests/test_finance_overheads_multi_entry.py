"""Overheads multi-entry: many expense lines per cost centre (e.g. SW licenses)."""

from decimal import Decimal

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.finance import CostCentre
from sqlalchemy import select


def test_multiple_software_license_lines_same_centre(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    centre = session.scalar(select(CostCentre).where(CostCentre.code == "SW_LICENSES"))
    assert centre is not None
    session.commit()

    purchase = "2035-05-01"
    for name, amount in (("NX Mach 3", "120000"), ("NX Mach 2", "80000")):
        created = client.post(
            "/api/v1/finance/expenses",
            headers=auth_headers,
            json={
                "team_id": str(team.id),
                "cost_centre_id": str(centre.id),
                "name": name,
                "amount": amount,
                "currency_code": "INR",
                "nature": "opex",
                "frequency": "yearly",
                "paid_by": "prosohm",
                "purchase_date": purchase,
                "start_date": purchase,
                "is_recurring": True,
                "notify_enabled": False,
            },
        )
        assert created.status_code == 201, created.text

    listed = client.get(
        f"/api/v1/finance/expenses?team_id={team.id}&current_fy_only=false",
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    sw_lines = [
        row
        for row in listed.json()
        if row["cost_centre_id"] == str(centre.id)
        and row["name"] in ("NX Mach 3", "NX Mach 2")
        and row["paid_by"] == "prosohm"
    ]
    assert len(sw_lines) >= 2
    names = {row["name"] for row in sw_lines}
    assert "NX Mach 3" in names and "NX Mach 2" in names
    totals = sum(Decimal(str(row["amount"])) for row in sw_lines if row["name"] in names)
    assert totals >= Decimal("200000")
