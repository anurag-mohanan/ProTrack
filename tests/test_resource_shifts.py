"""Resource Planning wave 3 — shift masters, assignments, resolution, API."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.resource_shifts import ResourceShift
from app.services import resource_shift_service as svc
from tests.conftest import IDS, login

SHIFTS_URL = "/api/v1/resource-planning/shifts"


def _day_shift(session) -> ResourceShift:
    shift = session.query(ResourceShift).filter(ResourceShift.code == "DAY").first()
    assert shift is not None, "phase89 should seed the default Day shift"
    return shift


def test_default_shifts_seeded(session):
    codes = {shift.code for shift in svc.list_shifts(session)}
    assert {"DAY", "EVE", "NGT"} <= codes


def test_shift_duration_accounts_for_break_and_overnight(session):
    day = _day_shift(session)
    # 09:00–18:00 minus a 60 minute break.
    assert svc.shift_duration_hours(day) == Decimal("8.00")

    night = session.query(ResourceShift).filter(ResourceShift.code == "NGT").first()
    # 22:00–07:00 wraps midnight, minus a 60 minute break.
    assert svc.shift_duration_hours(night) == Decimal("8.00")


def test_permanent_assignment_resolves_for_employee(session):
    shift = _day_shift(session)
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
    shift = _day_shift(session)
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
    shifts = {shift.code: shift for shift in svc.list_shifts(session)}
    first = svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["DAY"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 1, 1),
        },
    )
    switch_date = date(2026, 4, 1)
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["NGT"].id,
            "assignment_type": "permanent",
            "effective_from": switch_date,
            "end_date_existing": True,
        },
    )

    session.refresh(first)
    assert first.effective_to == switch_date - timedelta(days=1)
    # History is preserved, not rewritten.
    assert svc.get_employee_shift(session, IDS["user_binil"], date(2026, 2, 1)).code == "DAY"
    assert svc.get_employee_shift(session, IDS["user_binil"], switch_date).code == "NGT"


def test_rotational_weekly_matches_only_configured_weekdays(session):
    shifts = {shift.code: shift for shift in svc.list_shifts(session)}
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_anurag"],
            "shift_id": shifts["EVE"].id,
            "assignment_type": "rotational",
            "rotation_pattern": "weekly",
            # Monday and Wednesday only.
            "rotation_weekdays": [0, 2],
            "effective_from": date(2026, 3, 2),
        },
    )

    monday = date(2026, 3, 2)
    assert monday.weekday() == 0
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday).code == "EVE"
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday + timedelta(days=2)).code == "EVE"
    # Tuesday / Thursday are not part of the rotation.
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday + timedelta(days=1)) is None
    assert svc.get_employee_shift(session, IDS["user_anurag"], monday + timedelta(days=3)) is None


def test_rotational_overrides_permanent_on_matching_day(session):
    shifts = {shift.code: shift for shift in svc.list_shifts(session)}
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["DAY"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 3, 1),
        },
    )
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["NGT"].id,
            "assignment_type": "rotational",
            "rotation_pattern": "weekly",
            "rotation_weekdays": [5, 6],
            "effective_from": date(2026, 3, 1),
        },
    )

    saturday = date(2026, 3, 7)
    assert saturday.weekday() == 5
    assert svc.get_employee_shift(session, IDS["user_binil"], saturday).code == "NGT"
    assert svc.get_employee_shift(session, IDS["user_binil"], date(2026, 3, 5)).code == "DAY"


def test_bulk_assign_reports_conflicts(session):
    shift = _day_shift(session)
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shift.id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 3, 1),
        },
    )

    created, conflicts = svc.bulk_assign(
        session,
        {
            "user_ids": [IDS["user_binil"], IDS["user_anurag"]],
            "shift_id": shift.id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 4, 1),
        },
    )
    assert [item.user_id for item in created] == [IDS["user_anurag"]]
    assert [item["user_id"] for item in conflicts] == [IDS["user_binil"]]


def test_shift_hours_for_range_feeds_capacity(session):
    shifts = {shift.code: shift for shift in svc.list_shifts(session)}
    svc.update_shift(session, shifts["EVE"], {"break_minutes": 0})
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["EVE"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 3, 2),
        },
    )

    hours = svc.shift_hours_for_range(
        session, [IDS["user_binil"]], date(2026, 3, 2), date(2026, 3, 4)
    )
    # 14:00–23:00 with no break.
    assert hours[IDS["user_binil"]][date(2026, 3, 3)] == Decimal("9.00")


def test_resource_planning_grid_still_builds_without_shifts(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "designers" in response.json()


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def test_api_shift_crud_and_assignment_flow(client, auth_headers):
    listed = client.get(SHIFTS_URL, headers=auth_headers)
    assert listed.status_code == 200
    assert {item["code"] for item in listed.json()} >= {"DAY", "EVE", "NGT"}

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
    shift_id = client.get(SHIFTS_URL, headers=auth_headers).json()[0]["id"]
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

    shift_id = client.get(SHIFTS_URL, headers=headers).json()[0]["id"]
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
