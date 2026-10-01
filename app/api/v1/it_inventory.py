"""IT inventory (consumable stock), Virtual Seats and computer availability APIs."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_HUMAN_RESOURCES,
    MODULE_IT_OPERATIONS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_MANAGE_IT_SETTINGS,
    SPECIAL_VIEW_IT_OPERATIONS,
)
from app.core.exceptions import ProTrackValidationError
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name, is_admin, user_has_module, user_has_special
from app.models.it_operations import (
    InventoryItem,
    ItProvisioningRequest,
    RestockRequest,
    StockReservation,
    VirtualSeat,
)
from app.models.models import User
from app.schemas.it_inventory import (
    ReservationRelease,
    RestockCreate,
    RestockUpdate,
    SeatRequirementsUpdate,
    StockAdjust,
    StockIssue,
    StockItemCreate,
    StockItemUpdate,
    StockLocationCreate,
    StockReceive,
    StockReserve,
    StockReturn,
    StockTransfer,
    StockWriteOff,
)
from app.services import it_availability_service as availability
from app.services import it_inventory_reports as reports
from app.services import it_inventory_rules as rules
from app.services import it_stock_service as stock
from app.services import virtual_seat_service as seats

router = APIRouter(prefix="/it", tags=["it-inventory"], dependencies=[Depends(get_current_user)])


def _fail(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.detail)


def _role(db: Session, user: User) -> str:
    return get_role_name(db, user)


def _can_view(db: Session, user: User) -> bool:
    role = _role(db, user)
    return (
        is_admin(db, user)
        or user_has_module(user, role, MODULE_IT_OPERATIONS)
        or user_has_special(user, role, SPECIAL_VIEW_IT_OPERATIONS)
    )


def _require_view(db: Session, user: User) -> None:
    if not _can_view(db, user):
        raise HTTPException(status_code=403, detail="IT Operations access required.")


def _require_manage(db: Session, user: User) -> None:
    if is_admin(db, user) or user_has_special(user, _role(db, user), SPECIAL_MANAGE_IT_ASSETS):
        return
    raise HTTPException(status_code=403, detail="Requires manage_it_assets permission.")


def _require_assign(db: Session, user: User) -> None:
    role = _role(db, user)
    if (
        is_admin(db, user)
        or user_has_special(user, role, SPECIAL_ASSIGN_IT_ASSETS)
        or user_has_special(user, role, SPECIAL_MANAGE_IT_ASSETS)
    ):
        return
    raise HTTPException(status_code=403, detail="Requires assign_it_assets permission.")


def _require_employee_view(db: Session, user: User, employee_id: UUID) -> None:
    if user.id == employee_id or _can_view(db, user):
        return
    if user_has_module_action(user, _role(db, user), MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW):
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions.")


def _item(db: Session, item_id: UUID) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Stock item not found.")
    return item


def _item_row(db: Session, item_id: UUID) -> dict[str, Any]:
    rows = [r for r in stock.item_rows(db, include_archived=True) if r["id"] == str(item_id)]
    if not rows:
        raise HTTPException(status_code=404, detail="Stock item not found.")
    return rows[0]


def _commit(db: Session, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        db.commit()
        return result
    except ProTrackValidationError as exc:
        db.rollback()
        raise _fail(exc) from exc


# --- Reference data -------------------------------------------------------------------


@router.get("/inventory/reference")
def inventory_reference(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    from sqlalchemy import select

    from app.models.resource_shifts import ResourceShift
    from app.services import resource_shift_service

    resource_shift_service.ensure_company_standard_shifts(db)
    active_shifts = db.scalars(
        select(ResourceShift).where(ResourceShift.is_active.is_(True)).order_by(ResourceShift.start_time)
    ).all()
    return {
        "shifts": [
            {"id": str(s.id), "code": s.code, "label": resource_shift_service.format_shift_label(s)}
            for s in active_shifts
        ],
        "roles": [{"code": code, "label": label} for code, label in rules.ROLE_LABELS.items()],
        "stock_kinds": [{"code": code, "label": rules.ROLE_LABELS[code]} for code in rules.STOCK_KINDS],
        "groups": [{"code": code, "label": label} for code, label in rules.GROUP_LABELS.items()],
        "seat_types": [{"code": code, "label": label} for code, label in rules.SEAT_TYPE_LABELS.items()],
        "locations": [
            {"id": str(loc.id), "name": loc.name, "notes": loc.notes} for loc in stock.locations(db)
        ],
    }


@router.post("/inventory/locations", status_code=201)
def create_location(
    payload: StockLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    row = _commit(db, stock.create_location, db, name=payload.name, notes=payload.notes)
    return {"id": str(row.id), "name": row.name, "notes": row.notes}


# --- Overview / items -----------------------------------------------------------------


@router.get("/inventory/overview")
def inventory_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    data = stock.overview(db)
    data["virtual_seats"] = seats.seat_summary(seats.derive_seats(db))
    return data


@router.get("/inventory/items")
def list_items(
    search: str | None = Query(None),
    kind: str | None = Query(None),
    location_id: UUID | None = Query(None),
    stock_status: str | None = Query(None),
    supplier_id: UUID | None = Query(None),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return stock.item_rows(
        db,
        search=search,
        kind=kind,
        location_id=location_id,
        stock_status_filter=stock_status,
        supplier_id=supplier_id,
        include_archived=include_archived,
    )


@router.post("/inventory/items", status_code=201)
def create_item(
    payload: StockItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    data = payload.model_dump(exclude={"opening_qty"}, exclude_unset=True)
    item = _commit(db, stock.create_item, db, actor=current_user, data=data, opening_qty=payload.opening_qty)
    return _item_row(db, item.id)


@router.get("/inventory/items/{item_id}")
def get_item(item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    row = _item_row(db, item_id)
    movements, _total = stock.movement_rows(db, item_id=item_id, limit=50)
    row["recent_movements"] = movements
    row["reservations"] = stock.reservation_rows(db, item_id=item_id)
    row["restock_requests"] = stock.restock_rows(db, item_id=item_id)
    return row


@router.patch("/inventory/items/{item_id}")
def update_item(
    item_id: UUID,
    payload: StockItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.update_item, db, item, actor=current_user, data=payload.model_dump(exclude_unset=True))
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/receive")
def receive_stock(
    item_id: UUID,
    payload: StockReceive,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.receive, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/issue")
def issue_stock(
    item_id: UUID,
    payload: StockIssue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.issue, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/return")
def return_stock(
    item_id: UUID,
    payload: StockReturn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.return_to_stock, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/adjust")
def adjust_stock(
    item_id: UUID,
    payload: StockAdjust,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.adjust, db, item, actor=current_user, counted_qty=payload.counted_qty, reason=payload.reason)
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/write-off")
def write_off_stock(
    item_id: UUID,
    payload: StockWriteOff,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.write_off, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/transfer")
def transfer_stock(
    item_id: UUID,
    payload: StockTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.transfer, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


@router.post("/inventory/items/{item_id}/reserve", status_code=201)
def reserve_stock(
    item_id: UUID,
    payload: StockReserve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    item = _item(db, item_id)
    _commit(db, stock.reserve, db, item, actor=current_user, **payload.model_dump())
    return _item_row(db, item_id)


# --- Movements / reservations / restock -----------------------------------------------


@router.get("/inventory/movements")
def list_movements(
    item_id: UUID | None = Query(None),
    movement_type: str | None = Query(None),
    employee_user_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    rows, total = stock.movement_rows(
        db,
        item_id=item_id,
        movement_type=movement_type,
        employee_user_id=employee_user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/inventory/reservations")
def list_reservations(
    item_id: UUID | None = Query(None),
    status_filter: str | None = Query("active", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return stock.reservation_rows(db, item_id=item_id, status=status_filter or None)


@router.post("/inventory/reservations/{reservation_id}/release")
def release_reservation(
    reservation_id: UUID,
    payload: ReservationRelease,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    reservation = db.get(StockReservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    _commit(db, stock.release_reservation, db, reservation, actor=current_user, reason=payload.reason)
    return _item_row(db, reservation.item_id)


@router.get("/inventory/restock-requests")
def list_restock(
    status_filter: str | None = Query(None, alias="status"),
    item_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return stock.restock_rows(db, status=status_filter, item_id=item_id)


@router.post("/inventory/restock-requests", status_code=201)
def create_restock(
    payload: RestockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    item = _item(db, payload.item_id)
    request = _commit(
        db,
        stock.create_restock_request,
        db,
        item,
        actor=current_user,
        quantity=payload.quantity,
        supplier_id=payload.supplier_id,
        expected_date=payload.expected_date,
        notes=payload.notes,
    )
    return next(r for r in stock.restock_rows(db, item_id=item.id) if r["id"] == str(request.id))


@router.patch("/inventory/restock-requests/{request_id}")
def update_restock(
    request_id: UUID,
    payload: RestockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    request = db.get(RestockRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Restock request not found.")
    _commit(db, stock.update_restock_status, db, request, actor=current_user, **payload.model_dump())
    return next(r for r in stock.restock_rows(db, item_id=request.item_id) if r["id"] == str(request.id))


@router.get("/inventory/provisioning/{request_id}/check")
def provisioning_stock_check(
    request_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _require_view(db, current_user)
    request = db.get(ItProvisioningRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Provisioning request not found.")
    return {
        "request_id": str(request.id),
        "status": request.status,
        "lines": stock.requirement_check(db, request),
        "reservations": [
            r for r in stock.reservation_rows(db, status="active") if r["provisioning_request_id"] == str(request.id)
        ],
    }


@router.get("/inventory/employee/{user_id}")
def employee_it_setup(
    user_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _require_employee_view(db, current_user, user_id)
    return {
        "virtual_seats": seats.seats_for_user(db, user_id),
        "consumables": stock.employee_consumables(db, user_id),
    }


# --- Virtual Seats --------------------------------------------------------------------


@router.get("/virtual-seats")
def list_virtual_seats(
    search: str | None = Query(None),
    setup_status: str | None = Query(None),
    seat_type: str | None = Query(None),
    shift_id: UUID | None = Query(None),
    shared_only: bool = Query(False),
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    rows = seats.list_seats(
        db,
        actor=current_user,
        on_date=on_date,
        search=search,
        setup_status=setup_status,
        seat_type=seat_type,
        shift_id=shift_id,
        shared_only=shared_only,
    )
    return {"seats": rows, "summary": seats.seat_summary(seats.derive_seats(db, on_date=on_date))}


@router.get("/virtual-seats/requirements")
def seat_requirements(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    reqs = rules.seat_requirements(db)
    return [
        {
            "seat_type": code,
            "label": rules.SEAT_TYPE_LABELS.get(code, code),
            "lines": [
                {**line, "label": rules.ROLE_LABELS.get(line["role"], line["role"])} for line in reqs.get(code, [])
            ],
        }
        for code in rules.SEAT_TYPE_LABELS
    ]


@router.put("/virtual-seats/requirements/{seat_type}")
def update_seat_requirements(
    seat_type: str,
    payload: SeatRequirementsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = _role(db, current_user)
    if not (
        is_admin(db, current_user)
        or user_has_special(current_user, role, SPECIAL_MANAGE_IT_SETTINGS)
        or user_has_special(current_user, role, SPECIAL_MANAGE_IT_ASSETS)
    ):
        raise HTTPException(status_code=403, detail="Requires manage_it_settings permission.")
    _commit(
        db,
        rules.save_seat_requirements,
        db,
        seat_type,
        [line.model_dump() for line in payload.lines],
        actor=current_user,
    )
    return seat_requirements(db=db, current_user=current_user)


@router.get("/virtual-seats/{seat_id}/history")
def virtual_seat_history(
    seat_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _require_view(db, current_user)
    if db.get(VirtualSeat, seat_id) is None:
        raise HTTPException(status_code=404, detail="Virtual seat not found.")
    return seats.seat_history(db, seat_id)


# --- Reports --------------------------------------------------------------------------


@router.get("/inventory/reports")
def inventory_report_catalog(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    return reports.catalog()


@router.get("/inventory/reports/{report_key}")
def inventory_report(
    report_key: str,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    movement_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    try:
        return reports.run_report(
            db, report_key, date_from=date_from, date_to=date_to, movement_type=movement_type
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc


# --- Availability ---------------------------------------------------------------------


@router.get("/availability/computers")
def computers_availability(
    on_date: date | None = Query(None),
    seat_type: str | None = Query(None),
    shift_id: UUID | None = Query(None),
    start_time: str | None = Query(None, max_length=5),
    end_time: str | None = Query(None, max_length=5),
    only_available: bool = Query(False),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    try:
        return availability.computer_availability(
            db,
            on_date=on_date,
            seat_type=seat_type,
            shift_id=shift_id,
            start_time=start_time,
            end_time=end_time,
            only_available=only_available,
            search=search,
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
