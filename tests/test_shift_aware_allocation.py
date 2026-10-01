"""Shift-aware resource allocation: one engine for computers, peripherals, seats and licenses."""

from __future__ import annotations

import sqlite3
import threading
import traceback
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    ResourceReservation,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Activity, User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, it_software_service
from app.services import resource_allocation_engine as engine
from app.services import resource_assignment_service as assignments
from app.services import resource_shift_service as shifts
from app.services import virtual_seat_service as seats
from tests.conftest import IDS, login

API = "/api/v1/it"
TODAY = date.today()


# --- helpers -----------------------------------------------------------------------------


def _type(session, code: str, name: str, category: str) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == code))
    if existing:
        return existing
    row = AssetType(id=uuid4(), code=code, name=name, category=category, is_active=True)
    session.add(row)
    session.commit()
    return row


def _shift(session, code: str) -> ResourceShift:
    shifts.ensure_company_standard_shifts(session)
    row = session.scalar(select(ResourceShift).where(ResourceShift.code == code))
    assert row is not None
    return row


def _users(session):
    return (
        session.get(User, IDS["user_admin"]),
        session.get(User, IDS["user_anurag"]),
        session.get(User, IDS["user_binil"]),
        session.get(User, IDS["user_ranjith"]),
    )


def _computer(session, admin, number: str | None = None, status: str | None = None) -> Asset:
    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=number or f"WS-{uuid4().hex[:6].upper()}",
        computer_type="ENG_WS",
        commit=True,
    )
    if status:
        asset.status = status
        session.commit()
    return asset


def _pool(session, metric: str, seats_owned: int, name: str = "Cimatron") -> SoftwareLicensePool:
    software = SoftwareCatalog(id=uuid4(), name=f"{name}-{uuid4().hex[:4]}", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid4(),
        software_id=software.id,
        seat_count=seats_owned,
        status="active",
        assignment_model=metric,
    )
    session.add(pool)
    session.commit()
    return pool


def _assign(session, asset, user, admin, **kw):
    return it_asset_service.assign_asset(session, asset, user_id=user.id, by_user=admin, **kw)


# --- windows ------------------------------------------------------------------------------


def test_overlap_rule_supports_overnight_windows():
    night = engine.window_from_times("22:00", "06:00")
    assert engine.windows_overlap(night, engine.window_from_times("05:00", "10:00"))
    assert not engine.windows_overlap(night, engine.window_from_times("06:00", "14:00"))
    assert engine.windows_overlap(night, engine.window_from_times("23:00", "23:30"))
    first = engine.window_from_times("06:00", "14:00")
    assert not engine.windows_overlap(first, engine.window_from_times("14:00", "22:00"))
    assert engine.describe_overlap(first, engine.window_from_times("09:00", "18:00")) == "09:00–14:00"


# --- computers (regression 50) ---------------------------------------------------------------


def test_ws001_first_and_second_allowed_general_blocked(client, session, auth_headers):
    admin, a, b, c = _users(session)
    ws = _computer(session, admin)
    first, second, general = _shift(session, "FIRST"), _shift(session, "SECOND"), _shift(session, "GENERAL")

    _assign(session, ws, a, admin, shift_id=first.id)
    _assign(session, ws, b, admin, shift_id=second.id)

    res = client.post(
        f"{API}/assets/{ws.id}/assign",
        headers=auth_headers,
        json={"user_id": str(c.id), "shift_id": str(general.id)},
    )
    assert res.status_code == 409, res.text
    assert "scheduled shift" in res.json()["detail"]

    check = client.post(
        f"{API}/allocation/check",
        headers=auth_headers,
        json={"resource_type": "asset", "resource_id": str(ws.id), "user_id": str(c.id),
              "shift_id": str(general.id)},
    ).json()
    assert check["available"] is False
    assert check["reason_code"] == engine.REASON_TIME_OVERLAP
    overlaps = sorted(x["overlap"] for x in check["conflicting_assignments"])
    assert overlaps == ["09:00–14:00", "14:00–18:00"]

    session.refresh(ws)
    assert ws.status == "assigned"


def test_overnight_custom_window_blocks_overlap_but_allows_adjacent(session):
    admin, a, b, c = _users(session)
    ws = _computer(session, admin)
    _assign(session, ws, a, admin, start_time="22:00", end_time="06:00")

    with pytest.raises(ProTrackValidationError) as exc:
        _assign(session, ws, b, admin, start_time="05:00", end_time="10:00")
    assert exc.value.status_code == 409

    row = _assign(session, ws, c, admin, start_time="06:00", end_time="14:00")
    assert row.start_time == "06:00" and row.end_time == "14:00"


@pytest.mark.parametrize("status", ["maintenance", "retired"])
def test_lifecycle_status_blocks_assignment(session, status):
    admin, a, _b, _c = _users(session)
    ws = _computer(session, admin, status=status)
    req = engine.build_request(session, shift_id=_shift(session, "FIRST").id, user_id=a.id)
    result = engine.evaluate_asset(session, ws, req)
    assert result["status"] == engine.UNAVAILABLE
    assert result["reason_code"] == engine.REASON_LIFECYCLE
    with pytest.raises(ProTrackValidationError):
        _assign(session, ws, a, admin, shift_id=_shift(session, "FIRST").id)


def test_date_ranges_allow_sequential_use_of_same_slot(session):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first = _shift(session, "FIRST")
    _assign(session, ws, a, admin, shift_id=first.id, assigned_date=TODAY,
            planned_end_date=TODAY + timedelta(days=5))

    with pytest.raises(ProTrackValidationError):
        _assign(session, ws, b, admin, shift_id=first.id, assigned_date=TODAY + timedelta(days=3))

    later = _assign(session, ws, b, admin, shift_id=first.id, assigned_date=TODAY + timedelta(days=6))
    assert later.assigned_date == TODAY + timedelta(days=6)
    session.refresh(ws)
    assert ws.status == "assigned"


def test_reservation_blocks_others_and_is_fulfilled_by_its_employee(session):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first = _shift(session, "FIRST")
    res = assignments.create_reservation(
        session, actor=admin, resource_type="asset", resource_id=ws.id, user_id=a.id,
        shift_id=first.id, reason="Joining Monday",
    )

    with pytest.raises(ProTrackValidationError) as exc:
        _assign(session, ws, b, admin, shift_id=first.id)
    assert exc.value.status_code == 409

    _assign(session, ws, a, admin, shift_id=first.id)
    session.refresh(res)
    assert res.status == "FULFILLED"


def test_reservation_release_frees_the_slot(session):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first = _shift(session, "FIRST")
    res = assignments.create_reservation(
        session, actor=admin, resource_type="asset", resource_id=ws.id, reserved_for="New joiner",
        shift_id=first.id,
    )
    assignments.release_reservation(session, res.id, actor=admin, reason="Offer withdrawn")
    _assign(session, ws, b, admin, shift_id=first.id)
    assert session.scalar(
        select(func.count()).select_from(Activity).where(
            Activity.action == ActivityAction.it_reservation_released
        )
    ) >= 1


def test_exclusive_sharing_policy_blocks_second_employee(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    monitor_type = _type(session, "MONITOR", "Monitor", "peripheral")
    policy = client.put(
        f"{API}/allocation/sharing-policy/{monitor_type.id}",
        headers=auth_headers,
        json={"is_shareable": False},
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["shareable"] is False

    mon = it_asset_service.create_asset(
        session, actor=admin, asset_type_id=monitor_type.id,
        asset_number=f"MON-{uuid4().hex[:6]}", commit=True,
    )
    _assign(session, mon, a, admin, shift_id=_shift(session, "FIRST").id)
    with pytest.raises(ProTrackValidationError) as exc:
        _assign(session, mon, b, admin, shift_id=_shift(session, "SECOND").id)
    assert exc.value.status_code == 409

    reset = client.put(
        f"{API}/allocation/sharing-policy/{monitor_type.id}",
        headers=auth_headers,
        json={"is_shareable": None},
    )
    assert reset.status_code == 200 and reset.json()["configured"] is False


def test_override_requires_reason_and_is_audited(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first = _shift(session, "FIRST")
    _assign(session, ws, a, admin, shift_id=first.id)

    same_slot = client.post(
        f"{API}/assets/{ws.id}/assign", headers=auth_headers,
        json={"user_id": str(b.id), "shift_id": str(first.id), "force_override": True,
              "override_reason": "Same slot cannot be forced"},
    )
    assert same_slot.status_code == 409

    missing_reason = client.post(
        f"{API}/assets/{ws.id}/assign", headers=auth_headers,
        json={"user_id": str(b.id), "start_time": "10:00", "end_time": "12:00", "force_override": True},
    )
    assert missing_reason.status_code == 422
    assert "override_reason" in missing_reason.json()["detail"]

    forced = client.post(
        f"{API}/assets/{ws.id}/assign", headers=auth_headers,
        json={"user_id": str(b.id), "start_time": "10:00", "end_time": "12:00",
              "force_override": True, "override_reason": "Temporary cover"},
    )
    assert forced.status_code == 200, forced.text
    row = session.get(AssetAssignment, UUID(forced.json()["id"]))
    assert row.override_reason == "Temporary cover"


def test_legacy_assignment_is_flagged_and_can_be_resolved(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    legacy = AssetAssignment(
        id=uuid4(), asset_id=ws.id, assigned_to_user_id=a.id, assigned_by_user_id=admin.id,
        assigned_date=TODAY - timedelta(days=30),
    )
    session.add(legacy)
    ws.status = "assigned"
    session.commit()

    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")
    req = engine.build_request(session, shift_id=second.id, user_id=b.id)
    blocked = engine.evaluate_asset(session, ws, req)
    assert blocked["reason_code"] == engine.REASON_LEGACY

    review = client.get(f"{API}/allocation/legacy", headers=auth_headers).json()
    entry = next(x for x in review["assignments"] if x["assignment_id"] == str(legacy.id))
    assert entry["status"] == "LEGACY / NEEDS REVIEW"
    assert entry["assigned_date"] == (TODAY - timedelta(days=30)).isoformat()

    resolved = client.post(
        f"{API}/allocation/legacy/{legacy.id}/resolve", headers=auth_headers,
        json={"mode": "shift", "shift_id": str(first.id)},
    )
    assert resolved.status_code == 200, resolved.text
    session.expire_all()
    assert session.get(AssetAssignment, legacy.id).assigned_date == TODAY - timedelta(days=30)
    _assign(session, ws, b, admin, shift_id=second.id)


# --- virtual seats (regression 51) ---------------------------------------------------------------


def test_shared_computer_yields_one_seat_per_shift_without_new_assets(session):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")
    assets_before = session.scalar(select(func.count()).select_from(Asset))

    _assign(session, ws, a, admin, shift_id=first.id)
    _assign(session, ws, b, admin, shift_id=second.id)

    seat_a = next(s for s in seats.seats_for_user(session, a.id) if s["primary"])
    seat_b = next(s for s in seats.seats_for_user(session, b.id) if s["primary"])
    assert seat_a["primary"]["asset_number"] == seat_b["primary"]["asset_number"] == ws.asset_number
    assert seat_a["seat_code"] != seat_b["seat_code"]
    assert session.scalar(select(func.count()).select_from(Asset)) == assets_before
    assert not session.scalar(select(Asset).where(Asset.asset_number == f"{ws.asset_number}-A"))


# --- licenses (regression 49) ----------------------------------------------------------------------


def test_cimatron_floating_one_right_shift_sharing(client, session, auth_headers):
    admin, a, b, c = _users(session)
    pool = _pool(session, "floating", 1)
    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")

    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id,
                                       shift_id=first.id, actor=admin)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id,
                                       shift_id=second.id, actor=admin)

    res = client.post(
        f"{API}/software/assignments", headers=auth_headers,
        json={"license_pool_id": str(pool.id), "user_id": str(c.id), "shift_id": str(first.id)},
    )
    assert res.status_code == 409, res.text
    assert "LICENSE CONCURRENCY CONFLICT" in res.json()["detail"]

    summary = engine.license_summary(session, pool)
    assert summary["metric"] == engine.METRIC_CONCURRENT
    assert summary["authorized_users"] == 2
    assert summary["scheduled_peak"] == 1
    assert summary["compliance_status"] == "FULLY_ALLOCATED"

    schedule = client.get(f"{API}/allocation/schedule/license/{pool.id}", headers=auth_headers).json()
    free = [blk for blk in schedule["blocks"] if blk["available"]]
    assert any(blk["start"] == "22:00" for blk in free)


def test_employee_profile_shows_assignment_windows(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    pool = _pool(session, "floating", 1)
    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")
    _assign(session, ws, a, admin, shift_id=first.id)
    _assign(session, ws, b, admin, shift_id=second.id)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id,
                                       shift_id=first.id, actor=admin)

    res = client.get(f"{API}/profile/{a.id}", headers=auth_headers)
    assert res.status_code == 200, res.text
    rows = {r["resource_type"]: r for r in res.json()["allocations"] if r["resource_id"] in {str(ws.id), str(pool.id)}}
    assert rows["asset"]["times"] == "06:00–14:00"
    assert rows["asset"]["allocation_kind"] == "scheduled"
    assert rows["asset"]["shared_with"] == 1
    assert rows["license"]["allocation_kind"] == "scheduled"
    assert rows["license"]["times"] == "06:00–14:00"


def test_named_user_license_is_not_shared_between_shifts(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "named_user", 1)
    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id,
                                       shift_id=first.id, actor=admin)
    res = client.post(
        f"{API}/software/assignments", headers=auth_headers,
        json={"license_pool_id": str(pool.id), "user_id": str(b.id), "shift_id": str(second.id)},
    )
    assert res.status_code == 422, res.text
    assert "Named User" in res.json()["detail"]


def test_floating_two_rights_allows_two_concurrent_users(session):
    admin, a, b, c = _users(session)
    pool = _pool(session, "floating", 2)
    first = _shift(session, "FIRST")
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id, shift_id=first.id)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id, shift_id=first.id)
    with pytest.raises(ProTrackValidationError) as exc:
        it_software_service.assign_license(session, license_pool_id=pool.id, user_id=c.id,
                                           start_time="13:00", end_time="15:00")
    assert exc.value.status_code == 409


def test_unscheduled_floating_authorization_consumes_no_right(session):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "floating", 1)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id)
    summary = engine.license_summary(session, pool)
    assert summary["authorized_users"] == 2
    assert summary["rights_allocated"] == 0
    assert summary["compliance_status"] == "COMPLIANT"


def test_per_device_license_follows_the_device(session):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "device_bound", 1)
    ws1, ws2 = _computer(session, admin), _computer(session, admin)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id, asset_id=ws1.id)
    with pytest.raises(ProTrackValidationError):
        it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id, asset_id=ws2.id)
    req = engine.build_request(session, user_id=b.id)
    assert engine.evaluate_license(session, pool, req)["reason_code"] == engine.REASON_METRIC


def test_concurrent_checkout_is_limited_by_rights(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "floating", 1)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id)

    out_a = client.post(f"{API}/allocation/licenses/{pool.id}/checkout", headers=auth_headers,
                        json={"user_id": str(a.id)})
    assert out_a.status_code == 201, out_a.text
    out_b = client.post(f"{API}/allocation/licenses/{pool.id}/checkout", headers=auth_headers,
                        json={"user_id": str(b.id)})
    assert out_b.status_code == 409
    assert client.post(f"{API}/allocation/license-sessions/{out_a.json()['id']}/checkin",
                       headers=auth_headers).status_code == 200
    assert client.post(f"{API}/allocation/licenses/{pool.id}/checkout", headers=auth_headers,
                       json={"user_id": str(b.id)}).status_code == 201


def test_metric_change_is_blocked_when_it_would_over_allocate(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "floating", 1)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=a.id,
                                       shift_id=_shift(session, "FIRST").id)
    it_software_service.assign_license(session, license_pool_id=pool.id, user_id=b.id,
                                       shift_id=_shift(session, "SECOND").id)
    res = client.patch(f"{API}/software/licenses/{pool.id}", headers=auth_headers,
                       json={"assignment_model": "named_user"})
    assert res.status_code == 422, res.text
    session.expire_all()
    assert session.get(SoftwareLicensePool, pool.id).assignment_model == "floating"


# --- bulk setup ---------------------------------------------------------------------------------


def _setup_payload(user, shift, lines, **extra):
    return {"user_id": str(user.id), "shift_id": str(shift.id), "lines": lines, **extra}


def test_setup_assigns_all_lines_in_one_transaction(client, session, auth_headers):
    admin, a, _b, _c = _users(session)
    ws = _computer(session, admin)
    monitor_type = _type(session, "MONITOR", "Monitor", "peripheral")
    mon = it_asset_service.create_asset(session, actor=admin, asset_type_id=monitor_type.id,
                                        asset_number=f"MON-{uuid4().hex[:6]}", commit=True)
    pool = _pool(session, "floating", 1)
    first = _shift(session, "FIRST")
    lines = [{"resource_type": "asset", "resource_id": str(ws.id)},
             {"resource_type": "asset", "resource_id": str(mon.id)},
             {"resource_type": "license", "resource_id": str(pool.id)}]

    dry = client.post(f"{API}/allocation/setup", headers=auth_headers,
                      json=_setup_payload(a, first, lines, dry_run=True)).json()
    assert dry["all_available"] is True and dry["committed"] is False
    assert session.scalar(select(func.count()).select_from(AssetAssignment)
                          .where(AssetAssignment.asset_id == ws.id)) == 0

    done = client.post(f"{API}/allocation/setup", headers=auth_headers,
                       json=_setup_payload(a, first, lines)).json()
    assert done["committed"] is True
    assert [line["result"] for line in done["lines"]] == ["ASSIGNED"] * 3


def test_setup_rolls_back_unless_partial_is_chosen(client, session, auth_headers):
    admin, a, b, _c = _users(session)
    ws, taken = _computer(session, admin), _computer(session, admin)
    first = _shift(session, "FIRST")
    _assign(session, taken, b, admin, shift_id=first.id)
    lines = [{"resource_type": "asset", "resource_id": str(ws.id)},
             {"resource_type": "asset", "resource_id": str(taken.id)}]

    failed = client.post(f"{API}/allocation/setup", headers=auth_headers,
                         json=_setup_payload(a, first, lines)).json()
    assert failed["committed"] is False and failed["rolled_back"] is True
    assert [line["result"] for line in failed["lines"]] == ["ROLLED_BACK", "FAILED"]
    session.expire_all()
    assert not it_asset_service.list_open_assignments(session, ws.id)

    partial = client.post(f"{API}/allocation/setup", headers=auth_headers,
                          json=_setup_payload(a, first, lines, allow_partial=True)).json()
    assert partial["committed"] is True and partial["partial"] is True
    assert [line["result"] for line in partial["lines"]] == ["ASSIGNED", "FAILED"]


# --- permissions ------------------------------------------------------------------------------------


def test_backend_enforces_allocation_permissions(client, session):
    admin, a, _b, _c = _users(session)
    ws = _computer(session, admin)
    headers = login(client, "readonly@prosohm.com")
    first = _shift(session, "FIRST")
    at = _type(session, "DESKTOP", "Desktop", "computer")

    setup = client.post(f"{API}/allocation/setup", headers=headers, json=_setup_payload(
        a, first, [{"resource_type": "asset", "resource_id": str(ws.id)}]))
    assert setup.status_code == 403
    assert client.put(f"{API}/allocation/sharing-policy/{at.id}", headers=headers,
                      json={"is_shareable": False}).status_code == 403
    assert client.post(f"{API}/allocation/reservations", headers=headers, json={
        "resource_type": "asset", "resource_id": str(ws.id), "reserved_for": "x"}).status_code == 403
    assert client.post(f"{API}/assets/{ws.id}/assign", headers=headers,
                       json={"user_id": str(a.id)}).status_code == 403
    assert session.scalar(select(func.count()).select_from(ResourceReservation)) == 0


# --- race protection (section 59) -------------------------------------------------------------------


def _file_copy(test_engine, tmp_path):
    """Two real connections need a file database; copy the seeded in-memory one."""
    path = tmp_path / "race.db"
    raw = test_engine.raw_connection()
    try:
        target = sqlite3.connect(path)
        raw.driver_connection.backup(target)
        target.close()
    finally:
        raw.close()
    file_engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 15})
    return file_engine, sessionmaker(bind=file_engine, autocommit=False, autoflush=False)


def _race(factory, work):
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def run(i):
        db = factory()
        try:
            barrier.wait()
            work(db, i)
            outcomes.append("ok")
        except ProTrackValidationError as exc:
            db.rollback()
            outcomes.append(f"blocked:{exc.status_code}")
        except Exception as exc:  # noqa: BLE001 - surfaced in the assertion
            db.rollback()
            outcomes.append(f"error:{type(exc).__name__}:{exc}\n{traceback.format_exc()}")
        finally:
            db.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return sorted(outcomes)


def test_two_simultaneous_assignments_of_one_slot_only_one_succeeds(session, test_engine, tmp_path):
    admin, a, b, _c = _users(session)
    ws = _computer(session, admin)
    first = _shift(session, "FIRST")
    ws_id, admin_id, shift_id = ws.id, admin.id, first.id
    file_engine, factory = _file_copy(test_engine, tmp_path)
    users = [a.id, b.id]

    def work(db, i):
        asset = db.get(Asset, ws_id)
        actor = db.get(User, admin_id)
        it_asset_service.assign_asset(db, asset, user_id=users[i], by_user=actor, shift_id=shift_id)

    try:
        assert _race(factory, work) == ["blocked:409", "ok"]
        with factory() as db:
            assert len(it_asset_service.list_open_assignments(db, ws_id)) == 1
    finally:
        file_engine.dispose()


def test_two_simultaneous_requests_for_one_concurrent_right(session, test_engine, tmp_path):
    admin, a, b, _c = _users(session)
    pool = _pool(session, "floating", 1)
    first = _shift(session, "FIRST")
    pool_id, shift_id = pool.id, first.id
    file_engine, factory = _file_copy(test_engine, tmp_path)
    users = [a.id, b.id]

    def work(db, i):
        it_software_service.assign_license(db, license_pool_id=pool_id, user_id=users[i], shift_id=shift_id)

    try:
        assert _race(factory, work) == ["blocked:409", "ok"]
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(SoftwareAssignment)
                             .where(SoftwareAssignment.license_pool_id == pool_id)) == 1
    finally:
        file_engine.dispose()
