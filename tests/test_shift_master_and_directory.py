"""Shift Master roster, employee directory, per-shift capacity and the section 67 scenario."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import AssetType, SoftwareCatalog, SoftwareLicensePool
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, it_data_quality_service
from app.services import resource_shift_service as shifts
from tests.conftest import IDS, login

API = "/api/v1"
TODAY = date.today()


def _shift(session, code: str) -> ResourceShift:
    shifts.ensure_company_standard_shifts(session)
    row = session.scalar(select(ResourceShift).where(ResourceShift.code == code))
    assert row is not None
    return row


def _employee(session, label: str, *, active: bool = True) -> User:
    user = User(
        id=uuid4(),
        role_id=IDS["role_junior_designer"],
        email=f"{label.lower()}-{uuid4().hex[:6]}@example.test",
        password_hash="x",
        first_name="Employee",
        last_name=f"{label}-{uuid4().hex[:4]}",
        designation="Designer",
        is_active=active,
    )
    session.add(user)
    session.commit()
    return user


def _put_on_shift(session, user: User, shift: ResourceShift) -> None:
    shifts.assign_shift(
        session,
        {
            "user_id": user.id,
            "shift_id": shift.id,
            "assignment_type": "permanent",
            "effective_from": TODAY - timedelta(days=1),
            "end_date_existing": True,
        },
    )


def _workstation(session, number: str):
    desktop = session.scalar(select(AssetType).where(AssetType.code == "DESKTOP"))
    if desktop is None:
        desktop = AssetType(id=uuid4(), code="DESKTOP", name="Desktop", category="computer", is_active=True)
        session.add(desktop)
        session.commit()
    admin = session.get(User, IDS["user_admin"])
    return it_asset_service.create_asset(
        session, actor=admin, asset_type_id=desktop.id,
        asset_number=f"{number}-{uuid4().hex[:4].upper()}", computer_type="ENG_WS", commit=True,
    )


def _cimatron(session, seats: int) -> SoftwareLicensePool:
    software = SoftwareCatalog(id=uuid4(), name=f"Cimatron-{uuid4().hex[:4]}", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid4(), software_id=software.id, seat_count=seats, status="active",
        assignment_model="floating", entitlement_code=f"CIM-{uuid4().hex[:4]}",
    )
    session.add(pool)
    session.commit()
    return pool


def _assign_ws(client, headers, ws, user, shift):
    return client.post(
        f"{API}/it/assets/{ws.id}/assign", headers=headers,
        json={"user_id": str(user.id), "shift_id": str(shift.id)},
    )


def _assign_license(client, headers, pool, user, shift):
    return client.post(
        f"{API}/it/software/assignments", headers=headers,
        json={"license_pool_id": str(pool.id), "user_id": str(user.id), "shift_id": str(shift.id)},
    )


# --- section 67: WS-001 + Cimatron ---------------------------------------------------------------


def test_section_67_workstation_and_cimatron_by_shift(client, session, auth_headers):
    first, second, general = _shift(session, "FIRST"), _shift(session, "SECOND"), _shift(session, "GENERAL")
    a, b, c, d = (_employee(session, x) for x in "ABCD")
    for user, shift in ((a, first), (b, second), (c, general), (d, first)):
        _put_on_shift(session, user, shift)
    ws = _workstation(session, "WS-001")
    pool = _cimatron(session, 1)

    assert _assign_ws(client, auth_headers, ws, a, first).status_code == 200
    assert _assign_license(client, auth_headers, pool, a, first).status_code in (200, 201)
    assert _assign_ws(client, auth_headers, ws, b, second).status_code == 200
    assert _assign_license(client, auth_headers, pool, b, second).status_code in (200, 201)

    blocked_ws = _assign_ws(client, auth_headers, ws, c, general)
    assert blocked_ws.status_code == 409, blocked_ws.text
    detail = blocked_ws.json()["detail"]
    assert a.last_name in detail or b.last_name in detail
    assert _assign_license(client, auth_headers, pool, c, general).status_code == 409

    assert _assign_ws(client, auth_headers, ws, d, first).status_code == 409
    assert _assign_license(client, auth_headers, pool, d, first).status_code == 409

    raised = client.patch(f"{API}/it/software/licenses/{pool.id}", headers=auth_headers, json={"seat_count": 2})
    assert raised.status_code == 200, raised.text

    c_license = _assign_license(client, auth_headers, pool, c, general)
    assert c_license.status_code in (200, 201), c_license.text
    another_first = _employee(session, "F")
    _put_on_shift(session, another_first, first)
    assert _assign_license(client, auth_headers, pool, another_first, first).status_code == 409

    capacity = client.get(f"{API}/resource-planning/shifts/capacity", headers=auth_headers)
    assert capacity.status_code == 200, capacity.text
    by_code = {row["shift_code"]: row for row in capacity.json()["shifts"]}
    assert by_code["FIRST"]["window"] == "06:00–14:00"
    assert by_code["GENERAL"]["window"] == "09:00–18:00"
    cim = {row["shift_code"]: next(lic for lic in row["licenses"] if lic["license_pool_id"] == str(pool.id))
           for row in capacity.json()["shifts"]}
    assert cim["FIRST"]["available"] == 0
    assert cim["SECOND"]["available"] == 0
    assert by_code["FIRST"]["employees"] >= 3


# --- sections 51-53: roster visibility -----------------------------------------------------------


def test_roster_lists_every_employee_with_shift_state(client, session, auth_headers):
    first, second, general = _shift(session, "FIRST"), _shift(session, "SECOND"), _shift(session, "GENERAL")
    a, b, c, d = (_employee(session, x) for x in "ABCD")
    e = _employee(session, "E", active=False)
    for user, shift in ((a, first), (b, second), (c, general)):
        _put_on_shift(session, user, shift)

    res = client.get(f"{API}/resource-planning/shifts/roster", headers=auth_headers)
    assert res.status_code == 200, res.text
    rows = {row["user_id"]: row for row in res.json()["rows"]}
    assert rows[str(a.id)]["shift_code"] == "FIRST"
    assert rows[str(a.id)]["shift_display"]
    assert rows[str(b.id)]["shift_code"] == "SECOND"
    assert rows[str(c.id)]["shift_code"] == "GENERAL"
    assert rows[str(d.id)]["shift_state"] == "NOT_ASSIGNED"
    assert rows[str(d.id)]["shift_code"] is None
    assert str(e.id) not in rows

    none_only = client.get(f"{API}/resource-planning/shifts/roster?shift=none", headers=auth_headers).json()
    ids = {row["user_id"] for row in none_only["rows"]}
    assert str(d.id) in ids and str(a.id) not in ids

    first_only = client.get(f"{API}/resource-planning/shifts/roster?shift=FIRST", headers=auth_headers).json()
    assert {row["shift_code"] for row in first_only["rows"]} == {"FIRST"}

    inactive = client.get(f"{API}/resource-planning/shifts/roster?status=inactive", headers=auth_headers).json()
    inactive_rows = {row["user_id"]: row for row in inactive["rows"]}
    assert inactive_rows[str(e.id)]["shift_state"] == "INACTIVE"
    assert str(a.id) not in inactive_rows

    searched = client.get(
        f"{API}/resource-planning/shifts/roster", headers=auth_headers, params={"q": d.last_name}
    ).json()
    assert [row["user_id"] for row in searched["rows"]] == [str(d.id)]


def test_it_employee_picker_is_unscoped_and_permission_checked(client, session, auth_headers):
    d = _employee(session, "D")
    res = client.get(f"{API}/it/allocation/employees", headers=auth_headers, params={"q": d.last_name})
    assert res.status_code == 200, res.text
    row = res.json()["rows"][0]
    assert row["user_id"] == str(d.id)
    assert row["shift_state"] == "NOT_ASSIGNED"

    denied = client.get(f"{API}/it/allocation/employees", headers=login(client, "readonly@prosohm.com"))
    assert denied.status_code == 403


def test_calendar_includes_employees_without_a_shift(client, session, auth_headers):
    d = _employee(session, "D")
    res = client.get(
        f"{API}/resource-planning/shifts/calendar", headers=auth_headers,
        params={"from": TODAY.isoformat(), "to": TODAY.isoformat()},
    )
    assert res.status_code == 200, res.text
    row = next(r for r in res.json()["rows"] if r["user_id"] == str(d.id))
    assert row["days"][0]["shift_id"] is None


# --- active-employee rule ---------------------------------------------------------------------


def test_inactive_employee_cannot_receive_shift_or_resources(client, session, auth_headers):
    first = _shift(session, "FIRST")
    e = _employee(session, "E", active=False)
    ws = _workstation(session, "WS-INACT")
    pool = _cimatron(session, 1)

    shift_res = client.post(
        f"{API}/resource-planning/shifts/assignments", headers=auth_headers,
        json={"user_id": str(e.id), "shift_id": str(first.id), "effective_from": TODAY.isoformat(),
              "assignment_type": "permanent"},
    )
    assert shift_res.status_code in (400, 422), shift_res.text
    assert "inactive" in shift_res.json()["detail"]
    assert _assign_ws(client, auth_headers, ws, e, first).status_code == 422
    assert _assign_license(client, auth_headers, pool, e, first).status_code == 422

    check = client.post(
        f"{API}/it/allocation/check", headers=auth_headers,
        json={"resource_type": "asset", "resource_id": str(ws.id), "user_id": str(e.id),
              "shift_id": str(first.id)},
    ).json()
    assert check["available"] is False
    assert check["reason_code"] == "EMPLOYEE_INELIGIBLE"


def test_data_quality_flags_inactive_shift_holders(session):
    first = _shift(session, "FIRST")
    leaver = _employee(session, "L")
    _put_on_shift(session, leaver, first)
    leaver.is_active = False
    session.commit()
    report = it_data_quality_service.build_data_quality_report(session)
    issue = next(i for i in report["issues"] if i["code"] == "shift_assigned_to_inactive_employee")
    assert any(s["user_id"] == str(leaver.id) for s in issue["samples"])


# --- Resource Planning package uses the engine -----------------------------------------------------


def test_package_preview_and_assign_share_a_workstation_across_shifts(client, session, auth_headers):
    first, second, general = _shift(session, "FIRST"), _shift(session, "SECOND"), _shift(session, "GENERAL")
    a, b, c = (_employee(session, x) for x in "ABC")
    _put_on_shift(session, a, first)
    _put_on_shift(session, b, second)
    _put_on_shift(session, c, general)
    ws = _workstation(session, "WS-PKG")
    desktop = session.scalar(select(AssetType).where(AssetType.code == "DESKTOP"))
    assert _assign_ws(client, auth_headers, ws, a, first).status_code == 200

    created = client.post(
        f"{API}/it/resource-packages", headers=auth_headers,
        json={"code": f"SH-{uuid4().hex[:4]}", "name": "Shift workstation",
              "hardware_lines": [{"asset_type_id": str(desktop.id), "quantity": 1, "is_required": True}]},
    )
    assert created.status_code == 201, created.text
    package_id = created.json()["id"]

    preview_b = client.post(
        f"{API}/dashboard/resource-planning/packages/{package_id}/preview",
        headers=auth_headers, json={"user_id": str(b.id)},
    ).json()
    assert preview_b["assignment_shift"]["code"] == "SECOND"
    assert str(ws.id) in {cand["id"] for cand in preview_b["hardware"][0]["candidates"]}

    preview_c = client.post(
        f"{API}/dashboard/resource-planning/packages/{package_id}/preview",
        headers=auth_headers, json={"user_id": str(c.id)},
    ).json()
    assert str(ws.id) not in {cand["id"] for cand in preview_c["hardware"][0]["candidates"]}

    assigned_b = client.post(
        f"{API}/dashboard/resource-planning/packages/{package_id}/assign",
        headers=auth_headers, json={"user_id": str(b.id), "asset_ids": [str(ws.id)]},
    )
    assert assigned_b.status_code == 200, assigned_b.text

    blocked_c = client.post(
        f"{API}/dashboard/resource-planning/packages/{package_id}/assign",
        headers=auth_headers, json={"user_id": str(c.id), "asset_ids": [str(ws.id)]},
    )
    assert blocked_c.status_code == 409, blocked_c.text
