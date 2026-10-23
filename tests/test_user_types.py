"""Employee vs virtual/system accounts: classification, exclusions, audit."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.timesheet_eligibility import user_requires_timesheet
from app.models.enums import ActivityAction, UserType
from app.models.models import Activity, User
from app.services import resource_allocation_engine as engine
from tests.conftest import IDS, login


def _create(client, headers, *, user_type: str | None = None) -> dict:
    payload = {
        "role_id": str(IDS["role_designer"]),
        "email": f"type.{uuid.uuid4().hex[:8]}@prosohm.com",
        "password": "TempPass@123",
        "first_name": "Type",
        "last_name": "Check",
        "is_active": True,
        "employment_type": "full_time",
    }
    if user_type:
        payload["user_type"] = user_type
    created = client.post("/api/v1/users", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def _hr_total(client, headers) -> int:
    response = client.get("/api/v1/hr/dashboard/overview", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["cards"]["total_employees"]


def test_virtual_account_keeps_role_but_is_excluded(client, session):
    admin = login(client, "admin@prosohm.com")
    headcount_before = _hr_total(client, admin)
    virtual = _create(client, admin, user_type="virtual")
    assert _hr_total(client, admin) == headcount_before
    _create(client, admin)
    assert _hr_total(client, admin) == headcount_before + 1
    assert virtual["user_type"] == "virtual"
    assert virtual["requires_timesheet"] is False
    assert virtual["requires_salary"] is False
    assert virtual["role_id"] == str(IDS["role_designer"])

    row = session.get(User, uuid.UUID(virtual["id"]))
    assert user_requires_timesheet(row) is False
    blocked = engine.employee_block(session, row.id)
    assert blocked and "virtual/system account" in blocked

    virtual_list = client.get(
        "/api/v1/users", headers=admin, params={"user_type": "virtual", "page_size": 200}
    ).json()["items"]
    assert virtual["id"] in {item["id"] for item in virtual_list}
    employee_list = client.get(
        "/api/v1/users", headers=admin, params={"user_type": "employee", "page_size": 200}
    ).json()["items"]
    assert virtual["id"] not in {item["id"] for item in employee_list}


def test_reclassification_warns_and_is_audited(client, session):
    admin = login(client, "admin@prosohm.com")
    person = _create(client, admin)
    assert person["user_type"] == "employee"
    assert person["requires_timesheet"] is True

    impact = client.get(
        f"/api/v1/users/{person['id']}/user-type-impact",
        headers=admin,
        params={"target": "virtual"},
    )
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["changes"] is True
    assert body["current_type"] == "employee"
    assert body["effects"]
    for key in ("open_asset_assignments", "active_shift_assignments", "open_project_assignments"):
        assert isinstance(body[key], int)

    changed = client.patch(
        f"/api/v1/users/{person['id']}", headers=admin, json={"user_type": "virtual"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["user_type"] == "virtual"
    assert changed.json()["requires_timesheet"] is False
    audit = session.scalars(
        select(Activity).where(
            Activity.entity_id == uuid.UUID(person["id"]),
            Activity.action == ActivityAction.user_type_changed,
        )
    ).all()
    assert len(audit) == 1
    assert audit[0].old_value == "employee" and audit[0].new_value == "virtual"

    back = client.patch(
        f"/api/v1/users/{person['id']}", headers=admin, json={"user_type": "employee"}
    )
    assert back.status_code == 200, back.text
    assert back.json()["requires_timesheet"] is True
    session.expire_all()
    assert session.get(User, uuid.UUID(person["id"])).user_type == UserType.employee


def test_only_admin_can_view_type_impact(client):
    admin = login(client, "admin@prosohm.com")
    person = _create(client, admin)
    designer = login(client, "binil@prosohm.com")
    denied = client.get(
        f"/api/v1/users/{person['id']}/user-type-impact",
        headers=designer,
        params={"target": "virtual"},
    )
    assert denied.status_code == 403
