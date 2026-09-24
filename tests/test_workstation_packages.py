"""Core acceptance: shared workstation package across First/Second shifts."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import AssetType
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service
from app.services import resource_shift_service as shifts
from app.services import workstation_package_service as packages
from tests.conftest import IDS


def _type(session, code: str, name: str, category: str) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == code))
    if existing:
        return existing
    row = AssetType(id=uuid4(), code=code, name=name, category=category, is_active=True)
    session.add(row)
    session.commit()
    return row


def test_shared_package_first_second_general_conflict(session):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    general = session.scalar(select(ResourceShift).where(ResourceShift.code == "GENERAL"))
    assert first and second and general

    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    mouse3d = _type(session, "3DMOUSE", "3D Mouse", "peripheral")

    admin = session.get(User, IDS["user_admin"])
    anurag = session.get(User, IDS["user_anurag"])
    binil = session.get(User, IDS["user_binil"])
    ranjith = session.get(User, IDS["user_ranjith"])

    computer = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    mon1 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    mon2 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    mouse = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=mouse3d.id, asset_number=f"3DM-{uuid4().hex[:4].upper()}", commit=True
    )

    package = packages.create_package(
        session,
        actor=admin,
        code=f"PKG-{computer.asset_number}",
        name=f"Package {computer.asset_number}",
        primary_computer_asset_id=computer.id,
        computer_type="ENG_WS",
        members=[
            {"asset_id": mon1.id, "role": "PRIMARY_MONITOR"},
            {"asset_id": mon2.id, "role": "SECONDARY_MONITOR"},
            {"asset_id": mouse.id, "role": "3D_MOUSE", "is_required": False},
        ],
        commit=True,
    )

    for shift in (first, second, general):
        avail = packages.package_shift_availability(
            session, package, shift_id=shift.id, on_date=date.today()
        )
        assert avail["status"] == "AVAILABLE", shift.code

    packages.assign_package(
        session,
        package,
        actor=admin,
        user_id=anurag.id,
        shift_id=first.id,
        commit=True,
    )
    packages.assign_package(
        session,
        package,
        actor=admin,
        user_id=binil.id,
        shift_id=second.id,
        commit=True,
    )

    members = packages.active_members(session, package.id)
    assert len(members) == 4
    assert {m.asset_id for m in members} == {computer.id, mon1.id, mon2.id, mouse.id}

    first_avail = packages.package_shift_availability(
        session, package, shift_id=first.id, on_date=date.today()
    )
    second_avail = packages.package_shift_availability(
        session, package, shift_id=second.id, on_date=date.today()
    )
    general_avail = packages.package_shift_availability(
        session, package, shift_id=general.id, on_date=date.today()
    )
    assert first_avail["status"] == "ASSIGNED"
    assert second_avail["status"] == "ASSIGNED"
    assert general_avail["status"] == "CONFLICT"

    found = packages.find_available_packages(
        session,
        on_date=date.today(),
        shift_id=second.id,
        computer_type="ENG_WS",
        monitor_quantity=2,
        mouse_3d_required=True,
    )
    exact_ids = {row["id"] for row in found["exact_matches"]}
    assert str(package.id) not in exact_ids

    computer2 = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    mon3 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    mon4 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    mouse2 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=mouse3d.id, asset_number=f"3DM-{uuid4().hex[:4].upper()}", commit=True
    )
    free_pkg = packages.create_package(
        session,
        actor=admin,
        code=f"PKG-{computer2.asset_number}",
        name="Free eng ws",
        primary_computer_asset_id=computer2.id,
        computer_type="ENG_WS",
        members=[
            {"asset_id": mon3.id, "role": "PRIMARY_MONITOR"},
            {"asset_id": mon4.id, "role": "SECONDARY_MONITOR"},
            {"asset_id": mouse2.id, "role": "3D_MOUSE"},
        ],
        commit=True,
    )
    found2 = packages.find_available_packages(
        session,
        on_date=date.today(),
        shift_id=second.id,
        computer_type="ENG_WS",
        monitor_quantity=2,
        mouse_3d_required=True,
    )
    assert str(free_pkg.id) in {row["id"] for row in found2["exact_matches"]}

    with pytest.raises(ProTrackValidationError) as exc:
        packages.assign_package(
            session,
            package,
            actor=admin,
            user_id=ranjith.id,
            shift_id=general.id,
            commit=False,
        )
    assert exc.value.status_code == 409


def test_find_partial_match_insufficient_monitors(session):
    shifts.ensure_company_standard_shifts(session)
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    admin = session.get(User, IDS["user_admin"])
    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    computer = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    mon = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    pkg = packages.create_package(
        session,
        actor=admin,
        code=f"PKG-{computer.asset_number}",
        name="One monitor only",
        primary_computer_asset_id=computer.id,
        computer_type="ENG_WS",
        members=[{"asset_id": mon.id, "role": "PRIMARY_MONITOR"}],
        commit=True,
    )
    found = packages.find_available_packages(
        session,
        on_date=date.today(),
        shift_id=second.id,
        computer_type="ENG_WS",
        monitor_quantity=2,
        mouse_3d_required=False,
    )
    assert str(pkg.id) not in {r["id"] for r in found["exact_matches"]}
    assert str(pkg.id) in {r["id"] for r in found["partial_matches"]}


def test_asset_inventory_shows_shift_availability_from_virtual_seat(session):
    """Asset inventory enrichment must use Virtual Seat assignments, not RP employee shift."""
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    general = session.scalar(select(ResourceShift).where(ResourceShift.code == "GENERAL"))
    admin = session.get(User, IDS["user_admin"])
    anurag = session.get(User, IDS["user_anurag"])
    binil = session.get(User, IDS["user_binil"])

    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    computer = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    mon1 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )
    mon2 = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor.id, asset_number=f"MON-{uuid4().hex[:4].upper()}", commit=True
    )

    package = packages.create_package(
        session,
        actor=admin,
        code=f"VSEAT-{computer.asset_number}",
        name="Core acceptance seat",
        primary_computer_asset_id=computer.id,
        computer_type="ENG_WS",
        members=[
            {"asset_id": mon1.id, "role": "PRIMARY_MONITOR"},
            {"asset_id": mon2.id, "role": "SECONDARY_MONITOR"},
        ],
        commit=True,
    )
    packages.assign_package(
        session, package, actor=admin, user_id=anurag.id, shift_id=first.id, commit=True
    )
    packages.assign_package(
        session, package, actor=admin, user_id=binil.id, shift_id=second.id, commit=True
    )

    for asset in (computer, mon1, mon2):
        enrich = packages.inventory_availability_for_asset(session, asset)
        assert enrich["virtual_seat_code"] == package.code
        by_code = {r["shift_code"]: r for r in enrich["shift_availability"]}
        assert by_code[first.code]["status"] == "ASSIGNED"
        assert by_code[second.code]["status"] == "ASSIGNED"
        assert by_code[general.code]["status"] == "CONFLICT"
        assert enrich["is_shared"] is True

    grouped = packages.grouped_by_user(session)
    codes = {(g["user_id"], g["virtual_seat_code"]) for g in grouped}
    assert (str(anurag.id), package.code) in codes
    assert (str(binil.id), package.code) in codes
    shared_rows = [g for g in grouped if g["virtual_seat_code"] == package.code]
    assert all(g["shared"] for g in shared_rows)

    # Filter: available in First Shift must exclude this seat's computer
    enrich_map = packages.batch_inventory_availability(session, [computer])
    assert not packages.asset_matches_availability_filter(
        enrich_map[computer.id],
        availability_shift_id=first.id,
        availability_status="AVAILABLE",
    )
    assert packages.asset_matches_availability_filter(
        enrich_map[computer.id],
        availability_shift_id=first.id,
        availability_status="ASSIGNED",
    )
