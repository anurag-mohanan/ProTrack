"""Floating license peak-by-shift + parent/child transfer cascade."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import AssetType, SoftwareCatalog, SoftwareLicensePool
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, resource_it_gap_service
from app.services import resource_shift_service as shifts
from app.models.it_operations import EmployeeSoftwareRequirement
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


def test_floating_peak_uses_shift_overlap_not_headcount(session):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    assert first and second

    binil = session.get(User, IDS["user_binil"])
    anurag = session.get(User, IDS["user_anurag"])
    assert binil and anurag

    today = date.today()
    for user, shift in ((binil, first), (anurag, second)):
        shifts.assign_shift(
            session,
            {
                "user_id": user.id,
                "shift_id": shift.id,
                "assignment_type": "permanent",
                "effective_from": today - timedelta(days=3),
                "end_date_existing": True,
            },
            commit=True,
        )

    software = SoftwareCatalog(
        id=uuid4(),
        name=f"FloatCAD-{uuid4().hex[:4]}",
        is_active=True,
    )
    session.add(software)
    session.flush()
    session.add(
        SoftwareLicensePool(
            id=uuid4(),
            software_id=software.id,
            seat_count=1,
            license_type="floating",
        )
    )
    for user in (binil, anurag):
        session.add(
            EmployeeSoftwareRequirement(
                id=uuid4(),
                user_id=user.id,
                software_id=software.id,
                requirement_level="required",
            )
        )
    session.commit()

    gaps = resource_it_gap_service.get_resource_gaps(session, on_date=today)
    demand = {row["software_id"]: row for row in gaps["license_demand"]}
    assert software.id in demand
    row = demand[software.id]
    assert row["is_floating"] is True
    assert row["required_headcount"] >= 2
    # First and Second do not overlap → peak should be 1, not headcount.
    assert row["peak_estimate"] == 1
    assert row["seat_shortfall"] == 0


def test_parent_child_transfer_cascade(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    binil = session.get(User, IDS["user_binil"])
    anurag = session.get(User, IDS["user_anurag"])

    parent = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-PAR-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    child = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-CHD-{uuid4().hex[:5].upper()}",
        commit=False,
    )
    child.parent_asset_id = parent.id
    session.add(child)
    session.commit()

    it_asset_service.assign_asset(
        session, parent, by_user=admin, user_id=binil.id, commit=True
    )
    it_asset_service.assign_asset(
        session, child, by_user=admin, user_id=binil.id, commit=True
    )

    children = it_asset_service.list_child_assets(session, parent.id)
    assert len(children) == 1

    it_asset_service.transfer_asset(
        session,
        parent,
        to_user_id=anurag.id,
        by_user=admin,
        include_children=True,
        commit=True,
    )

    parent_open = it_asset_service.get_current_assignment(session, parent.id)
    child_open = it_asset_service.get_current_assignment(session, child.id)
    assert parent_open is not None and parent_open.assigned_to_user_id == anurag.id
    assert child_open is not None and child_open.assigned_to_user_id == anurag.id


def test_return_assets_for_user_on_exit(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    binil = session.get(User, IDS["user_binil"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-EXIT-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    it_asset_service.assign_asset(
        session, asset, by_user=admin, user_id=binil.id, commit=True
    )
    returned = it_asset_service.return_assets_for_user(
        session, user_id=binil.id, by_user=admin, commit=True
    )
    assert len(returned) >= 1
    assert it_asset_service.get_current_assignment(session, asset.id) is None
