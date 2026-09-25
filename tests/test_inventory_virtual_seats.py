"""Acceptance: derived Virtual Seats, consumable stock control, onboarding stock check."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType, NotificationType
from app.models.it_operations import (
    Asset,
    AssetType,
    InventoryItem,
    StockAlert,
    StockMovement,
    VirtualSeat,
)
from app.models.models import Activity, Notification, User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, it_availability_service, it_provisioning_service
from app.services import it_stock_service as stock
from app.services import resource_shift_service as shifts
from app.services import virtual_seat_service as seats
from tests.conftest import IDS, login

API = "/api/v1/it"


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


def _asset(session, admin, asset_type, number, computer_type=None) -> Asset:
    return it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=asset_type.id,
        asset_number=number,
        computer_type=computer_type,
        commit=True,
    )


def _setup_first_shift_seat(session):
    admin = session.get(User, IDS["user_admin"])
    employee_a = session.get(User, IDS["user_anurag"])
    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    mouse_3d = _type(session, "M3D", "3D Mouse", "peripheral")
    tag = uuid4().hex[:4].upper()
    ws = _asset(session, admin, desktop, f"WS-001-{tag}", computer_type="ENG_WS")
    mon1 = _asset(session, admin, monitor, f"MON-001-{tag}")
    mon2 = _asset(session, admin, monitor, f"MON-002-{tag}")
    m3d = _asset(session, admin, mouse_3d, f"3DM-001-{tag}")
    first = _shift(session, "FIRST")
    it_asset_service.assign_asset(session, ws, user_id=employee_a.id, by_user=admin, shift_id=first.id)
    for peripheral in (mon1, mon2, m3d):
        it_asset_service.assign_asset(session, peripheral, user_id=employee_a.id, by_user=admin)
    return admin, employee_a, ws, mon1, mon2, m3d


def test_virtual_seat_is_derived_updates_and_supports_shift_sharing(client, session):
    admin, employee_a, ws, _mon1, mon2, _m3d = _setup_first_shift_seat(session)

    [seat] = [s for s in seats.seats_for_user(session, employee_a.id) if s["primary"]]
    assert seat["primary"]["asset_number"] == ws.asset_number
    assert seat["seat_code"] and seat["seat_code"].startswith("VSEAT-")
    assert seat["counts"]["monitor"] == 2
    assert seat["counts"]["mouse_3d"] == 1
    assert seat["seat_type"] == "ENG_WS"
    assert seat["setup_status"] == "complete"
    seat_code = seat["seat_code"]

    it_asset_service.return_asset(session, mon2, by_user=admin)
    [seat] = [s for s in seats.seats_for_user(session, employee_a.id) if s["primary"]]
    assert seat["counts"]["monitor"] == 1
    assert mon2.asset_number not in {c["asset_number"] for c in seat["components"]}
    assert seat["seat_code"] == seat_code
    record = session.scalar(select(VirtualSeat).where(VirtualSeat.code == seat_code))
    history = seats.seat_history(session, record.id)
    removed = [h for h in history if h["action"] == ActivityAction.it_virtual_seat_components_changed.value]
    assert any(mon2.asset_number in (h["new_value"] or {}).get("removed", []) for h in removed)

    employee_b = session.get(User, IDS["user_binil"])
    second = _shift(session, "SECOND")
    it_asset_service.assign_asset(session, ws, user_id=employee_b.id, by_user=admin, shift_id=second.id)
    [seat_b] = [s for s in seats.seats_for_user(session, employee_b.id) if s["primary"]]
    assert seat_b["primary"]["asset_id"] == str(ws.id)
    assert seat_b["shift_display"] and "Second" in seat_b["shift_display"]
    assert seat_b["conflicts"] == []
    [seat_a] = [s for s in seats.seats_for_user(session, employee_a.id) if s["primary"]]
    assert {w["user_name"] for w in seat_a["shared_with"]} == {seat_b["user_name"]}
    assert session.scalar(select(func.count()).select_from(Asset).where(Asset.asset_number == ws.asset_number)) == 1

    employee_c = session.get(User, IDS["user_ranjith"])
    general = _shift(session, "GENERAL")
    with pytest.raises(ProTrackValidationError) as exc:
        it_asset_service.assign_asset(session, ws, user_id=employee_c.id, by_user=admin, shift_id=general.id)
    assert exc.value.status_code == 409
    session.rollback()

    matrix = it_availability_service.computer_availability(session, search=ws.asset_number)
    [row] = matrix["computers"]
    by_shift = {s["shift_code"]: s["status"] for s in row["shifts"]}
    assert by_shift["FIRST"] == "ASSIGNED"
    assert by_shift["SECOND"] == "ASSIGNED"
    assert by_shift["GENERAL"] == "CONFLICT"

    admin_headers = login(client, "admin@prosohm.com")
    listed = client.get(f"{API}/virtual-seats", params={"search": ws.asset_number}, headers=admin_headers)
    assert listed.status_code == 200, listed.text
    holders = {s["user_id"] for s in listed.json()["seats"] if s["primary"]}
    assert holders == {str(employee_a.id), str(employee_b.id)}
    assert listed.json()["summary"]["shared_devices"] >= 1

    profile = client.get(f"/api/v1/users/{employee_a.id}/360", headers=admin_headers)
    assert profile.status_code == 200, profile.text
    assert any(s.get("seat_code") == seat_code for s in profile.json()["virtual_seats"])


def test_returning_primary_device_ends_the_seat(session):
    admin, employee_a, ws, *_ = _setup_first_shift_seat(session)
    [seat] = [s for s in seats.seats_for_user(session, employee_a.id) if s["primary"]]
    it_asset_service.return_asset(session, ws, by_user=admin)
    remaining = seats.seats_for_user(session, employee_a.id)
    assert all(s["primary"] is None for s in remaining)
    assert remaining and remaining[0]["setup_status"] == "no_primary_device"
    record = session.scalar(select(VirtualSeat).where(VirtualSeat.code == seat["seat_code"]))
    assert record.status == "ended"


def _mouse(session, admin, *, on_hand=3, minimum=2) -> InventoryItem:
    item = stock.create_item(
        session,
        actor=admin,
        data={"name": f"USB Mouse {uuid4().hex[:4]}", "item_kind": "mouse", "min_stock": minimum, "target_stock": 10},
        opening_qty=on_hand,
    )
    session.commit()
    return item


def _low_stock_notifications(session, item_id) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.entity_id == item_id, Notification.notification_type == NotificationType.it_low_stock)
    )


def test_consumable_stock_thresholds_alerts_and_receiving(client, session):
    admin = session.get(User, IDS["user_admin"])
    employee = session.get(User, IDS["user_binil"])
    item = _mouse(session, admin)
    lv = stock.item_levels(session, item)
    assert (lv["available"], lv["stock_status"]) == (3, "ok")

    stock.issue(session, item, actor=admin, quantity=1, employee_user_id=employee.id, reason="Replacement")
    session.commit()
    assert stock.item_levels(session, item)["stock_status"] == "ok"
    assert stock.item_levels(session, item)["available"] == 2
    assert _low_stock_notifications(session, item.id) == 0

    stock.issue(session, item, actor=admin, quantity=1, employee_user_id=employee.id)
    session.commit()
    lv = stock.item_levels(session, item)
    assert (lv["available"], lv["stock_status"]) == (1, "low_stock")
    first_count = _low_stock_notifications(session, item.id)
    assert first_count >= 1
    stock.evaluate_alert(session, item, actor=admin)
    session.commit()
    assert _low_stock_notifications(session, item.id) == first_count

    stock.issue(session, item, actor=admin, quantity=1, employee_user_id=employee.id)
    session.commit()
    lv = stock.item_levels(session, item)
    assert (lv["available"], lv["stock_status"]) == (0, "out_of_stock")
    with pytest.raises(ProTrackValidationError):
        stock.issue(session, item, actor=admin, quantity=1, employee_user_id=employee.id)
    session.rollback()
    session.refresh(item)
    assert item.on_hand_qty == 0

    stock.receive(session, item, actor=admin, quantity=10, purchase_order="PO-77")
    session.commit()
    lv = stock.item_levels(session, item)
    assert (lv["on_hand"], lv["available"], lv["stock_status"]) == (10, 10, "ok")
    alerts = session.scalars(select(StockAlert).where(StockAlert.item_id == item.id)).all()
    assert len(alerts) == 1 and alerts[0].status == "resolved"

    ledger = session.scalars(
        select(StockMovement).where(StockMovement.item_id == item.id).order_by(StockMovement.created_at)
    ).all()
    assert [m.movement_type for m in ledger] == ["opening_balance", "issue", "issue", "issue", "receive"]
    assert ledger[-1].previous_qty == 0 and ledger[-1].new_qty == 10

    history = client.get(
        f"{API}/inventory/employee/{employee.id}", headers=login(client, "admin@prosohm.com")
    ).json()
    assert sum(abs(m["quantity"]) for m in history["consumables"] if m["item_id"] == str(item.id)) == 3


def test_reservations_hold_stock_and_release_on_cancel(session):
    admin = session.get(User, IDS["user_admin"])
    employee = session.get(User, IDS["user_binil"])
    item = _mouse(session, admin, on_hand=4)
    reservation = stock.reserve(session, item, actor=admin, quantity=2, for_user_id=employee.id)
    session.commit()
    lv = stock.item_levels(session, item)
    assert (lv["on_hand"], lv["reserved"], lv["available"], lv["stock_status"]) == (4, 2, 2, "ok")
    with pytest.raises(ProTrackValidationError):
        stock.reserve(session, item, actor=admin, quantity=3)
    session.rollback()
    with pytest.raises(ProTrackValidationError):
        stock.issue(session, item, actor=admin, quantity=3, employee_user_id=employee.id)
    session.rollback()
    stock.issue(
        session, item, actor=admin, quantity=2, employee_user_id=employee.id, reservation_id=reservation.id
    )
    session.commit()
    session.refresh(reservation)
    assert reservation.status == "fulfilled"
    lv = stock.item_levels(session, item)
    assert (lv["on_hand"], lv["reserved"], lv["available"]) == (2, 0, 2)

    held = stock.reserve(session, item, actor=admin, quantity=1)
    session.commit()
    assert stock.item_levels(session, item)["stock_status"] == "low_stock"
    stock.release_reservation(session, held, actor=admin, reason="Request cancelled")
    session.commit()
    assert stock.item_levels(session, item)["stock_status"] == "ok"
    assert stock.active_alert(session, item.id) is None


def test_onboarding_requirement_check_shows_shortage_and_low_stock(client, session):
    admin = session.get(User, IDS["user_admin"])
    new_hire = session.get(User, IDS["user_ranjith"])
    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    mouse_3d = _type(session, "M3D", "3D Mouse", "peripheral")
    tag = uuid4().hex[:4].upper()
    _asset(session, admin, desktop, f"WS-ON-{tag}", computer_type="ENG_WS")
    _asset(session, admin, monitor, f"MON-ON1-{tag}")
    _asset(session, admin, monitor, f"MON-ON2-{tag}")
    _asset(session, admin, mouse_3d, f"3DM-ON-{tag}")
    keyboards = stock.create_item(
        session, actor=admin, data={"name": f"Keyboard {tag}", "item_kind": "keyboard", "min_stock": 2}, opening_qty=5
    )
    mice = stock.create_item(
        session, actor=admin, data={"name": f"Mouse {tag}", "item_kind": "mouse", "min_stock": 2}, opening_qty=1
    )
    session.commit()

    request = it_provisioning_service.create_provisioning_for_user(
        session,
        user=new_hire,
        created_by=admin,
        hardware={
            "computer_required": True,
            "computer_type": "ENG_WS",
            "monitor_quantity": 2,
            "mouse_3d_required": True,
            "wireless_keyboard_required": True,
            "wireless_mouse_required": True,
        },
        required_by=date.today() + timedelta(days=7),
    )
    headers = login(client, "admin@prosohm.com")
    check = client.get(f"{API}/inventory/provisioning/{request.id}/check", headers=headers)
    assert check.status_code == 200, check.text
    states = {line["key"]: line["state"] for line in check.json()["lines"]}
    assert states["computer:ENG_WS"] == "available"
    assert states["monitor"] == "available"
    assert states["mouse_3d"] == "available"
    assert states["keyboard"] == "available"
    assert states["mouse"] == "low_stock"

    overview = client.get(f"{API}/inventory/overview", headers=headers).json()
    assert any(row["key"] == "mouse" for row in overview["upcoming_demand"])
    assert any(row["id"] == str(mice.id) for row in overview["low_stock_items"])

    issued = client.post(
        f"{API}/inventory/items/{mice.id}/issue",
        headers=headers,
        json={"quantity": 1, "employee_user_id": str(new_hire.id), "reason": "Onboarding"},
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["stock_status"] == "out_of_stock"
    assert _low_stock_notifications(session, mice.id) >= 1
    assert keyboards.on_hand_qty == 5


def test_stock_permissions_enforced_on_backend(client, session):
    admin = session.get(User, IDS["user_admin"])
    item = _mouse(session, admin)
    employee = login(client, "binil@prosohm.com")
    assert client.get(f"{API}/inventory/items", headers=employee).status_code == 403
    assert client.get(f"{API}/virtual-seats", headers=employee).status_code == 403
    assert (
        client.post(
            f"{API}/inventory/items/{item.id}/receive", headers=employee, json={"quantity": 5}
        ).status_code
        == 403
    )
    own = client.get(f"{API}/inventory/employee/{IDS['user_binil']}", headers=employee)
    assert own.status_code == 200
    other = client.get(f"{API}/inventory/employee/{IDS['user_ranjith']}", headers=employee)
    assert other.status_code == 403
    audit = session.scalars(
        select(Activity).where(Activity.entity_type == EntityType.it_stock_item, Activity.entity_id == item.id)
    ).all()
    assert any(a.action == ActivityAction.it_stock_movement for a in audit)


def test_reports_data_quality_dashboard_and_requirement_config(client, session):
    admin = session.get(User, IDS["user_admin"])
    low = _mouse(session, admin, on_hand=1, minimum=2)
    _setup_first_shift_seat(session)
    headers = login(client, "admin@prosohm.com")

    catalog = client.get(f"{API}/inventory/reports", headers=headers)
    assert catalog.status_code == 200
    for entry in catalog.json():
        res = client.get(f"{API}/inventory/reports/{entry['key']}", headers=headers)
        assert res.status_code == 200, (entry["key"], res.text)
        body = res.json()
        assert body["columns"] and isinstance(body["rows"], list)
    low_report = client.get(f"{API}/inventory/reports/low_stock", headers=headers).json()
    assert any(r["id"] == str(low.id) for r in low_report["rows"])
    seat_report = client.get(f"{API}/inventory/reports/virtual_seats", headers=headers).json()
    assert any((r["seat_code"] or "").startswith("VSEAT-") for r in seat_report["rows"])
    assert client.get(f"{API}/inventory/reports/nope", headers=headers).status_code == 404

    dashboard = client.get(f"{API}/dashboard", headers=headers).json()
    assert dashboard["stock_low_items"] >= 1

    dq = client.get(f"{API}/data-quality", headers=headers).json()
    codes = {row["code"] for row in dq["issues"]}
    assert {"consumables_without_min_stock", "low_stock_without_reorder_info", "virtual_seat_conflicts"} <= codes
    unsourced = next(row for row in dq["issues"] if row["code"] == "low_stock_without_reorder_info")
    assert any(s.get("item_id") == str(low.id) for s in unsourced["samples"])

    saved = client.put(
        f"{API}/virtual-seats/requirements/ENG_WS",
        headers=headers,
        json={"lines": [{"role": "monitor", "required": 3, "recommended": 3}]},
    )
    assert saved.status_code == 200, saved.text
    eng = next(row for row in saved.json() if row["seat_type"] == "ENG_WS")
    assert any(line["role"] == "monitor" and line["required"] == 3 for line in eng["lines"])
    assert session.scalar(
        select(func.count())
        .select_from(Activity)
        .where(Activity.action == ActivityAction.it_settings_updated, Activity.entity_type == EntityType.it_settings)
    )
    employee = login(client, "binil@prosohm.com")
    assert client.get(f"{API}/inventory/reports/low_stock", headers=employee).status_code == 403
    assert (
        client.put(
            f"{API}/virtual-seats/requirements/ENG_WS",
            headers=employee,
            json={"lines": [{"role": "monitor", "required": 1, "recommended": 1}]},
        ).status_code
        == 403
    )
