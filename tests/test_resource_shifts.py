"""Resource Planning wave 3 — shift masters, assignments, resolution, API."""

from datetime import date, timedelta
from decimal import Decimal
import json

import pytest

from app.core.access_control import (
    ENGINEERING_MANAGER,
    SPECIAL_ASSIGN_RESOURCE_SHIFTS,
    SPECIAL_MANAGE_RESOURCE_SHIFTS,
    resolve_user_special_permissions,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import resource_shift_service as svc
from tests.conftest import IDS, login

SHIFTS_URL = "/api/v1/resource-planning/shifts"


def _general_shift(session) -> ResourceShift:
    shift = session.query(ResourceShift).filter(ResourceShift.code == "GENERAL").first()
    assert shift is not None, "phase89 should seed the General shift"
    return shift


def _shifts_by_code(session) -> dict[str, ResourceShift]:
    return {shift.code: shift for shift in svc.list_shifts(session, active_only=False)}


def test_default_shifts_seeded(session):
    codes = {shift.code for shift in svc.list_shifts(session, active_only=True)}
    assert {"FIRST", "SECOND", "GENERAL"} <= codes
    # Obsolete Day/Evening/Night seeds must not stay active for new assignments.
    active_legacy = {
        shift.code
        for shift in svc.list_shifts(session, active_only=True)
        if shift.code in {"DAY", "EVE", "NGT"}
    }
    assert not active_legacy


def test_company_shift_windows_and_display(session):
    shifts = _shifts_by_code(session)
    assert svc.format_shift_window(shifts["FIRST"].start_time, shifts["FIRST"].end_time) == (
        "6:00 AM – 2:00 PM"
    )
    assert svc.format_shift_window(shifts["SECOND"].start_time, shifts["SECOND"].end_time) == (
        "2:00 PM – 10:00 PM"
    )
    assert svc.format_shift_window(shifts["GENERAL"].start_time, shifts["GENERAL"].end_time) == (
        "9:00 AM – 6:00 PM"
    )


def test_shift_duration_accounts_for_break_and_overnight(session):
    general = _general_shift(session)
    # 09:00–18:00 minus a 60 minute break.
    assert svc.shift_duration_hours(general) == Decimal("8.00")

    overnight = svc.create_shift(
        session,
        {
            "code": "NIGHTX",
            "name": "Overnight Test",
            "start_time": "22:00",
            "end_time": "07:00",
            "break_minutes": 60,
            "is_overnight": True,
        },
    )
    assert svc.shift_duration_hours(overnight) == Decimal("8.00")


def test_permanent_assignment_resolves_for_employee(session):
    shift = _general_shift(session)
    start = date(2026, 3, 2)
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shift.id,
            "assignment_type": "permanent",
            "effective_from": start,
        },
    )

    resolved = svc.get_employee_shift(session, IDS["user_binil"], start + timedelta(days=10))
    assert resolved is not None
    assert resolved.id == shift.id

    # Nothing before the effective date.
    assert svc.get_employee_shift(session, IDS["user_binil"], start - timedelta(days=1)) is None


def test_overlapping_permanent_assignment_is_rejected(session):
    shift = _general_shift(session)
    base = {
        "user_id": IDS["user_binil"],
        "shift_id": shift.id,
        "assignment_type": "permanent",
        "effective_from": date(2026, 3, 1),
        "effective_to": date(2026, 6, 30),
    }
    svc.assign_shift(session, dict(base))

    with pytest.raises(svc.ShiftConflictError):
        svc.assign_shift(session, {**base, "effective_from": date(2026, 5, 1), "effective_to": None})


def test_end_date_existing_closes_history_instead_of_overwriting(session):
    shifts = _shifts_by_code(session)
    first = svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["GENERAL"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 1, 1),
        },
    )
    switch_date = date(2026, 4, 1)
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["FIRST"].id,
            "assignment_type": "permanent",
            "effective_from": switch_date,
            "end_date_existing": True,
        },
    )

    session.refresh(first)
    assert first.effective_to == switch_date - timedelta(days=1)
    # History is preserved, not rewritten.
    assert svc.get_employee_shift(session, IDS["user_binil"], date(2026, 2, 1)).code == "GENERAL"
    assert svc.get_employee_shift(session, IDS["user_binil"], switch_date).code == "FIRST"


def test_rotational_weekly_assignment(session):
    shifts = _shifts_by_code(session)
    monday = date(2026, 3, 2)  # Monday
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_anurag"],
            "shift_id": shifts["SECOND"].id,
            "assignment_type": "rotational",
            "rotation_pattern": "weekly",
            "rotation_weekdays": [0, 2, 4],  # Mon/Wed/Fri
            "effective_from": monday,
        },
    )
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday).code == "SECOND"
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday + timedelta(days=2)).code == "SECOND"
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday + timedelta(days=1)) is None


def test_shift_hours_for_range_feeds_capacity(session):
    shifts = _shifts_by_code(session)
    svc.update_shift(session, shifts["SECOND"], {"break_minutes": 0})
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["SECOND"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 3, 2),
        },
    )

    hours = svc.shift_hours_for_range(
        session, [IDS["user_binil"]], date(2026, 3, 2), date(2026, 3, 4)
    )
    # 14:00–22:00 with no break.
    assert hours[IDS["user_binil"]][date(2026, 3, 3)] == Decimal("8.00")


def test_resource_planning_grid_still_builds_without_shifts(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "designers" in response.json()


def test_admin_with_stale_special_permissions_can_still_assign(client, session):
    """FE grants Admin all specials; BE must match even when stored JSON is stale."""
    admin = session.get(User, IDS["user_admin"])
    admin.special_permissions = json.dumps(["manage_users", "view_reports"])
    session.add(admin)
    session.commit()

    resolved = resolve_user_special_permissions(admin, "Admin")
    assert SPECIAL_ASSIGN_RESOURCE_SHIFTS in resolved
    assert SPECIAL_MANAGE_RESOURCE_SHIFTS in resolved

    headers = login(client, "admin@prosohm.com")
    shift_id = client.get(f"{SHIFTS_URL}?active_only=true", headers=headers).json()[0]["id"]
    assigned = client.post(
        f"{SHIFTS_URL}/assignments",
        headers=headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": shift_id,
            "assignment_type": "permanent",
            "effective_from": "2026-09-07",
            "end_date_existing": True,
        },
    )
    assert assigned.status_code == 201, assigned.text


def test_engineering_manager_stale_specials_still_get_assign(session):
    """Saved specials without assign_resource_shifts must still resolve for Eng Manager."""
    user = session.get(User, IDS["user_pm"])  # typically Engineering Manager fixture
    if user is None:
        pytest.skip("user_pm fixture missing")
    user.special_permissions = json.dumps(
        ["create_projects", "edit_projects", "view_reports", "view_resource_planning"]
    )
    session.add(user)
    session.commit()
    resolved = resolve_user_special_permissions(user, ENGINEERING_MANAGER)
    assert SPECIAL_ASSIGN_RESOURCE_SHIFTS in resolved
    assert "view_resource_planning" in resolved
    # Custom/stale list is not wiped — create_projects remains.
    assert "create_projects" in resolved

# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def test_api_shift_crud_and_assignment_flow(client, auth_headers):
    listed = client.get(SHIFTS_URL, headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert {item["code"] for item in body if item["is_active"]} >= {
        "FIRST",
        "SECOND",
        "GENERAL",
    }
    general = next(item for item in body if item["code"] == "GENERAL")
    assert general["display_window"] == "9:00 AM – 6:00 PM"
    assert general["display_label"].startswith("General Shift")

    created = client.post(
        SHIFTS_URL,
        headers=auth_headers,
        json={
            "code": "SPL",
            "name": "Split Shift",
            "start_time": "06:00",
            "end_time": "15:00",
            "break_minutes": 30,
        },
    )
    assert created.status_code == 201, created.text
    shift_id = created.json()["id"]

    patched = client.patch(
        f"{SHIFTS_URL}/{shift_id}",
        headers=auth_headers,
        json={"name": "Split Shift (Early)", "break_minutes": 45},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Split Shift (Early)"

    assigned = client.post(
        f"{SHIFTS_URL}/assignments",
        headers=auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": shift_id,
            "assignment_type": "permanent",
            "effective_from": "2026-03-02",
        },
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["shift_code"] == "SPL"
    assert assigned.json()["shift_display"]

    conflict = client.post(
        f"{SHIFTS_URL}/assignments",
        headers=auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": shift_id,
            "assignment_type": "permanent",
            "effective_from": "2026-04-01",
        },
    )
    assert conflict.status_code == 409

    for_user = client.get(
        f"{SHIFTS_URL}/for-user/{IDS['user_binil']}?date=2026-03-10",
        headers=auth_headers,
    )
    assert for_user.status_code == 200
    assert for_user.json()["shift"]["code"] == "SPL"

    calendar = client.get(
        f"{SHIFTS_URL}/calendar?from=2026-03-02&to=2026-03-08",
        headers=auth_headers,
    )
    assert calendar.status_code == 200
    rows = calendar.json()["rows"]
    assert any(str(IDS["user_binil"]) == row["user_id"] for row in rows)


def test_api_bulk_assignment_returns_conflicts(client, auth_headers):
    shift_id = next(
        item["id"]
        for item in client.get(f"{SHIFTS_URL}?active_only=true", headers=auth_headers).json()
        if item["code"] == "GENERAL"
    )
    client.post(
        f"{SHIFTS_URL}/assignments",
        headers=auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": shift_id,
            "effective_from": "2026-03-02",
        },
    )
    response = client.post(
        f"{SHIFTS_URL}/assignments/bulk",
        headers=auth_headers,
        json={
            "user_ids": [str(IDS["user_binil"]), str(IDS["user_anurag"])],
            "shift_id": shift_id,
            "effective_from": "2026-05-01",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["created"]) == 1
    assert len(body["conflicts"]) == 1


def test_api_requires_manage_permission_to_create_shift(client):
    designer_headers = login(client, "binil@prosohm.com")
    response = client.post(
        SHIFTS_URL,
        headers=designer_headers,
        json={
            "code": "XXX",
            "name": "Nope",
            "start_time": "09:00",
            "end_time": "17:00",
        },
    )
    assert response.status_code == 403


def test_api_requires_view_access_to_list_shifts(client):
    designer_headers = login(client, "binil@prosohm.com")
    assert client.get(SHIFTS_URL, headers=designer_headers).status_code == 403


def test_api_requires_authentication(client):
    assert client.get(SHIFTS_URL).status_code == 401


def test_engineering_manager_can_assign_but_not_manage(client):
    headers = login(client, "pm@prosohm.com")
    assert client.get(SHIFTS_URL, headers=headers).status_code == 200

    denied = client.post(
        SHIFTS_URL,
        headers=headers,
        json={"code": "EM1", "name": "EM shift", "start_time": "09:00", "end_time": "17:00"},
    )
    assert denied.status_code == 403

    shift_id = next(
        item["id"]
        for item in client.get(f"{SHIFTS_URL}?active_only=true", headers=headers).json()
        if item["code"] == "FIRST"
    )
    allowed = client.post(
        f"{SHIFTS_URL}/assignments",
        headers=headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": shift_id,
            "effective_from": "2026-03-02",
        },
    )
    assert allowed.status_code == 201, allowed.text


def test_designer_cannot_assign_via_api(client):
    headers = login(client, "binil@prosohm.com")
    # Designers cannot even list — but if they somehow had a shift id, assign must 403.
    response = client.post(
        f"{SHIFTS_URL}/assignments",
        headers=headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "shift_id": str(IDS["user_binil"]),
            "effective_from": "2026-03-02",
        },
    )
    assert response.status_code == 403
