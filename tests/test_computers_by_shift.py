"""Computers by shift + shared-desk peer enrichment."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.it_operations import AssetType, Computer
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service
from app.services import it_computer_reconciliation_service as recon
from app.services import it_computer_shift_service as shift_computers
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


def test_computers_by_shift_buckets_open_and_assigned(session, auth_headers, client):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    assert first is not None

    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    designer = session.get(User, IDS["user_binil"])

    open_asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-OPEN-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    session.add(
        Computer(id=uuid4(), asset_id=open_asset.id, computer_name=f"OpenPC{uuid4().hex[:3]}")
    )

    assigned_asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-ASG-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    session.add(
        Computer(
            id=uuid4(),
            asset_id=assigned_asset.id,
            computer_name=f"ShiftPC{uuid4().hex[:3]}",
        )
    )
    session.commit()
    it_asset_service.assign_asset(
        session,
        assigned_asset,
        by_user=admin,
        user_id=designer.id,
        assigned_date=date.today(),
        commit=True,
    )
    shifts.assign_shift(
        session,
        {
            "user_id": designer.id,
            "shift_id": first.id,
            "assignment_type": "permanent",
            "effective_from": date.today() - timedelta(days=1),
        },
        commit=True,
    )

    report = shift_computers.computers_by_shift(session, on_date=date.today())
    assert report["summary"]["open"] >= 1
    first_section = next(s for s in report["shifts"] if s["shift_code"] == "FIRST")
    assert first_section["assigned_count"] >= 1
    assert any(c["computer_name"].startswith("ShiftPC") for c in first_section["computers"])

    api = client.get("/api/v1/dashboard/resource-planning/computers-by-shift", headers=auth_headers)
    assert api.status_code == 200
    assert "shifts" in api.json()


def test_last_used_by_and_shared_candidate(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    designer = session.get(User, IDS["user_binil"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-SHR-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    session.add(Computer(id=uuid4(), asset_id=asset.id, computer_name=f"Share{uuid4().hex[:3]}"))
    session.commit()

    it_asset_service.assign_asset(
        session,
        asset,
        by_user=admin,
        user_id=admin.id,
        assigned_date=date.today() - timedelta(days=30),
        commit=True,
    )
    it_asset_service.return_asset(
        session,
        asset,
        by_user=admin,
        returned_date=date.today() - timedelta(days=10),
        commit=True,
    )
    it_asset_service.assign_asset(
        session,
        asset,
        by_user=admin,
        user_id=designer.id,
        assigned_date=date.today() - timedelta(days=5),
        commit=True,
    )

    prev_id, prev_name = shift_computers.last_used_by(session, asset.id)
    assert prev_id == admin.id
    assert prev_name

    computer = session.scalar(
        select(Computer)
        .options(selectinload(Computer.asset))
        .where(Computer.asset_id == asset.id)
    )
    resolved = recon.resolve_computer_display(session, computer)
    assert resolved["is_shared_candidate"] is True
    assert resolved["previous_user_id"] == str(admin.id)
