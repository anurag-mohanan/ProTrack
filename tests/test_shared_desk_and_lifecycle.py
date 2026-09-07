"""Shared-desk dual occupancy + asset lifecycle history periods."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.it_operations import AssetType, Computer
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service
from app.services import resource_shift_service as shifts
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


def test_shared_desk_two_open_assignments_different_shifts(session):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    assert first and second

    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    binil = session.get(User, IDS["user_binil"])
    anurag = session.get(User, IDS["user_anurag"])

    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-SHARE-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    session.add(Computer(id=uuid4(), asset_id=asset.id, computer_name=f"Desk{uuid4().hex[:3]}"))
    session.commit()

    it_asset_service.assign_asset(
        session,
        asset,
        by_user=admin,
        user_id=anurag.id,
        shift_id=first.id,
        assigned_date=date.today(),
        commit=True,
    )
    it_asset_service.assign_asset(
        session,
        asset,
        by_user=admin,
        user_id=binil.id,
        shift_id=second.id,
        assigned_date=date.today(),
        commit=True,
    )

    opens = it_asset_service.list_open_assignments(session, asset.id)
    assert len(opens) == 2
    session.refresh(asset)
    assert asset.status == "assigned"

    # Same shift second occupant blocked
    try:
        it_asset_service.assign_asset(
            session,
            asset,
            by_user=admin,
            user_id=admin.id,
            shift_id=first.id,
            commit=True,
        )
        assert False, "expected validation error"
    except Exception as exc:
        assert "already has an open assignment for that shift" in str(exc).lower()

    it_asset_service.return_asset(
        session,
        asset,
        by_user=admin,
        shift_id=first.id,
        commit=True,
    )
    assert len(it_asset_service.list_open_assignments(session, asset.id)) == 1
    session.refresh(asset)
    assert asset.status == "assigned"

    it_asset_service.return_asset(
        session,
        asset,
        by_user=admin,
        shift_id=second.id,
        commit=True,
    )
    session.refresh(asset)
    assert asset.status == "available"


def test_ownership_location_status_history_periods(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-HIST-{uuid4().hex[:5].upper()}",
        location="Bangalore",
        commit=True,
    )
    hist = it_asset_service.list_asset_lifecycle_history(session, asset.id)
    assert len(hist["ownership"]) >= 1
    assert len(hist["locations"]) >= 1
    assert len(hist["statuses"]) >= 1
    assert hist["locations"][0]["location"] == "Bangalore"
    assert hist["locations"][0]["effective_to"] is None

    it_asset_service.update_asset(
        session,
        asset,
        actor=admin,
        location="Sybridge Site",
        fields_set={"location"},
        commit=True,
    )
    hist = it_asset_service.list_asset_lifecycle_history(session, asset.id)
    assert len(hist["locations"]) >= 2
    assert hist["locations"][0]["location"] == "Sybridge Site"
    assert hist["locations"][0]["effective_to"] is None
    assert hist["locations"][1]["effective_to"] is not None

    it_asset_service.update_asset(
        session,
        asset,
        actor=admin,
        status="maintenance",
        fields_set={"status"},
        commit=True,
    )
    hist = it_asset_service.list_asset_lifecycle_history(session, asset.id)
    assert hist["statuses"][0]["status"] == "maintenance"


def test_shift_reassign_and_bulk_api(session, auth_headers, client):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    binil = session.get(User, IDS["user_binil"])
    anurag = session.get(User, IDS["user_anurag"])
    assert first and second

    shifts.assign_shift(
        session,
        {
            "user_id": binil.id,
            "shift_id": first.id,
            "assignment_type": "permanent",
            "effective_from": date.today() - timedelta(days=7),
            "end_date_existing": True,
        },
        commit=True,
    )

    moved = shifts.reassign_employee_shift(
        session,
        user_id=binil.id,
        new_shift_id=second.id,
        effective_from=date.today(),
        commit=True,
    )
    assert moved.shift_id == second.id

    created, conflicts = shifts.bulk_reassign_employee_shifts(
        session,
        user_ids=[anurag.id],
        new_shift_id=first.id,
        effective_from=date.today(),
    )
    assert len(created) + len(conflicts) >= 1

    resp = client.post(
        "/api/v1/resource-planning/shifts/assignments/reassign",
        headers=auth_headers,
        json={
            "user_id": str(binil.id),
            "shift_id": str(first.id),
            "effective_from": date.today().isoformat(),
            "assignment_type": "permanent",
        },
    )
    assert resp.status_code in {200, 201}
