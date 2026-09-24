"""IT provisioning onboarding + shared workstation time-overlap tests."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import AssetType, Computer, SoftwareCatalog
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service
from app.services import it_provisioning_service as provisioning
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


def _ensure_software(session, name: str) -> SoftwareCatalog:
    existing = session.scalar(select(SoftwareCatalog).where(SoftwareCatalog.name == name))
    if existing:
        return existing
    row = SoftwareCatalog(
        id=uuid4(),
        name=name,
        vendor="Test",
        is_active=True,
    )
    session.add(row)
    session.commit()
    return row


def test_hire_creates_provisioning_request_and_ticket(session):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    assert first

    admin = session.get(User, IDS["user_admin"])
    nx = _ensure_software(session, "Siemens NX")
    cimatron = _ensure_software(session, "Cimatron")
    teams = _ensure_software(session, "Microsoft Teams")
    zoho = _ensure_software(session, "Zoho Mail")

    # Use a dedicated user so we do not clash with fixtures
    emp = User(
        id=uuid4(),
        role_id=IDS["role_designer"],
        email=f"test.designer.{uuid4().hex[:6]}@prosohm.test",
        password_hash="x",
        first_name="Test",
        last_name="Engineering Designer",
        designation="Engineering Designer",
        joining_date=date.today() + timedelta(days=7),
        is_active=True,
    )
    session.add(emp)
    session.commit()

    request = provisioning.create_provisioning_for_user(
        session,
        user=emp,
        created_by=admin,
        shift_id=first.id,
        hardware={
            "computer_required": True,
            "computer_type": "ENG_WS",
            "monitor_quantity": 2,
            "mouse_3d_required": True,
            "mouse_3d_is_required": True,
        },
        software_lines=[
            {"software_id": nx.id, "license_required": True},
            {"software_id": cimatron.id, "license_required": True},
            {"software_id": teams.id, "license_required": True},
            {"software_id": zoho.id, "license_required": True},
        ],
        commit=True,
    )

    assert request.ticket_id is not None
    assert request.hardware is not None
    assert request.hardware.computer_type == "ENG_WS"
    assert request.hardware.monitor_quantity == 2
    assert request.hardware.mouse_3d_required is True
    sw = provisioning.software_requirements_for_request(session, request.id)
    assert len(sw) == 4
    readiness = provisioning.onboarding_readiness(session, emp.id)
    assert readiness["overall"] in {"PARTIALLY_READY", "NOT_STARTED", "READY"}
    assert readiness["provisioning_request_id"] == str(request.id)


def test_onboarding_software_cap(session):
    admin = session.get(User, IDS["user_admin"])
    emp = session.get(User, IDS["user_anurag"])
    softwares = []
    for i in range(6):
        softwares.append(_ensure_software(session, f"Cap Soft {i}"))
    with pytest.raises(ProTrackValidationError):
        provisioning.create_provisioning_for_user(
            session,
            user=emp,
            created_by=admin,
            hardware={"computer_required": False},
            software_lines=[{"software_id": s.id} for s in softwares],
            commit=False,
        )


def test_shared_desk_time_overlap_blocked_and_override(session):
    shifts.ensure_company_standard_shifts(session)
    first = session.scalar(select(ResourceShift).where(ResourceShift.code == "FIRST"))
    second = session.scalar(select(ResourceShift).where(ResourceShift.code == "SECOND"))
    general = session.scalar(select(ResourceShift).where(ResourceShift.code == "GENERAL"))
    assert first and second and general

    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    anurag = session.get(User, IDS["user_anurag"])
    binil = session.get(User, IDS["user_binil"])
    ranjith = session.get(User, IDS["user_ranjith"])

    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    session.add(Computer(id=uuid4(), asset_id=asset.id, computer_name=f"WS{uuid4().hex[:3]}"))
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

    util = provisioning.derive_computer_utilization(session, asset, open_assignments=opens)
    assert util["active_users"] == 2
    assert util["active_shifts"] == 2

    # GENERAL overlaps FIRST (and SECOND) → conflict
    with pytest.raises(ProTrackValidationError) as exc:
        it_asset_service.assign_asset(
            session,
            asset,
            by_user=admin,
            user_id=ranjith.id,
            shift_id=general.id,
            assigned_date=date.today(),
            commit=False,
        )
    assert "already assigned during part" in str(exc.value.detail).lower() or "scheduled shift" in str(
        exc.value.detail
    ).lower()
    assert exc.value.status_code == 409

    # Override with reason allowed
    forced = it_asset_service.assign_asset(
        session,
        asset,
        by_user=admin,
        user_id=ranjith.id,
        shift_id=general.id,
        assigned_date=date.today(),
        force_override=True,
        override_reason="Authorized temporary overlap for migration",
        commit=True,
    )
    assert forced.override_reason
    assert len(it_asset_service.list_open_assignments(session, asset.id)) == 3


def test_shift_windows_overlap_helpers():
    first = ResourceShift(
        id=uuid4(),
        code="FIRST",
        name="First",
        start_time="06:00",
        end_time="14:00",
        is_overnight=False,
        is_active=True,
    )
    second = ResourceShift(
        id=uuid4(),
        code="SECOND",
        name="Second",
        start_time="14:00",
        end_time="22:00",
        is_overnight=False,
        is_active=True,
    )
    general = ResourceShift(
        id=uuid4(),
        code="GENERAL",
        name="General",
        start_time="09:00",
        end_time="18:00",
        is_overnight=False,
        is_active=True,
    )
    assert not provisioning.shift_windows_overlap(first, second)
    assert provisioning.shift_windows_overlap(first, general)
    assert provisioning.shift_windows_overlap(second, general)
