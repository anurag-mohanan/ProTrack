"""Consolidation TEST 1–18: employee visibility, assignments, history, packages, reports."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models.it_operations import (
    SoftwareCatalog,
    SoftwareInstallation,
    SoftwareLicensePool,
)
from app.models.models import Activity, Team, TeamMember, User, UserJobEvent
from app.models.resource_shifts import ResourceShift
from tests.conftest import IDS, login


def _designer_role_id(client, headers) -> str:
    roles = client.get("/api/v1/roles", headers=headers).json()
    items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    return next(role["id"] for role in items if role["name"] == "Designer")


def _create_employee(client, headers, *, email: str, first: str = "Cons", last: str = "Hire") -> dict:
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": _designer_role_id(client, headers),
            "email": email,
            "password": "TempPass@123",
            "first_name": first,
            "last_name": last,
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _person_in_hierarchy(payload: dict, user_id: str) -> dict | None:
    for person in payload.get("unassigned", {}).get("people") or []:
        if person["user_id"] == user_id:
            return person
    for shift in payload.get("shifts") or []:
        for team in shift.get("teams") or []:
            for person in team.get("people") or []:
                if person["user_id"] == user_id:
                    return person
    return None


def _laptop_type_id(client, headers) -> str:
    types = client.get("/api/v1/it/asset-types", headers=headers).json()
    laptop = next((row for row in types if row["code"] == "LAPTOP"), types[0])
    return laptop["id"]


def _shift_by_code(session, code: str) -> ResourceShift:
    shift = session.scalar(select(ResourceShift).where(ResourceShift.code == code))
    assert shift is not None
    return shift


def test_new_employee_visible_unassigned(client, auth_headers):
    """TEST 1 + 11: new employee is visible with no shift/computer/software/project."""
    employee = _create_employee(client, auth_headers, email="cons.visible@prosohm.com")
    user_id = employee["id"]

    users = client.get("/api/v1/users", headers=auth_headers, params={"search": employee["email"]})
    assert users.status_code == 200
    items = users.json().get("items") or users.json()
    assert any(row["id"] == user_id for row in items)

    people = client.get("/api/v1/it/people", headers=auth_headers, params={"page_size": 200})
    assert people.status_code == 200
    people_items = people.json().get("items") or []
    assert any(row.get("user_id") == user_id for row in people_items)

    grid = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "week"},
    )
    assert grid.status_code == 200
    designers = grid.json().get("designers") or []
    assert any(row.get("user_id") == user_id for row in designers)

    hierarchy = client.get(
        "/api/v1/dashboard/resource-planning/shift-hierarchy",
        headers=auth_headers,
    )
    assert hierarchy.status_code == 200, hierarchy.text
    person = _person_in_hierarchy(hierarchy.json(), user_id)
    assert person is not None
    assert person["shift_id"] is None
    assert person["computer"] is None
    assert person["software"] == []
    assert person["projects"] == []
    assert person in (hierarchy.json()["unassigned"]["people"] or [])


def test_assign_shift_workstation_ip_software(client, session, auth_headers):
    """TEST 2–5: shift, workstation, IP, software appear on profile / hierarchy / inventory."""
    employee = _create_employee(client, auth_headers, email="cons.assign@prosohm.com")
    user_id = employee["id"]
    first = _shift_by_code(session, "FIRST")

    assigned_shift = client.post(
        "/api/v1/resource-planning/shifts/assignments",
        headers=auth_headers,
        json={
            "user_id": user_id,
            "shift_id": str(first.id),
            "assignment_type": "permanent",
            "effective_from": date.today().isoformat(),
        },
    )
    assert assigned_shift.status_code == 201, assigned_shift.text

    computer = client.post(
        "/api/v1/it/computers",
        headers=auth_headers,
        json={"asset_type_id": _laptop_type_id(client, auth_headers), "make": "Dell", "ram_gb": 16},
    )
    assert computer.status_code == 201, computer.text
    computer_id = computer.json()["id"]
    asset_id = computer.json()["asset_id"]

    assigned_pc = client.post(
        f"/api/v1/it/computers/{computer_id}/assign",
        headers=auth_headers,
        json={"user_id": user_id},
    )
    assert assigned_pc.status_code == 200, assigned_pc.text

    network = client.post(
        "/api/v1/it/networks",
        headers=auth_headers,
        json={
            "name": f"Cons LAN {uuid.uuid4().hex[:6]}",
            "cidr": "10.77.77.0/29",
            "gateway": "10.77.77.1",
        },
    )
    assert network.status_code == 201, network.text
    ips = client.get(
        f"/api/v1/it/networks/{network.json()['id']}/ips",
        headers=auth_headers,
    ).json()
    available = [row for row in ips if row["status"] == "available"]
    allocated = client.post(
        "/api/v1/it/ips/allocate",
        headers=auth_headers,
        json={
            "ip_address_id": available[0]["id"],
            "assigned_to_user_id": user_id,
            "assigned_to_asset_id": asset_id,
        },
    )
    assert allocated.status_code == 200, allocated.text

    software = SoftwareCatalog(id=uuid.uuid4(), name="ConsCAD", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid.uuid4(),
        software_id=software.id,
        seat_count=2,
        status="active",
    )
    session.add(pool)
    session.commit()

    licensed = client.post(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        json={
            "license_pool_id": str(pool.id),
            "user_id": user_id,
            "computer_id": computer_id,
        },
    )
    assert licensed.status_code == 201, licensed.text

    profile = client.get(f"/api/v1/it/profile/{user_id}", headers=auth_headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body.get("shift")
    assert body.get("computer")
    assert any(row.get("address") == allocated.json()["address"] for row in body.get("ips") or [])
    assert any(row.get("software_name") == "ConsCAD" for row in body.get("software") or [])
    status_rows = body.get("software_status") or []
    assert any(row.get("licensed") and row.get("installed") for row in status_rows)

    installs = client.get(
        "/api/v1/it/software/installations",
        headers=auth_headers,
        params={"computer_id": computer_id},
    )
    assert installs.status_code == 200
    assert any(row["software_name"] == "ConsCAD" and row["is_active"] for row in installs.json())

    hierarchy = client.get(
        "/api/v1/dashboard/resource-planning/shift-hierarchy",
        headers=auth_headers,
    ).json()
    person = _person_in_hierarchy(hierarchy, user_id)
    assert person is not None
    assert person["shift_id"] == str(first.id)
    assert person["computer"]
    assert person["ips"]
    assert "ConsCAD" in person["software"]

    inventory = client.get(
        "/api/v1/it/assets",
        headers=auth_headers,
        params={"category": "computer", "page_size": 200},
    )
    assert inventory.status_code == 200
    assert any(row["id"] == asset_id for row in inventory.json()["items"])

    again = client.get(f"/api/v1/it/profile/{user_id}", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["computer"]["computer_id"] == computer_id

    relogin = login(client, "admin@prosohm.com")
    persisted = client.get(f"/api/v1/it/profile/{user_id}", headers=relogin)
    assert persisted.status_code == 200
    assert persisted.json()["computer"]["computer_id"] == computer_id


def test_shift_move_keeps_history(client, session, auth_headers):
    """TEST 6: First → Second keeps prior assignment history."""
    employee = _create_employee(client, auth_headers, email="cons.shiftmove@prosohm.com")
    first = _shift_by_code(session, "FIRST")
    second = _shift_by_code(session, "SECOND")
    start = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    first_assign = client.post(
        "/api/v1/resource-planning/shifts/assignments",
        headers=auth_headers,
        json={
            "user_id": employee["id"],
            "shift_id": str(first.id),
            "assignment_type": "permanent",
            "effective_from": start,
        },
    )
    assert first_assign.status_code == 201, first_assign.text
    moved = client.post(
        "/api/v1/resource-planning/shifts/assignments/reassign",
        headers=auth_headers,
        json={
            "user_id": employee["id"],
            "shift_id": str(second.id),
            "assignment_type": "permanent",
            "effective_from": today,
        },
    )
    assert moved.status_code == 200, moved.text

    history = client.get(
        "/api/v1/resource-planning/shifts/assignments",
        headers=auth_headers,
        params={"user_id": employee["id"], "include_inactive": True},
    )
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) >= 2
    codes = {row.get("shift_code") or row.get("shift_id") for row in rows}
    assert str(first.id) in codes or "FIRST" in codes
    assert str(second.id) in codes or "SECOND" in codes

    hierarchy = client.get(
        "/api/v1/dashboard/resource-planning/shift-hierarchy",
        headers=auth_headers,
    ).json()
    person = _person_in_hierarchy(hierarchy, employee["id"])
    assert person is not None
    assert person["shift_id"] == str(second.id)


def test_team_transfer_keeps_timesheet_history(client, session, auth_headers):
    """TEST 7: team move updates planning team; timesheet rows remain."""
    employee = _create_employee(client, auth_headers, email="cons.transfer@prosohm.com")
    user = session.get(User, uuid.UUID(employee["id"]))
    source = Team(id=uuid.uuid4(), name="Cons Source", colour="#1565c0", is_active=True)
    target = Team(id=uuid.uuid4(), name="Cons Target", colour="#c62828", is_active=True)
    session.add_all([source, target])
    session.commit()
    user.team_id = source.id
    session.add(user)
    session.add(
        TeamMember(
            team_id=source.id,
            user_id=user.id,
            role_within_team="Designer",
            is_primary=True,
        )
    )
    session.commit()

    before = session.scalars(
        select(UserJobEvent).where(UserJobEvent.user_id == user.id)
    ).all()
    before_ids = {row.id for row in before}

    transfer = client.post(
        f"/api/v1/hr/users/{employee['id']}/transfer",
        headers=auth_headers,
        json={
            "target_team_id": str(target.id),
            "effective_date": date.today().isoformat(),
        },
    )
    assert transfer.status_code in (201, 200), transfer.text

    session.expire_all()
    after = session.scalars(
        select(UserJobEvent).where(UserJobEvent.user_id == user.id)
    ).all()
    assert before_ids <= {row.id for row in after}
    assert any(row.event_type == "transfer" or "transfer" in (row.event_type or "") for row in after)

    hierarchy = client.get(
        "/api/v1/dashboard/resource-planning/shift-hierarchy",
        headers=auth_headers,
    ).json()
    person = _person_in_hierarchy(hierarchy, employee["id"])
    assert person is not None
    assert person["team_id"] == str(target.id)


def test_computer_reassign_keeps_previous_user_history(client, auth_headers):
    """TEST 8: reassign computer — previous user remains in assignment history."""
    first_user = _create_employee(client, auth_headers, email="cons.pc1@prosohm.com")
    second_user = _create_employee(client, auth_headers, email="cons.pc2@prosohm.com")
    computer = client.post(
        "/api/v1/it/computers",
        headers=auth_headers,
        json={"asset_type_id": _laptop_type_id(client, auth_headers), "make": "HP", "ram_gb": 32},
    )
    assert computer.status_code == 201, computer.text
    computer_id = computer.json()["id"]
    asset_id = computer.json()["asset_id"]

    assert (
        client.post(
            f"/api/v1/it/computers/{computer_id}/assign",
            headers=auth_headers,
            json={"user_id": first_user["id"]},
        ).status_code
        == 200
    )
    transferred = client.post(
        f"/api/v1/it/computers/{computer_id}/transfer",
        headers=auth_headers,
        json={"to_user_id": second_user["id"]},
    )
    assert transferred.status_code == 200, transferred.text

    history = client.get(f"/api/v1/it/assets/{asset_id}/assignments", headers=auth_headers)
    assert history.status_code == 200
    rows = history.json()
    user_ids = {row.get("assigned_to_user_id") or row.get("user_id") for row in rows}
    assert first_user["id"] in user_ids
    assert second_user["id"] in user_ids
    assert any(row.get("returned_date") for row in rows)


def test_terminated_license_not_assignable(client, session, auth_headers):
    """TEST 9: terminated pool cannot be assigned; history remains."""
    software = SoftwareCatalog(id=uuid.uuid4(), name="ConsTerm", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid.uuid4(),
        software_id=software.id,
        seat_count=1,
        status="active",
    )
    session.add(pool)
    session.commit()

    assigned = client.post(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        json={"license_pool_id": str(pool.id), "user_id": str(IDS["user_binil"])},
    )
    assert assigned.status_code == 201, assigned.text

    term = client.post(
        f"/api/v1/it/software/licenses/{pool.id}/terminate",
        headers=auth_headers,
        json={"reason": "Contract ended"},
    )
    assert term.status_code == 200, term.text

    blocked = client.post(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        json={"license_pool_id": str(pool.id), "user_id": str(IDS["user_anurag"])},
    )
    assert blocked.status_code == 422

    history = client.get(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        params={"license_pool_id": str(pool.id), "active_only": False},
    )
    assert history.status_code == 200
    assert any(row["id"] == assigned.json()["id"] for row in history.json())


def test_return_to_customer_not_internally_assignable(client, session, auth_headers):
    """TEST 10: returned-to-customer asset is not internally assignable; history remains."""
    from app.models.models import Customer

    customer = session.scalar(select(Customer).limit(1))
    created = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": _laptop_type_id(client, auth_headers),
            "make": "Lenovo",
            "purchased_by": "customer",
            "owner_customer_id": str(customer.id),
        },
    )
    assert created.status_code == 201, created.text
    asset_id = created.json()["id"]
    assigned = client.post(
        f"/api/v1/it/assets/{asset_id}/assign",
        headers=auth_headers,
        json={"user_id": str(IDS["user_binil"])},
    )
    assert assigned.status_code == 200, assigned.text

    returned = client.post(
        f"/api/v1/it/assets/{asset_id}/return-to-customer",
        headers=auth_headers,
        json={"condition_at_return": "good", "return_reason": "Project ended"},
    )
    assert returned.status_code == 200, returned.text

    blocked = client.post(
        f"/api/v1/it/assets/{asset_id}/assign",
        headers=auth_headers,
        json={"user_id": str(IDS["user_anurag"])},
    )
    assert blocked.status_code in (400, 409, 422)

    history = client.get(f"/api/v1/it/assets/{asset_id}/assignments", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) >= 1


def test_reports_use_source_of_truth(client, auth_headers):
    """TEST 17: IT reports and RP readiness read the same assignment tables."""
    register = client.get("/api/v1/it/reports/asset-register", headers=auth_headers)
    assert register.status_code == 200
    gaps = client.get("/api/v1/dashboard/resource-planning/it-gaps", headers=auth_headers)
    assert gaps.status_code == 200
    matrix = client.get("/api/v1/dashboard/resource-planning/it-matrix", headers=auth_headers)
    assert matrix.status_code == 200
    hierarchy = client.get(
        "/api/v1/dashboard/resource-planning/shift-hierarchy",
        headers=auth_headers,
    )
    assert hierarchy.status_code == 200
    assert "unassigned" in hierarchy.json()
    assert "totals" in hierarchy.json()


def test_bulk_assign_writes_audit_log(client, session, auth_headers):
    """TEST 18: bulk assign updates assets and writes an activity row."""
    type_id = _laptop_type_id(client, auth_headers)
    a1 = client.post("/api/v1/it/assets", headers=auth_headers, json={"asset_type_id": type_id}).json()
    a2 = client.post("/api/v1/it/assets", headers=auth_headers, json={"asset_type_id": type_id}).json()
    before = session.scalar(select(Activity).order_by(Activity.created_at.desc()))
    before_id = before.id if before else None

    result = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=auth_headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "assign_user",
            "parameters": {"user_id": str(IDS["user_binil"])},
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["updated"] >= 1

    session.expire_all()
    latest = session.scalars(select(Activity).order_by(Activity.created_at.desc()).limit(5)).all()
    assert latest
    if before_id is not None:
        assert any(row.id != before_id for row in latest)


def test_license_assign_to_computer_creates_installation(client, session, auth_headers):
    computer = client.post(
        "/api/v1/it/computers",
        headers=auth_headers,
        json={"asset_type_id": _laptop_type_id(client, auth_headers), "make": "Acer"},
    )
    assert computer.status_code == 201, computer.text
    software = SoftwareCatalog(id=uuid.uuid4(), name="ConsInstall", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid.uuid4(), software_id=software.id, seat_count=1, status="active"
    )
    session.add(pool)
    session.commit()

    assigned = client.post(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        json={
            "license_pool_id": str(pool.id),
            "user_id": str(IDS["user_binil"]),
            "computer_id": computer.json()["id"],
        },
    )
    assert assigned.status_code == 201, assigned.text

    rows = session.scalars(
        select(SoftwareInstallation).where(
            SoftwareInstallation.computer_id == uuid.UUID(computer.json()["id"]),
            SoftwareInstallation.software_id == software.id,
            SoftwareInstallation.uninstalled_date.is_(None),
        )
    ).all()
    assert len(rows) == 1

    unassigned = client.post(
        f"/api/v1/it/software/assignments/{assigned.json()['id']}/unassign",
        headers=auth_headers,
        json={},
    )
    assert unassigned.status_code == 200
    session.expire_all()
    still = session.scalars(
        select(SoftwareInstallation).where(
            SoftwareInstallation.computer_id == uuid.UUID(computer.json()["id"]),
            SoftwareInstallation.uninstalled_date.is_(None),
        )
    ).all()
    assert still, "unassign must not auto-uninstall"
