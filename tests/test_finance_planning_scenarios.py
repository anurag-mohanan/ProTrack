"""API tests for persisted finance planning scenarios (v2)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.models.enums import ActivityAction, EntityType
from app.models.finance import FinancePlanningScenario
from app.models.models import Activity
from tests.conftest import login


def _sample_payload() -> dict:
    return {
        "schema_version": 2,
        "overhead": {
            "extra_hq_salary_monthly": 10000,
            "extra_shared_opex_monthly": 0,
            "extra_shared_capex_monthly": 0,
        },
        "new_teams": [
            {
                "id": "new_test1",
                "name": "IoT Delivery",
                "working_model_code": "retainer",
                "revenue_mode": "expected_revenue",
                "fixed_fee_amount": 0,
                "fixed_fee_period": "monthly",
                "expected_monthly_revenue": 500000,
                "opex_lines": [
                    {
                        "id": "ox1",
                        "category": "software_license",
                        "label": "Tools",
                        "amount_monthly": 100000,
                    }
                ],
                "delivery_headcount": 5,
                "salary_monthly_each": 80000,
                "billable": True,
            }
        ],
        "management_hires": [
            {
                "id": "mgr1",
                "label": "Delivery Manager",
                "headcount": 1,
                "salary_monthly_each": 150000,
                "attribution": "hq",
                "team_id": None,
            }
        ],
        "facility_lines": [
            {
                "id": "fac1",
                "category": "rent",
                "label": "Extra floor",
                "amount_monthly": 250000,
                "yearly": False,
                "attribution": "hq",
                "team_id": None,
            }
        ],
        "expansion": {"hires": [], "software": []},
        "opex_yearly": False,
        "capex_yearly": False,
    }


def test_planning_scenario_crud_and_clone(client, auth_headers, session):
    create = client.post(
        "/api/v1/finance/planning-scenarios",
        headers=auth_headers,
        json={
            "name": "Expansion IoT",
            "description": "Test scenario",
            "scenario_type": "expansion",
            "payload": _sample_payload(),
        },
    )
    assert create.status_code == 201
    body = create.json()
    scenario_id = body["id"]
    assert body["name"] == "Expansion IoT"
    assert body["payload"]["schema_version"] == 2
    assert len(body["payload"]["new_teams"]) == 1

    listed = client.get("/api/v1/finance/planning-scenarios", headers=auth_headers)
    assert listed.status_code == 200
    assert any(row["id"] == scenario_id for row in listed.json())

    got = client.get(f"/api/v1/finance/planning-scenarios/{scenario_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Expansion IoT"

    patched = client.patch(
        f"/api/v1/finance/planning-scenarios/{scenario_id}",
        headers=auth_headers,
        json={"name": "Expansion IoT v2"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Expansion IoT v2"

    cloned = client.post(
        f"/api/v1/finance/planning-scenarios/{scenario_id}/clone",
        headers=auth_headers,
    )
    assert cloned.status_code == 201
    assert cloned.json()["name"].endswith("(copy)")
    assert cloned.json()["id"] != scenario_id

    compute = client.post(
        "/api/v1/finance/planning-scenarios/compute",
        headers=auth_headers,
        json={"payload": _sample_payload()},
    )
    assert compute.status_code == 200
    result = compute.json()["result"]
    assert float(result["simulated_billable_fte"]) >= 5
    assert len(result["teams"]) >= 1

    compare = client.post(
        "/api/v1/finance/planning-scenarios/compare",
        headers=auth_headers,
        json={
            "scenario_id_a": scenario_id,
            "scenario_id_b": cloned.json()["id"],
        },
    )
    assert compare.status_code == 200
    assert compare.json()["scenario_a"]["name"] == "Expansion IoT v2"

    deleted = client.delete(
        f"/api/v1/finance/planning-scenarios/{scenario_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    row = session.get(FinancePlanningScenario, UUID(scenario_id))
    assert row is None

    activities = session.scalars(
        select(Activity).where(Activity.entity_type == EntityType.finance_planning_scenario)
    ).all()
    actions = {a.action for a in activities}
    assert ActivityAction.finance_planning_scenario_created in actions
    assert ActivityAction.finance_planning_scenario_updated in actions
    assert ActivityAction.finance_planning_scenario_deleted in actions


def test_planning_scenario_forbidden_without_finance_module(client):
    designer_headers = login(client, "binil@prosohm.com")
    resp = client.get("/api/v1/finance/planning-scenarios", headers=designer_headers)
    assert resp.status_code == 403
