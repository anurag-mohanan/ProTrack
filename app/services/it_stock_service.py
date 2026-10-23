"""Consumable (quantity-based) IT stock: ledger, reservations, alerts, restock.

Inventory equation (never stored, always computed):

    available = on_hand - reserved          (reserved = active reservations)
    projected = available + incoming - upcoming demand not yet reserved

Every on-hand change writes one ``StockMovement`` row. Stock can never go
negative and non-reservation issues can never consume reserved units.
Low/out-of-stock alerts are episodes: one active alert per item, notified once,
resolved when available stock is back at or above the minimum.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType, NotificationType
from app.models.it_operations import (
    PROVISIONING_TERMINAL,
    STOCK_MOVEMENT_ADJUST,
    STOCK_MOVEMENT_DAMAGE,
    STOCK_MOVEMENT_DISPOSE,
    STOCK_MOVEMENT_ISSUE,
    STOCK_MOVEMENT_OPENING,
    STOCK_MOVEMENT_RECEIVE,
    STOCK_MOVEMENT_RETURN,
    STOCK_MOVEMENT_TRANSFER_IN,
    STOCK_MOVEMENT_TRANSFER_OUT,
    InventoryItem,
    ItProvisioningHardware,
    ItProvisioningRequest,
    ITSupplier,
    RestockRequest,
    StockAlert,
    StockLocation,
    StockMovement,
    StockReservation,
)
from app.models.models import Notification, User
from app.services import it_inventory_rules as rules
from app.services.activity_service import log_activity

MODULE = "it_operations"

STATUS_OK = "ok"
STATUS_LOW = "low_stock"
STATUS_OUT = "out_of_stock"
STATUS_OVER = "overstock"
STATUS_UNSET = "no_minimum"

RESTOCK_OPEN = frozenset({"requested", "ordered", "partially_received"})
RESTOCK_INCOMING = frozenset({"ordered", "partially_received"})
RESTOCK_TRANSITIONS = {
    "requested": {"ordered", "cancelled"},
    "ordered": {"cancelled"},
    "partially_received": {"cancelled"},
}


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _positive(value: int, label: str = "Quantity") -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError) as exc:
        raise ProTrackValidationError(f"{label} must be a whole number.") from exc
    if qty <= 0:
        raise ProTrackValidationError(f"{label} must be greater than zero.")
    return qty


def _audit(db: Session, actor: User | None, item_id: UUID, action: ActivityAction, new: Any, old: Any = None) -> None:
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_stock_item,
        entity_id=item_id,
        action=action,
        old_value=old,
        new_value=new,
        outcome="success",
        module=MODULE,
        commit=False,
    )


# --- Levels ---------------------------------------------------------------------------


def reserved_map(db: Session, item_ids: list[UUID] | None = None) -> dict[UUID, int]:
    stmt = select(StockReservation.item_id, func.coalesce(func.sum(StockReservation.quantity), 0)).where(
        StockReservation.status == "active"
    )
    if item_ids is not None:
        if not item_ids:
            return {}
        stmt = stmt.where(StockReservation.item_id.in_(item_ids))
    return {row[0]: int(row[1]) for row in db.execute(stmt.group_by(StockReservation.item_id)).all()}


def incoming_map(db: Session, item_ids: list[UUID] | None = None) -> dict[UUID, int]:
    stmt = select(
        RestockRequest.item_id,
        func.coalesce(func.sum(RestockRequest.quantity - RestockRequest.received_qty), 0),
    ).where(RestockRequest.status.in_(RESTOCK_INCOMING))
    if item_ids is not None:
        if not item_ids:
            return {}
        stmt = stmt.where(RestockRequest.item_id.in_(item_ids))
    return {row[0]: max(int(row[1]), 0) for row in db.execute(stmt.group_by(RestockRequest.item_id)).all()}


def pending_restock_map(db: Session, item_ids: list[UUID] | None = None) -> dict[UUID, int]:
    stmt = select(RestockRequest.item_id, func.count()).where(RestockRequest.status == "requested")
    if item_ids is not None:
        if not item_ids:
            return {}
        stmt = stmt.where(RestockRequest.item_id.in_(item_ids))
    return {row[0]: int(row[1]) for row in db.execute(stmt.group_by(RestockRequest.item_id)).all()}


def stock_status(available: int, on_hand: int, min_stock: int | None, target: int | None) -> str:
    if available <= 0:
        return STATUS_OUT
    if min_stock is not None and available < min_stock:
        return STATUS_LOW
    if target is not None and target > 0 and on_hand > target:
        return STATUS_OVER
    if min_stock is None:
        return STATUS_UNSET
    return STATUS_OK


def levels(item: InventoryItem, *, reserved: int, incoming: int = 0) -> dict[str, Any]:
    on_hand = int(item.on_hand_qty or 0)
    available = on_hand - reserved
    status = stock_status(available, on_hand, item.min_stock, item.target_stock)
    minimum = item.min_stock
    shortfall = max((minimum or 0) - available, 0)
    if item.reorder_qty:
        recommended = item.reorder_qty
    elif item.target_stock:
        recommended = max(item.target_stock - available - incoming, 0)
    else:
        recommended = max((minimum or 0) - available - incoming, 0)
    projected = available + incoming
    if item.reorder_point is not None:
        reorder_needed = projected <= item.reorder_point
    elif minimum is not None:
        reorder_needed = projected < minimum
    else:
        reorder_needed = False
    return {
        "on_hand": on_hand,
        "reserved": reserved,
        "available": available,
        "incoming": incoming,
        "min_stock": minimum,
        "reorder_point": item.reorder_point,
        "target_stock": item.target_stock,
        "stock_status": status,
        "shortfall": shortfall,
        "recommended_order_qty": recommended if reorder_needed else 0,
        "reorder_needed": reorder_needed,
    }


def item_levels(db: Session, item: InventoryItem) -> dict[str, Any]:
    return levels(
        item,
        reserved=reserved_map(db, [item.id]).get(item.id, 0),
        incoming=incoming_map(db, [item.id]).get(item.id, 0),
    )


# --- Alerts + notifications -----------------------------------------------------------


def it_stock_recipients(db: Session) -> set[UUID]:
    from app.core.access_control import SPECIAL_MANAGE_IT_ASSETS, user_has_special
    from app.core.permissions import get_role_name

    out: set[UUID] = set()
    for user in db.scalars(select(User).where(User.is_active.is_(True), User.is_deleted.is_(False))).all():
        if user_has_special(user, get_role_name(db, user), SPECIAL_MANAGE_IT_ASSETS):
            out.add(user.id)
    return out


def _notify(db: Session, item: InventoryItem, lv: dict[str, Any], alert_type: str) -> None:
    label = "out of stock" if alert_type == STATUS_OUT else "below minimum"
    title = f"{item.name} stock is {label}"
    message = (
        f"Available: {lv['available']} · Minimum: {lv['min_stock']} · "
        f"Shortfall: {lv['shortfall']} · Recommended order: {lv['recommended_order_qty']}. "
        "Restock required."
    )
    for user_id in it_stock_recipients(db):
        db.add(
            Notification(
                user_id=user_id,
                notification_type=NotificationType.it_low_stock,
                title=title[:200],
                message=message,
                entity_type=EntityType.it_stock_item,
                entity_id=item.id,
                is_read=False,
                is_archived=False,
            )
        )


def _restock_ticket_key(alert: StockAlert) -> str:
    return f"it_stock_alert:{alert.id}"


def _raise_restock_ticket(
    db: Session, item: InventoryItem, alert: StockAlert, lv: dict[str, Any], actor: User | None
) -> None:
    """One restock ticket per alert episode (idempotent on the alert id).

    Only raised from stock write paths, never from a read. With no acting user
    there is no truthful requester, so the alert notification stands alone.
    """
    if actor is None:
        return
    from app.services import ticket_workflow_service as workflow

    label = "out of stock" if alert.alert_type == STATUS_OUT else "below minimum"
    workflow.create_ticket(
        db,
        title=f"Restock {item.name} — {label}",
        description=(
            f"{item.name} is {label}.\n"
            f"Available: {lv['available']} · Minimum: {lv['min_stock']} · "
            f"Shortfall: {lv['shortfall']} · Recommended order: {lv['recommended_order_qty']}.\n\n"
            "This ticket resolves automatically when stock is back at or above the minimum."
        ),
        category="it",
        subcategory="stock.restock",
        priority="urgent" if alert.alert_type == STATUS_OUT else "high",
        requester=actor,
        actor=actor,
        source_module="it_stock",
        source_record_id=str(alert.id),
        idempotency_key=_restock_ticket_key(alert),
        related_stock_item_id=item.id,
    )


def _restock_ticket(db: Session, alert: StockAlert):
    from app.services import ticket_workflow_service as workflow

    return workflow.find_by_key(db, _restock_ticket_key(alert))


def _resolve_restock_ticket(
    db: Session, alert: StockAlert, item: InventoryItem, lv: dict[str, Any], actor: User | None
) -> None:
    from app.services import ticket_workflow_service as workflow
    from app.services.ticketing_service import OPEN_STATUSES

    ticket = _restock_ticket(db, alert)
    if ticket is None or ticket.status not in OPEN_STATUSES:
        return
    workflow.transition(
        db,
        ticket,
        to_status="resolved",
        actor=actor,
        resolution=f"Stock replenished: {lv['available']} available (minimum {item.min_stock}).",
        work_performed="Stock level restored by a recorded stock movement; alert episode closed.",
        resolution_category="fulfilled",
        source="it_stock",
    )


def active_alert(db: Session, item_id: UUID) -> StockAlert | None:
    return db.scalar(
        select(StockAlert).where(StockAlert.item_id == item_id, StockAlert.status == "active").limit(1)
    )


def evaluate_alert(db: Session, item: InventoryItem, *, actor: User | None) -> StockAlert | None:
    """Open, escalate or resolve the item's alert episode. Idempotent."""
    db.flush()
    lv = item_levels(db, item)
    current = active_alert(db, item.id)
    minimum = item.min_stock
    condition: str | None = None
    if minimum is not None and not item.is_deleted:
        if lv["available"] <= 0:
            condition = STATUS_OUT
        elif lv["available"] < minimum:
            condition = STATUS_LOW

    if condition is None:
        if current is not None:
            current.status = "resolved"
            current.resolved_at = datetime.now(UTC)
            db.add(current)
            _audit(db, actor, item.id, ActivityAction.it_stock_alert_resolved, {"available": lv["available"], "min_stock": minimum})
            _resolve_restock_ticket(db, current, item, lv, actor)
        return None

    if current is None:
        current = StockAlert(
            id=uuid4(),
            item_id=item.id,
            alert_type=condition,
            status="active",
            available_qty=lv["available"],
            min_stock=int(minimum or 0),
        )
        db.add(current)
        db.flush()
        _audit(db, actor, item.id, ActivityAction.it_stock_alert_raised, {"alert_type": condition, "available": lv["available"], "min_stock": minimum})
        _notify(db, item, lv, condition)
        _raise_restock_ticket(db, item, current, lv, actor)
        return current

    escalated = current.alert_type != STATUS_OUT and condition == STATUS_OUT
    current.alert_type = condition
    current.available_qty = lv["available"]
    current.min_stock = int(minimum or 0)
    db.add(current)
    if escalated:
        _audit(db, actor, item.id, ActivityAction.it_stock_alert_raised, {"alert_type": condition, "available": lv["available"], "min_stock": minimum})
        _notify(db, item, lv, condition)
        ticket = _restock_ticket(db, current)
        if ticket is None:
            _raise_restock_ticket(db, item, current, lv, actor)
        elif actor is not None and ticket.priority != "urgent":
            from app.services import ticket_workflow_service as workflow

            workflow.update_fields(db, ticket, actor=actor, data={"priority": "urgent"})
    return current


# --- Items ----------------------------------------------------------------------------

_ITEM_FIELDS = (
    "name",
    "description",
    "item_kind",
    "sku",
    "supplier_id",
    "supplier_sku",
    "unit_cost",
    "min_stock",
    "reorder_point",
    "target_stock",
    "reorder_qty",
    "lead_time_days",
    "is_returnable",
    "location_id",
    "notes",
)


def _validate_item_fields(db: Session, data: dict[str, Any]) -> None:
    if "name" in data and not (data.get("name") or "").strip():
        raise ProTrackValidationError("Item name is required.")
    kind = data.get("item_kind")
    if kind is not None and kind not in rules.STOCK_KINDS:
        raise ProTrackValidationError(f"Invalid item kind: {kind}")
    for key in ("min_stock", "reorder_point", "target_stock", "reorder_qty", "lead_time_days"):
        value = data.get(key)
        if value is not None and int(value) < 0:
            raise ProTrackValidationError(f"{key.replace('_', ' ').capitalize()} cannot be negative.")
    if data.get("supplier_id") and db.get(ITSupplier, data["supplier_id"]) is None:
        raise ProTrackValidationError("Supplier not found.")
    if data.get("location_id"):
        location = db.get(StockLocation, data["location_id"])
        if location is None or not location.is_active:
            raise ProTrackValidationError("Stock location not found.")


def create_item(
    db: Session, *, actor: User, data: dict[str, Any], opening_qty: int = 0
) -> InventoryItem:
    _validate_item_fields(db, data)
    if opening_qty < 0:
        raise ProTrackValidationError("Opening quantity cannot be negative.")
    name = data["name"].strip()
    location_id = data.get("location_id")
    same_location = (
        InventoryItem.location_id.is_(None)
        if location_id is None
        else InventoryItem.location_id == location_id
    )
    duplicate = db.scalar(
        select(InventoryItem).where(
            func.lower(InventoryItem.name) == name.lower(),
            InventoryItem.is_deleted.is_(False),
            same_location,
        )
    )
    if duplicate is not None:
        raise ProTrackValidationError(f"A stock item named '{name}' already exists at this location.")
    item = InventoryItem(id=uuid4(), name=name, on_hand_qty=0, total_qty=0, issued_qty=0)
    for key in _ITEM_FIELDS:
        if key in data and key != "name":
            setattr(item, key, data[key])
    item.item_kind = rules.kind_for_stock_item(item.item_kind, item.name, item.category)
    if item.location_id:
        item.location = db.get(StockLocation, item.location_id).name  # type: ignore[union-attr]
    db.add(item)
    db.flush()
    _audit(db, actor, item.id, ActivityAction.it_stock_item_created, {"name": item.name, "kind": item.item_kind})
    if opening_qty:
        _move(db, item, actor=actor, movement_type=STOCK_MOVEMENT_OPENING, delta=opening_qty, reason="Opening balance")
    evaluate_alert(db, item, actor=actor)
    return item


def update_item(db: Session, item: InventoryItem, *, actor: User, data: dict[str, Any]) -> InventoryItem:
    if item.is_deleted:
        raise ProTrackValidationError("Item is archived.")
    _validate_item_fields(db, data)
    before = {k: getattr(item, k) for k in _ITEM_FIELDS}
    for key in _ITEM_FIELDS:
        if key in data:
            value = data[key]
            if key == "name":
                value = (value or "").strip()
            setattr(item, key, value)
    if "location_id" in data:
        loc = db.get(StockLocation, item.location_id) if item.location_id else None
        item.location = loc.name if loc else None
    db.add(item)
    changed = {k: getattr(item, k) for k in _ITEM_FIELDS if getattr(item, k) != before[k]}
    if changed:
        _audit(
            db,
            actor,
            item.id,
            ActivityAction.it_stock_item_updated,
            changed,
            {k: before[k] for k in changed},
        )
    evaluate_alert(db, item, actor=actor)
    return item


# --- Movements ------------------------------------------------------------------------


def _move(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    movement_type: str,
    delta: int,
    reason: str | None = None,
    reference: str | None = None,
    employee_user_id: UUID | None = None,
    reservation: StockReservation | None = None,
    restock_request_id: UUID | None = None,
    ticket_id: UUID | None = None,
    supplier_id: UUID | None = None,
    purchase_order: str | None = None,
    invoice_number: str | None = None,
    unit_cost: Decimal | None = None,
    occurred_on: date | None = None,
    counterpart_location_id: UUID | None = None,
    related_movement_id: UUID | None = None,
    notes: str | None = None,
) -> StockMovement:
    if item.is_deleted:
        raise ProTrackValidationError("Item is archived.")
    previous = int(item.on_hand_qty or 0)
    new = previous + delta
    if new < 0:
        raise ProTrackValidationError(
            f"Insufficient stock: {previous} on hand, cannot remove {abs(delta)}. Negative stock is not allowed."
        )
    if delta < 0:
        reserved_total = reserved_map(db, [item.id]).get(item.id, 0)
        held_for_this = reservation.quantity if reservation is not None else 0
        free = previous - (reserved_total - held_for_this)
        if abs(delta) > free:
            raise ProTrackValidationError(
                f"Only {max(free, 0)} unit(s) are free; {reserved_total - held_for_this} are reserved for other requests."
            )
    item.on_hand_qty = new
    db.add(item)
    movement = StockMovement(
        id=uuid4(),
        item_id=item.id,
        movement_type=movement_type,
        quantity=delta,
        previous_qty=previous,
        new_qty=new,
        occurred_on=occurred_on or date.today(),
        performed_by_user_id=actor.id,
        employee_user_id=employee_user_id,
        reason=(reason or "").strip() or None,
        reference=(reference or "").strip() or None,
        reservation_id=reservation.id if reservation is not None else None,
        restock_request_id=restock_request_id,
        ticket_id=ticket_id,
        supplier_id=supplier_id,
        purchase_order=(purchase_order or "").strip() or None,
        invoice_number=(invoice_number or "").strip() or None,
        unit_cost=unit_cost,
        counterpart_location_id=counterpart_location_id,
        related_movement_id=related_movement_id,
        notes=(notes or "").strip() or None,
    )
    db.add(movement)
    db.flush()
    _audit(
        db,
        actor,
        item.id,
        ActivityAction.it_stock_movement,
        {
            "movement_type": movement_type,
            "quantity": delta,
            "previous_qty": previous,
            "new_qty": new,
            "reason": movement.reason,
            "reference": movement.reference,
            "employee_user_id": str(employee_user_id) if employee_user_id else None,
        },
    )
    return movement


def receive(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int,
    received_on: date | None = None,
    supplier_id: UUID | None = None,
    purchase_order: str | None = None,
    invoice_number: str | None = None,
    unit_cost: Decimal | None = None,
    restock_request_id: UUID | None = None,
    notes: str | None = None,
) -> StockMovement:
    qty = _positive(quantity)
    request = None
    if restock_request_id is not None:
        request = db.get(RestockRequest, restock_request_id)
        if request is None or request.item_id != item.id:
            raise ProTrackValidationError("Restock request not found for this item.")
        if request.status not in RESTOCK_OPEN:
            raise ProTrackValidationError(f"Restock request {request.code} is {request.status}.")
        supplier_id = supplier_id or request.supplier_id
        purchase_order = purchase_order or request.purchase_order
    if supplier_id and db.get(ITSupplier, supplier_id) is None:
        raise ProTrackValidationError("Supplier not found.")
    movement = _move(
        db,
        item,
        actor=actor,
        movement_type=STOCK_MOVEMENT_RECEIVE,
        delta=qty,
        reason="Purchase received",
        reference=purchase_order or invoice_number,
        supplier_id=supplier_id,
        purchase_order=purchase_order,
        invoice_number=invoice_number,
        unit_cost=unit_cost,
        restock_request_id=restock_request_id,
        occurred_on=received_on,
        notes=notes,
    )
    item.last_purchase_date = received_on or date.today()
    if unit_cost is not None:
        item.last_purchase_cost = unit_cost
        item.unit_cost = unit_cost
    if supplier_id and not item.supplier_id:
        item.supplier_id = supplier_id
    db.add(item)
    if request is not None:
        request.received_qty = int(request.received_qty or 0) + qty
        request.status = "received" if request.received_qty >= request.quantity else "partially_received"
        db.add(request)
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_restock_request,
            entity_id=request.id,
            action=ActivityAction.it_restock_request_changed,
            new_value={"status": request.status, "received_qty": request.received_qty, "code": request.code},
            outcome="success",
            module=MODULE,
            commit=False,
        )
    evaluate_alert(db, item, actor=actor)
    return movement


def issue(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int,
    employee_user_id: UUID,
    reason: str | None = None,
    reference: str | None = None,
    reservation_id: UUID | None = None,
    ticket_id: UUID | None = None,
    issued_on: date | None = None,
) -> StockMovement:
    qty = _positive(quantity)
    employee = db.get(User, employee_user_id)
    if employee is None or employee.is_deleted:
        raise ProTrackValidationError("Employee not found.")
    reservation = None
    if reservation_id is not None:
        reservation = db.get(StockReservation, reservation_id)
        if reservation is None or reservation.item_id != item.id or reservation.status != "active":
            raise ProTrackValidationError("Active reservation not found for this item.")
        if qty > reservation.quantity:
            raise ProTrackValidationError(f"Reservation holds only {reservation.quantity} unit(s).")
        ticket_id = ticket_id or reservation.ticket_id
    movement = _move(
        db,
        item,
        actor=actor,
        movement_type=STOCK_MOVEMENT_ISSUE,
        delta=-qty,
        reason=reason or "Issued to employee",
        reference=reference,
        employee_user_id=employee_user_id,
        reservation=reservation,
        ticket_id=ticket_id,
        occurred_on=issued_on,
    )
    if reservation is not None:
        if qty >= reservation.quantity:
            reservation.status = "fulfilled"
            reservation.closed_at = datetime.now(UTC)
            reservation.close_reason = "Issued"
        else:
            reservation.quantity -= qty
        db.add(reservation)
    evaluate_alert(db, item, actor=actor)
    return movement


def return_to_stock(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int,
    issue_movement_id: UUID | None = None,
    employee_user_id: UUID | None = None,
    reason: str | None = None,
) -> StockMovement:
    qty = _positive(quantity)
    if not item.is_returnable:
        raise ProTrackValidationError(f"{item.name} is not a returnable item.")
    source = None
    if issue_movement_id is not None:
        source = db.get(StockMovement, issue_movement_id)
        if source is None or source.item_id != item.id or source.movement_type != STOCK_MOVEMENT_ISSUE:
            raise ProTrackValidationError("Original issue not found for this item.")
        outstanding = abs(source.quantity) - (source.returned_qty or 0)
        if qty > outstanding:
            raise ProTrackValidationError(f"Only {outstanding} unit(s) from that issue are outstanding.")
        employee_user_id = source.employee_user_id
    movement = _move(
        db,
        item,
        actor=actor,
        movement_type=STOCK_MOVEMENT_RETURN,
        delta=qty,
        reason=reason or "Returned to stock",
        employee_user_id=employee_user_id,
        related_movement_id=source.id if source else None,
    )
    if source is not None:
        source.returned_qty = int(source.returned_qty or 0) + qty
        db.add(source)
    evaluate_alert(db, item, actor=actor)
    return movement


def write_off(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    movement_type: str,
    quantity: int,
    reason: str,
) -> StockMovement:
    if movement_type not in {STOCK_MOVEMENT_DAMAGE, STOCK_MOVEMENT_DISPOSE}:
        raise ProTrackValidationError("Write-off must be damage or dispose.")
    if not (reason or "").strip():
        raise ProTrackValidationError("A reason is required.")
    movement = _move(db, item, actor=actor, movement_type=movement_type, delta=-_positive(quantity), reason=reason)
    evaluate_alert(db, item, actor=actor)
    return movement


def adjust(
    db: Session, item: InventoryItem, *, actor: User, counted_qty: int, reason: str
) -> StockMovement:
    if not (reason or "").strip():
        raise ProTrackValidationError("A reason is required for a stock adjustment.")
    counted = int(counted_qty)
    if counted < 0:
        raise ProTrackValidationError("Counted quantity cannot be negative.")
    delta = counted - int(item.on_hand_qty or 0)
    if delta == 0:
        raise ProTrackValidationError("Counted quantity equals the current on-hand quantity.")
    reserved_total = reserved_map(db, [item.id]).get(item.id, 0)
    if counted < reserved_total:
        raise ProTrackValidationError(
            f"{reserved_total} unit(s) are reserved; release reservations before counting below that."
        )
    previous = int(item.on_hand_qty or 0)
    item.on_hand_qty = counted
    db.add(item)
    movement = StockMovement(
        id=uuid4(),
        item_id=item.id,
        movement_type=STOCK_MOVEMENT_ADJUST,
        quantity=delta,
        previous_qty=previous,
        new_qty=counted,
        occurred_on=date.today(),
        performed_by_user_id=actor.id,
        reason=reason.strip(),
    )
    db.add(movement)
    db.flush()
    _audit(db, actor, item.id, ActivityAction.it_stock_movement, {"movement_type": STOCK_MOVEMENT_ADJUST, "quantity": delta, "previous_qty": previous, "new_qty": counted, "reason": reason.strip()})
    evaluate_alert(db, item, actor=actor)
    return movement


def transfer(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int,
    to_location_id: UUID,
    reason: str | None = None,
) -> tuple[StockMovement, StockMovement]:
    qty = _positive(quantity)
    destination_loc = db.get(StockLocation, to_location_id)
    if destination_loc is None or not destination_loc.is_active:
        raise ProTrackValidationError("Destination location not found.")
    if item.location_id == to_location_id:
        raise ProTrackValidationError("Item is already at that location.")
    destination = db.scalar(
        select(InventoryItem).where(
            func.lower(InventoryItem.name) == item.name.lower(),
            InventoryItem.location_id == to_location_id,
            InventoryItem.is_deleted.is_(False),
        )
    )
    if destination is None:
        destination = InventoryItem(
            id=uuid4(),
            name=item.name,
            description=item.description,
            category=item.category,
            item_kind=item.item_kind,
            sku=item.sku,
            supplier_id=item.supplier_id,
            supplier_sku=item.supplier_sku,
            unit_cost=item.unit_cost,
            is_returnable=item.is_returnable,
            location_id=to_location_id,
            location=destination_loc.name,
            on_hand_qty=0,
            total_qty=0,
            issued_qty=0,
        )
        db.add(destination)
        db.flush()
        _audit(db, actor, destination.id, ActivityAction.it_stock_item_created, {"name": destination.name, "created_by_transfer_from": str(item.id)})
    out_move = _move(
        db,
        item,
        actor=actor,
        movement_type=STOCK_MOVEMENT_TRANSFER_OUT,
        delta=-qty,
        reason=reason or f"Transfer to {destination_loc.name}",
        counterpart_location_id=to_location_id,
    )
    in_move = _move(
        db,
        destination,
        actor=actor,
        movement_type=STOCK_MOVEMENT_TRANSFER_IN,
        delta=qty,
        reason=reason or "Transfer in",
        counterpart_location_id=item.location_id,
        related_movement_id=out_move.id,
    )
    evaluate_alert(db, item, actor=actor)
    evaluate_alert(db, destination, actor=actor)
    return out_move, in_move


# --- Reservations ---------------------------------------------------------------------


def reserve(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int,
    for_user_id: UUID | None = None,
    ticket_id: UUID | None = None,
    provisioning_request_id: UUID | None = None,
    reason: str | None = None,
) -> StockReservation:
    qty = _positive(quantity)
    lv = item_levels(db, item)
    if qty > lv["available"]:
        raise ProTrackValidationError(
            f"Only {max(lv['available'], 0)} unit(s) of {item.name} are available to reserve."
        )
    if provisioning_request_id is not None:
        request = db.get(ItProvisioningRequest, provisioning_request_id)
        if request is None:
            raise ProTrackValidationError("Provisioning request not found.")
        if request.status in PROVISIONING_TERMINAL:
            raise ProTrackValidationError(f"Provisioning request is {request.status}.")
        for_user_id = for_user_id or request.user_id
        ticket_id = ticket_id or request.ticket_id
    reservation = StockReservation(
        id=uuid4(),
        item_id=item.id,
        quantity=qty,
        status="active",
        for_user_id=for_user_id,
        ticket_id=ticket_id,
        provisioning_request_id=provisioning_request_id,
        reason=(reason or "").strip() or None,
        reserved_by_user_id=actor.id,
    )
    db.add(reservation)
    db.flush()
    _audit(db, actor, item.id, ActivityAction.it_stock_reserved, {"quantity": qty, "reservation_id": str(reservation.id), "for_user_id": str(for_user_id) if for_user_id else None})
    evaluate_alert(db, item, actor=actor)
    return reservation


def release_reservation(
    db: Session, reservation: StockReservation, *, actor: User | None, reason: str
) -> StockReservation:
    if reservation.status != "active":
        raise ProTrackValidationError("Reservation is not active.")
    reservation.status = "released"
    reservation.closed_at = datetime.now(UTC)
    reservation.close_reason = (reason or "").strip() or "Released"
    db.add(reservation)
    item = db.get(InventoryItem, reservation.item_id)
    _audit(db, actor, reservation.item_id, ActivityAction.it_stock_reservation_closed, {"reservation_id": str(reservation.id), "quantity": reservation.quantity, "reason": reservation.close_reason})
    if item is not None:
        evaluate_alert(db, item, actor=actor)
    return reservation


def release_for_ticket(db: Session, ticket_id: UUID, *, actor: User | None, reason: str) -> int:
    rows = db.scalars(
        select(StockReservation).where(StockReservation.ticket_id == ticket_id, StockReservation.status == "active")
    ).all()
    for row in rows:
        release_reservation(db, row, actor=actor, reason=reason)
    return len(rows)


def release_for_provisioning(db: Session, request_id: UUID, *, actor: User | None, reason: str) -> int:
    rows = db.scalars(
        select(StockReservation).where(
            StockReservation.provisioning_request_id == request_id, StockReservation.status == "active"
        )
    ).all()
    for row in rows:
        release_reservation(db, row, actor=actor, reason=reason)
    return len(rows)


# --- Restock requests -----------------------------------------------------------------


def _next_restock_code(db: Session) -> str:
    highest = 0
    for code in db.scalars(select(RestockRequest.code)).all():
        tail = (code or "").rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"RST-{highest + 1:04d}"


def create_restock_request(
    db: Session,
    item: InventoryItem,
    *,
    actor: User,
    quantity: int | None = None,
    supplier_id: UUID | None = None,
    expected_date: date | None = None,
    notes: str | None = None,
) -> RestockRequest:
    lv = item_levels(db, item)
    qty = _positive(quantity if quantity is not None else (lv["recommended_order_qty"] or 0), "Order quantity")
    supplier_id = supplier_id or item.supplier_id
    if supplier_id and db.get(ITSupplier, supplier_id) is None:
        raise ProTrackValidationError("Supplier not found.")
    alert = active_alert(db, item.id)
    request = RestockRequest(
        id=uuid4(),
        code=_next_restock_code(db),
        item_id=item.id,
        quantity=qty,
        received_qty=0,
        status="requested",
        supplier_id=supplier_id,
        expected_date=expected_date,
        alert_id=alert.id if alert else None,
        requested_by_user_id=actor.id,
        notes=(notes or "").strip() or None,
    )
    db.add(request)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_restock_request,
        entity_id=request.id,
        action=ActivityAction.it_restock_request_changed,
        new_value={"status": "requested", "quantity": qty, "code": request.code, "item": item.name},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    return request


def update_restock_status(
    db: Session,
    request: RestockRequest,
    *,
    actor: User,
    status: str,
    purchase_order: str | None = None,
    expected_date: date | None = None,
    notes: str | None = None,
) -> RestockRequest:
    allowed = RESTOCK_TRANSITIONS.get(request.status, set())
    if status not in allowed:
        raise ProTrackValidationError(f"Cannot move restock request from {request.status} to {status}.")
    if status == "ordered" and not (purchase_order or request.purchase_order):
        raise ProTrackValidationError("A purchase order number is required to mark as ordered.")
    old = request.status
    request.status = status
    if purchase_order:
        request.purchase_order = purchase_order.strip()
    if expected_date:
        request.expected_date = expected_date
    if notes:
        request.notes = f"{request.notes}\n{notes}".strip() if request.notes else notes.strip()
    db.add(request)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_restock_request,
        entity_id=request.id,
        action=ActivityAction.it_restock_request_changed,
        old_value={"status": old},
        new_value={"status": status, "purchase_order": request.purchase_order, "code": request.code},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    return request


# --- Read models ----------------------------------------------------------------------


def _last_movement_map(db: Session, item_ids: list[UUID]) -> dict[UUID, date]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(StockMovement.item_id, func.max(StockMovement.occurred_on))
        .where(StockMovement.item_id.in_(item_ids))
        .group_by(StockMovement.item_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def item_rows(
    db: Session,
    *,
    search: str | None = None,
    kind: str | None = None,
    location_id: UUID | None = None,
    stock_status_filter: str | None = None,
    supplier_id: UUID | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    stmt = select(InventoryItem)
    if not include_archived:
        stmt = stmt.where(InventoryItem.is_deleted.is_(False))
    if location_id:
        stmt = stmt.where(InventoryItem.location_id == location_id)
    if supplier_id:
        stmt = stmt.where(InventoryItem.supplier_id == supplier_id)
    items = list(db.scalars(stmt.order_by(InventoryItem.name)).all())
    ids = [i.id for i in items]
    reserved = reserved_map(db, ids)
    incoming = incoming_map(db, ids)
    pending = pending_restock_map(db, ids)
    last = _last_movement_map(db, ids)
    suppliers = {s.id: s.name for s in db.scalars(select(ITSupplier)).all()}
    locations = {loc.id: loc.name for loc in db.scalars(select(StockLocation)).all()}
    alerts = {
        a.item_id: a
        for a in db.scalars(select(StockAlert).where(StockAlert.status == "active")).all()
    }
    q = (search or "").strip().lower()
    out = []
    for item in items:
        item_kind = rules.kind_for_stock_item(item.item_kind, item.name, item.category)
        if kind and item_kind != kind:
            continue
        lv = levels(item, reserved=reserved.get(item.id, 0), incoming=incoming.get(item.id, 0))
        if stock_status_filter:
            if stock_status_filter == "reorder":
                if not lv["reorder_needed"]:
                    continue
            elif stock_status_filter == "incoming":
                if not lv["incoming"]:
                    continue
            elif lv["stock_status"] != stock_status_filter:
                continue
        location_name = locations.get(item.location_id) if item.location_id else item.location
        supplier_name = suppliers.get(item.supplier_id) if item.supplier_id else None
        if q:
            haystack = " ".join(
                str(v or "") for v in [item.name, item.sku, item.supplier_sku, supplier_name, location_name, item.description]
            ).lower()
            if q not in haystack:
                continue
        alert = alerts.get(item.id)
        out.append(
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description,
                "item_kind": item_kind,
                "item_kind_label": rules.ROLE_LABELS.get(item_kind, item_kind),
                "group": rules.group_for_role(item_kind),
                "sku": item.sku,
                "supplier_id": str(item.supplier_id) if item.supplier_id else None,
                "supplier_name": supplier_name,
                "supplier_sku": item.supplier_sku,
                "location_id": str(item.location_id) if item.location_id else None,
                "location_name": location_name,
                "unit_cost": item.unit_cost,
                "last_purchase_date": item.last_purchase_date,
                "last_purchase_cost": item.last_purchase_cost,
                "lead_time_days": item.lead_time_days,
                "reorder_qty": item.reorder_qty,
                "is_returnable": bool(item.is_returnable),
                "is_archived": bool(item.is_deleted),
                "notes": item.notes,
                "pending_restock_requests": pending.get(item.id, 0),
                "last_movement_on": last.get(item.id),
                "has_movements": item.id in last,
                "active_alert": (
                    {"id": str(alert.id), "alert_type": alert.alert_type, "since": alert.created_at}
                    if alert
                    else None
                ),
                **lv,
            }
        )
    return out


def movement_rows(
    db: Session,
    *,
    item_id: UUID | None = None,
    movement_type: str | None = None,
    employee_user_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(StockMovement, InventoryItem).join(InventoryItem, InventoryItem.id == StockMovement.item_id)
    if item_id:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if employee_user_id:
        stmt = stmt.where(StockMovement.employee_user_id == employee_user_id)
    if date_from:
        stmt = stmt.where(StockMovement.occurred_on >= date_from)
    if date_to:
        stmt = stmt.where(StockMovement.occurred_on <= date_to)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.execute(
        stmt.order_by(StockMovement.occurred_on.desc(), StockMovement.created_at.desc()).limit(limit).offset(offset)
    ).all()
    user_ids = {m.performed_by_user_id for m, _ in rows} | {m.employee_user_id for m, _ in rows if m.employee_user_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    locations = {loc.id: loc.name for loc in db.scalars(select(StockLocation)).all()}
    out = []
    for movement, item in rows:
        out.append(
            {
                "id": str(movement.id),
                "item_id": str(item.id),
                "item_name": item.name,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "previous_qty": movement.previous_qty,
                "new_qty": movement.new_qty,
                "occurred_on": movement.occurred_on,
                "recorded_at": movement.created_at,
                "performed_by_name": _full_name(users.get(movement.performed_by_user_id)),
                "employee_user_id": str(movement.employee_user_id) if movement.employee_user_id else None,
                "employee_name": _full_name(users.get(movement.employee_user_id)) if movement.employee_user_id else None,
                "reason": movement.reason,
                "reference": movement.reference,
                "purchase_order": movement.purchase_order,
                "invoice_number": movement.invoice_number,
                "unit_cost": movement.unit_cost,
                "counterpart_location": locations.get(movement.counterpart_location_id) if movement.counterpart_location_id else None,
                "returned_qty": movement.returned_qty,
                "returnable": bool(item.is_returnable),
                "ticket_id": str(movement.ticket_id) if movement.ticket_id else None,
            }
        )
    return out, total


def reservation_rows(db: Session, *, item_id: UUID | None = None, status: str | None = "active") -> list[dict[str, Any]]:
    stmt = select(StockReservation, InventoryItem).join(InventoryItem, InventoryItem.id == StockReservation.item_id)
    if item_id:
        stmt = stmt.where(StockReservation.item_id == item_id)
    if status:
        stmt = stmt.where(StockReservation.status == status)
    rows = db.execute(stmt.order_by(StockReservation.created_at.desc())).all()
    user_ids = {r.for_user_id for r, _ in rows if r.for_user_id} | {r.reserved_by_user_id for r, _ in rows}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return [
        {
            "id": str(r.id),
            "item_id": str(item.id),
            "item_name": item.name,
            "quantity": r.quantity,
            "status": r.status,
            "for_user_id": str(r.for_user_id) if r.for_user_id else None,
            "for_user_name": _full_name(users.get(r.for_user_id)) if r.for_user_id else None,
            "ticket_id": str(r.ticket_id) if r.ticket_id else None,
            "provisioning_request_id": str(r.provisioning_request_id) if r.provisioning_request_id else None,
            "reason": r.reason,
            "reserved_by_name": _full_name(users.get(r.reserved_by_user_id)),
            "created_at": r.created_at,
            "closed_at": r.closed_at,
            "close_reason": r.close_reason,
        }
        for r, item in rows
    ]


def restock_rows(db: Session, *, status: str | None = None, item_id: UUID | None = None) -> list[dict[str, Any]]:
    stmt = select(RestockRequest, InventoryItem).join(InventoryItem, InventoryItem.id == RestockRequest.item_id)
    if status == "open":
        stmt = stmt.where(RestockRequest.status.in_(RESTOCK_OPEN))
    elif status:
        stmt = stmt.where(RestockRequest.status == status)
    if item_id:
        stmt = stmt.where(RestockRequest.item_id == item_id)
    rows = db.execute(stmt.order_by(RestockRequest.created_at.desc())).all()
    suppliers = {s.id: s.name for s in db.scalars(select(ITSupplier)).all()}
    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_({r.requested_by_user_id for r, _ in rows}))).all()
    } if rows else {}
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "item_id": str(item.id),
            "item_name": item.name,
            "quantity": r.quantity,
            "received_qty": r.received_qty,
            "outstanding_qty": max(r.quantity - r.received_qty, 0),
            "status": r.status,
            "supplier_id": str(r.supplier_id) if r.supplier_id else None,
            "supplier_name": suppliers.get(r.supplier_id) if r.supplier_id else None,
            "purchase_order": r.purchase_order,
            "expected_date": r.expected_date,
            "requested_by_name": _full_name(users.get(r.requested_by_user_id)),
            "created_at": r.created_at,
            "notes": r.notes,
        }
        for r, item in rows
    ]


def employee_consumables(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    rows, _total = movement_rows(db, employee_user_id=user_id, limit=500)
    return rows


# --- Availability by kind + upcoming demand -------------------------------------------


def _open_provisioning(db: Session) -> list[tuple[ItProvisioningRequest, ItProvisioningHardware]]:
    return [
        tuple(row)  # type: ignore[misc]
        for row in db.execute(
            select(ItProvisioningRequest, ItProvisioningHardware)
            .join(ItProvisioningHardware, ItProvisioningHardware.provisioning_request_id == ItProvisioningRequest.id)
            .where(ItProvisioningRequest.status.not_in(PROVISIONING_TERMINAL))
        ).all()
    ]


def hardware_needs(hw: ItProvisioningHardware) -> dict[str, int]:
    """Requirement lines of one provisioning request, keyed by role (computer types separate)."""
    needs: dict[str, int] = defaultdict(int)
    if hw.computer_required and hw.computer_type:
        needs[f"computer:{hw.computer_type}"] += 1
    elif hw.computer_required:
        needs[rules.ROLE_COMPUTER] += 1
    if hw.monitor_quantity:
        needs[rules.ROLE_MONITOR] += int(hw.monitor_quantity)
    if hw.mouse_3d_required:
        needs[rules.ROLE_MOUSE_3D] += 1
    if hw.wireless_keyboard_required:
        needs[rules.ROLE_KEYBOARD] += 1
    if hw.wireless_mouse_required:
        needs[rules.ROLE_MOUSE] += 1
    if hw.headset_required:
        needs[rules.ROLE_HEADSET] += 1
    if hw.laptop_dock_required:
        needs[rules.ROLE_DOCK] += 1
    if hw.laptop_bag_required:
        needs[rules.ROLE_BAG] += 1
    return dict(needs)


def availability_by_kind(db: Session) -> dict[str, dict[str, Any]]:
    """Free units per role: unassigned serialized assets + available consumable stock."""
    from app.models.it_operations import Asset, AssetAssignment, AssetType

    open_asset_ids = set(
        db.scalars(select(AssetAssignment.asset_id).where(AssetAssignment.returned_date.is_(None))).all()
    )
    out: dict[str, dict[str, Any]] = {}

    def bucket(key: str, label: str) -> dict[str, Any]:
        return out.setdefault(
            key,
            {"key": key, "label": label, "assets_available": 0, "stock_available": 0, "stock_status": None, "min_stock": None},
        )

    for asset, asset_type in db.execute(
        select(Asset, AssetType)
        .join(AssetType, AssetType.id == Asset.asset_type_id)
        .where(Asset.is_deleted.is_(False), Asset.status == "available")
    ).all():
        if asset.id in open_asset_ids:
            continue
        role = rules.role_for_asset_type(asset_type)
        if role == rules.ROLE_COMPUTER:
            from app.services.virtual_seat_service import seat_type_for

            code = seat_type_for(asset, asset_type)
            bucket(f"computer:{code}", rules.SEAT_TYPE_LABELS.get(code, code))["assets_available"] += 1
            bucket(rules.ROLE_COMPUTER, "Computers (any type)")["assets_available"] += 1
        else:
            bucket(role, rules.ROLE_LABELS.get(role, role))["assets_available"] += 1

    items = list(db.scalars(select(InventoryItem).where(InventoryItem.is_deleted.is_(False))).all())
    reserved = reserved_map(db, [i.id for i in items])
    worst_rank = {STATUS_OUT: 3, STATUS_LOW: 2, STATUS_OK: 1, STATUS_OVER: 1, STATUS_UNSET: 0}
    for item in items:
        kind = rules.kind_for_stock_item(item.item_kind, item.name, item.category)
        lv = levels(item, reserved=reserved.get(item.id, 0))
        row = bucket(kind, rules.ROLE_LABELS.get(kind, kind))
        row["stock_available"] += max(lv["available"], 0)
        if item.min_stock is not None:
            row["min_stock"] = (row["min_stock"] or 0) + item.min_stock
        if row["stock_status"] is None or worst_rank[lv["stock_status"]] > worst_rank.get(row["stock_status"], 0):
            row["stock_status"] = lv["stock_status"]
    for row in out.values():
        row["available"] = row["assets_available"] + row["stock_available"]
    return out


def upcoming_demand(db: Session) -> list[dict[str, Any]]:
    """Open onboarding/provisioning requirements vs what is free now (nothing is deducted)."""
    demand: dict[str, int] = defaultdict(int)
    request_ids = []
    for request, hw in _open_provisioning(db):
        request_ids.append(request.id)
        for key, qty in hardware_needs(hw).items():
            demand[key] += qty
    reserved_for_requests: dict[str, int] = defaultdict(int)
    if request_ids:
        for reservation, item in db.execute(
            select(StockReservation, InventoryItem)
            .join(InventoryItem, InventoryItem.id == StockReservation.item_id)
            .where(StockReservation.status == "active", StockReservation.provisioning_request_id.in_(request_ids))
        ).all():
            reserved_for_requests[rules.kind_for_stock_item(item.item_kind, item.name, item.category)] += reservation.quantity
    avail = availability_by_kind(db)
    incoming_by_kind: dict[str, int] = defaultdict(int)
    for request in db.scalars(select(RestockRequest).where(RestockRequest.status.in_(RESTOCK_INCOMING))).all():
        item = db.get(InventoryItem, request.item_id)
        if item is not None:
            incoming_by_kind[rules.kind_for_stock_item(item.item_kind, item.name, item.category)] += max(
                request.quantity - request.received_qty, 0
            )
    rows = []
    for key, required in sorted(demand.items()):
        info = avail.get(key) or {}
        label = info.get("label")
        if not label:
            label = (
                rules.SEAT_TYPE_LABELS.get(key.split(":", 1)[1], key)
                if key.startswith("computer:")
                else rules.ROLE_LABELS.get(key, key)
            )
        committed = reserved_for_requests.get(key, 0)
        available = int(info.get("available", 0))
        incoming = incoming_by_kind.get(key, 0)
        projected = available + incoming - (required - committed)
        rows.append(
            {
                "key": key,
                "label": label,
                "required": required,
                "committed": committed,
                "available": available,
                "incoming": incoming,
                "projected": projected,
                "shortage": projected < 0,
            }
        )
    return rows


def requirement_check(db: Session, request: ItProvisioningRequest) -> list[dict[str, Any]]:
    """What one onboarding request needs vs inventory: available / low stock / shortage."""
    hw = request.hardware
    if hw is None:
        return []
    avail = availability_by_kind(db)
    reserved_here: dict[str, int] = defaultdict(int)
    for reservation, item in db.execute(
        select(StockReservation, InventoryItem)
        .join(InventoryItem, InventoryItem.id == StockReservation.item_id)
        .where(StockReservation.status == "active", StockReservation.provisioning_request_id == request.id)
    ).all():
        reserved_here[rules.kind_for_stock_item(item.item_kind, item.name, item.category)] += reservation.quantity
    lines = []
    for key, required in hardware_needs(hw).items():
        info = avail.get(key) or {}
        label = info.get("label") or (
            rules.SEAT_TYPE_LABELS.get(key.split(":", 1)[1], key)
            if key.startswith("computer:")
            else rules.ROLE_LABELS.get(key, key)
        )
        available = int(info.get("available", 0)) + reserved_here.get(key, 0)
        stock_after = int(info.get("stock_available", 0)) - max(required - reserved_here.get(key, 0), 0)
        min_stock = info.get("min_stock")
        if available < required:
            state = "shortage"
        elif info.get("stock_status") in {STATUS_LOW, STATUS_OUT} or (
            min_stock is not None and info.get("stock_available", 0) and stock_after < min_stock
        ):
            state = "low_stock"
        else:
            state = "available"
        lines.append(
            {
                "key": key,
                "label": label,
                "required": required,
                "available": available,
                "reserved_for_request": reserved_here.get(key, 0),
                "stock_status": info.get("stock_status"),
                "state": state,
            }
        )
    return lines


def overview(db: Session) -> dict[str, Any]:
    from app.models.it_operations import Asset, AssetAssignment, AssetType

    assets = db.execute(
        select(Asset, AssetType)
        .join(AssetType, AssetType.id == Asset.asset_type_id)
        .where(Asset.is_deleted.is_(False))
    ).all()
    open_asset_ids = set(
        db.scalars(select(AssetAssignment.asset_id).where(AssetAssignment.returned_date.is_(None))).all()
    )
    physical = defaultdict(int)
    computers = defaultdict(int)
    monitors = defaultdict(int)
    by_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    inactive = {"retired", "disposed", "returned_to_customer", "lost"}
    for asset, asset_type in assets:
        role = rules.role_for_asset_type(asset_type)
        group = rules.group_for_role(role)
        status = asset.status
        assigned = asset.id in open_asset_ids
        in_stock = status == "available" and not assigned
        if status not in inactive:
            physical["total"] += 1
            by_group[group]["total"] += 1
        if in_stock:
            physical["in_stock"] += 1
            by_group[group]["in_stock"] += 1
        if assigned:
            physical["assigned"] += 1
            by_group[group]["assigned"] += 1
        for key in ("maintenance", "reserved", "awaiting_return"):
            if status == key:
                physical[key] += 1
                by_group[group][key] += 1
        if status in {"retired", "disposed"}:
            physical["retired"] += 1
        if role == rules.ROLE_COMPUTER and status not in inactive:
            laptop = rules.is_laptop_type(asset_type)
            if in_stock:
                computers["laptops_in_stock" if laptop else "workstations_in_stock"] += 1
            if assigned:
                computers["assigned"] += 1
            if status == "maintenance":
                computers["maintenance"] += 1
            if status == "reserved":
                computers["reserved"] += 1
        if role == rules.ROLE_MONITOR and status not in inactive:
            monitors["total"] += 1
            if in_stock:
                monitors["in_stock"] += 1
            if assigned:
                monitors["assigned"] += 1
            if status == "maintenance":
                monitors["maintenance"] += 1

    stock = item_rows(db)
    consumables = {
        "total_items": len(stock),
        "low_stock": sum(1 for r in stock if r["stock_status"] == STATUS_LOW),
        "out_of_stock": sum(1 for r in stock if r["stock_status"] == STATUS_OUT),
        "reorder_needed": sum(1 for r in stock if r["reorder_needed"]),
        "incoming_units": sum(r["incoming"] for r in stock),
        "pending_restock": sum(r["pending_restock_requests"] for r in stock),
        "no_minimum": sum(1 for r in stock if r["min_stock"] is None),
    }
    demand = upcoming_demand(db)
    by_kind = availability_by_kind(db)
    return {
        "physical": {
            "total": physical["total"],
            "in_stock": physical["in_stock"],
            "assigned": physical["assigned"],
            "maintenance": physical["maintenance"],
            "reserved": physical["reserved"],
            "pending_return": physical["awaiting_return"],
            "retired": physical["retired"],
        },
        "computers": {
            "workstations_in_stock": computers["workstations_in_stock"],
            "laptops_in_stock": computers["laptops_in_stock"],
            "assigned": computers["assigned"],
            "maintenance": computers["maintenance"],
            "reserved": computers["reserved"],
        },
        "monitors": {
            "total": monitors["total"],
            "in_stock": monitors["in_stock"],
            "assigned": monitors["assigned"],
            "maintenance": monitors["maintenance"],
        },
        "by_group": [
            {"group": group, "label": rules.GROUP_LABELS.get(group, group), **dict(counts)}
            for group, counts in sorted(by_group.items())
        ],
        "consumables": consumables,
        "available_by_kind": sorted(
            by_kind.values(), key=lambda row: (not row["key"].startswith("computer"), row["label"])
        ),
        "low_stock_items": [
            {
                "id": r["id"],
                "name": r["name"],
                "available": r["available"],
                "min_stock": r["min_stock"],
                "stock_status": r["stock_status"],
                "shortfall": r["shortfall"],
                "recommended_order_qty": r["recommended_order_qty"],
                "incoming": r["incoming"],
            }
            for r in stock
            if r["stock_status"] in {STATUS_LOW, STATUS_OUT}
        ],
        "upcoming_demand": demand,
        "upcoming_shortages": sum(1 for row in demand if row["shortage"]),
    }


def locations(db: Session, *, include_inactive: bool = False) -> list[StockLocation]:
    stmt = select(StockLocation).order_by(StockLocation.name)
    if not include_inactive:
        stmt = stmt.where(StockLocation.is_active.is_(True))
    return list(db.scalars(stmt).all())


def create_location(db: Session, *, name: str, notes: str | None = None) -> StockLocation:
    clean = (name or "").strip()
    if not clean:
        raise ProTrackValidationError("Location name is required.")
    if db.scalar(select(StockLocation).where(func.lower(StockLocation.name) == clean.lower())):
        raise ProTrackValidationError(f"Location '{clean}' already exists.")
    row = StockLocation(id=uuid4(), name=clean, notes=(notes or "").strip() or None, is_active=True)
    db.add(row)
    db.flush()
    return row
