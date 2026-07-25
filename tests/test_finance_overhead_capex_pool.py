"""Corporate CapEx is part of the overhead CPR pool allocated to delivery teams."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.finance import CostCentre


def test_corporate_capex_enters_overhead_pool_and_cpr(client, auth_headers, session):
    home = ensure_corporate_shared_services_team(session)
    session.commit()
    centre = session.scalar(select(CostCentre).where(CostCentre.code == "HARDWARE"))
    if centre is None:
        centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
        hw = next(row for row in centres if row["code"] == "HARDWARE")
        centre_id = hw["id"]
    else:
        centre_id = str(centre.id)

    before = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    pool_before = Decimal(str(before["overhead"]["overhead_pool_monthly_inr"]))
    cpr_before = Decimal(str(before["overhead"]["overhead_cost_per_resource_inr"]))
    capex_before = Decimal(str(before["overhead"].get("overhead_capex_inr") or 0))

    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": str(home.id),
            "name": "HQ shared workstations",
            "amount": "120000",
            "purchase_date": date.today().replace(day=1).isoformat(),
            "currency_code": "INR",
            "nature": "capex",
            "frequency": "monthly",
            "paid_by": "prosohm",
        },
    )
    assert created.status_code == 201, created.text

    after = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    pool_after = Decimal(str(after["overhead"]["overhead_pool_monthly_inr"]))
    cpr_after = Decimal(str(after["overhead"]["overhead_cost_per_resource_inr"]))
    capex_after = Decimal(str(after["overhead"]["overhead_capex_inr"]))

    # Monthly CapEx on Corporate enters the overhead pool / CPR.
    assert capex_after >= capex_before + Decimal("120000.00")
    assert pool_after >= pool_before + Decimal("120000.00")
    assert cpr_after >= cpr_before

    delivery = [row for row in (after.get("by_team") or []) if not row.get("is_overhead_home")]
    if delivery and int(after["overhead"]["billable_resource_count"] or 0) > 0:
        assert any(
            Decimal(str(row.get("allocated_overhead_inr") or 0)) > 0 for row in delivery
        )


def test_overhead_pool_breakdown_includes_capex_group(client, auth_headers):
    pool = client.get(
        "/api/v1/finance/kpi-breakdown?metric=overhead_pool",
        headers=auth_headers,
    )
    assert pool.status_code == 200, pool.text
    labels = {g["label"] for g in pool.json()["groups"]}
    assert "Salaries" in labels
    assert "OpEx" in labels
    assert "CapEx" in labels

    capex = client.get(
        "/api/v1/finance/kpi-breakdown?metric=overhead_capex",
        headers=auth_headers,
    )
    assert capex.status_code == 200, capex.text
    assert capex.json()["metric"] == "overhead_capex"
