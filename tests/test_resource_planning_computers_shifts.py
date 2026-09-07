"""Computer assignment display consistency + rotation sequence resolution."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import Asset, AssetAssignment, AssetType, Computer
from app.models.models import User
from app.services import it_asset_service
from app.services import it_computer_reconciliation_service as recon
from app.services import resource_shift_service as svc
from tests.conftest import IDS


def _ensure_desktop_type(session) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == "DESKTOP"))
    if existing:
        return existing
    row = AssetType(
        id=uuid4(),
        code="DESKTOP",
        name="Desktop",
        category="computer",
        is_active=True,
    )
    session.add(row)
    session.commit()
    return row


def test_orphan_assigned_status_repaired(session, auth_headers, client):
    at = _ensure_desktop_type(session)
    asset = it_asset_service.create_asset(
        session,
        actor=session.get(User, IDS["user_admin"]),
        asset_type_id=at.id,
        asset_number=f"IT-TEST-{uuid4().hex[:6].upper()}",
        commit=True,
    )
    # Simulate bad import: status assigned with no open assignment
    asset.status = "assigned"
    session.add(asset)
    session.commit()

    computer = Computer(
        id=uuid4(),
        asset_id=asset.id,
        computer_name=f"ProengTest{uuid4().hex[:4]}",
        ram_gb=64,
    )
    session.add(computer)
    session.commit()

    report = recon.computer_data_quality_report(session)
    assert report["assigned_without_employee"] >= 1

    result = recon.repair_orphan_assigned_status(session, commit=True)
    assert result["repaired_count"] >= 1
    session.refresh(asset)
    assert asset.status == "available"

    listed = client.get(
        "/api/v1/it/computers",
        headers=auth_headers,
        params={"page_size": 200},
    )
    assert listed.status_code == 200, listed.text
    body = next(item for item in listed.json()["items"] if item["id"] == str(computer.id))
    assert body["status"] == "available"
    assert body["assigned_to_name"] is None
    assert "status_assigned_without_employee" not in (body.get("data_quality_flags") or [])


def test_assigned_computer_resolves_employee_team(session, auth_headers, client):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    assignee = session.get(User, IDS["user_anurag"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-OK-{uuid4().hex[:6].upper()}",
        location="Bangalore",
        commit=True,
    )
    it_asset_service.assign_asset(session, asset, user_id=assignee.id, by_user=admin, commit=True)
    computer = Computer(
        id=uuid4(),
        asset_id=asset.id,
        computer_name=f"ProengOK{uuid4().hex[:4]}",
        ram_gb=32,
    )
    session.add(computer)
    session.commit()

    listed = client.get(
        "/api/v1/it/computers",
        headers=auth_headers,
        params={"page_size": 200},
    )
    assert listed.status_code == 200, listed.text
    body = next(item for item in listed.json()["items"] if item["id"] == str(computer.id))
    assert body["status"] == "assigned"
    assert body["assigned_to_user_id"] == str(assignee.id)
    assert body["assigned_to_name"]
    assert body["location"] == "Bangalore"
    assert body["ram_gb"] == 32


def test_rotation_sequence_cycles_shifts(session):
    shifts = {s.code: s for s in svc.list_shifts(session, active_only=True)}
    first = shifts["FIRST"]
    second = shifts["SECOND"]
    start = date(2026, 9, 7)
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_anurag"],
            "shift_id": first.id,
            "assignment_type": "rotational",
            "rotation_pattern": "custom",
            "rotation_sequence": [str(first.id), str(second.id)],
            "slot_days": 7,
            "effective_from": start,
            "end_date_existing": True,
        },
    )
    assert svc.get_employee_shift(session, IDS["user_anurag"], start).code == "FIRST"
    assert svc.get_employee_shift(session, IDS["user_anurag"], start + timedelta(days=6)).code == "FIRST"
    assert svc.get_employee_shift(session, IDS["user_anurag"], start + timedelta(days=7)).code == "SECOND"
    assert svc.get_employee_shift(session, IDS["user_anurag"], start + timedelta(days=13)).code == "SECOND"
    assert svc.get_employee_shift(session, IDS["user_anurag"], start + timedelta(days=14)).code == "FIRST"

    nxt = svc.next_employee_shift(session, IDS["user_anurag"], after_date=start)
    assert nxt is not None
    assert nxt["next_change_date"] == start + timedelta(days=7)
    assert nxt["next_shift"].code == "SECOND"


def test_shift_overview_and_board_api(client, auth_headers, session):
    shifts = {s.code: s for s in svc.list_shifts(session, active_only=True)}
    svc.assign_shift(
        session,
        {
            "user_id": IDS["user_binil"],
            "shift_id": shifts["GENERAL"].id,
            "assignment_type": "permanent",
            "effective_from": date(2026, 1, 1),
            "end_date_existing": True,
        },
    )
    overview = client.get("/api/v1/resource-planning/shifts/overview", headers=auth_headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert "by_shift" in body
    assert body["total_employees"] >= 1

    board = client.get("/api/v1/resource-planning/shifts/board", headers=auth_headers)
    assert board.status_code == 200, board.text
    assert "columns" in board.json()
