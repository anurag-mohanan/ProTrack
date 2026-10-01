"""Tabular inventory / virtual-seat reports built on the stock, seat and availability services."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.services import it_availability_service as availability
from app.services import it_stock_service as stock
from app.services import resource_allocation_engine as allocation
from app.services import virtual_seat_service as seats

Column = tuple[str, str]


def _stock_columns() -> list[Column]:
    return [
        ("name", "Item"),
        ("item_kind_label", "Kind"),
        ("location_name", "Location"),
        ("on_hand", "On hand"),
        ("reserved", "Reserved"),
        ("available", "Available"),
        ("min_stock", "Min stock"),
        ("stock_status", "Status"),
        ("supplier_name", "Supplier"),
        ("last_movement_on", "Last movement"),
    ]


def _consumable_stock(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    return _stock_columns(), stock.item_rows(db)


def _low_stock(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    rows = [r for r in stock.item_rows(db) if r["stock_status"] in {stock.STATUS_LOW, stock.STATUS_OUT}]
    return _stock_columns() + [("shortfall", "Shortfall"), ("incoming", "Incoming")], rows


def _reorder(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    rows = [r for r in stock.item_rows(db) if r["reorder_needed"]]
    columns: list[Column] = [
        ("name", "Item"),
        ("available", "Available"),
        ("incoming", "Incoming"),
        ("min_stock", "Min stock"),
        ("reorder_point", "Reorder point"),
        ("target_stock", "Target"),
        ("recommended_order_qty", "Recommended qty"),
        ("supplier_name", "Supplier"),
        ("supplier_sku", "Supplier SKU"),
        ("lead_time_days", "Lead time (days)"),
        ("last_purchase_date", "Last purchase"),
        ("location_name", "Location"),
    ]
    return columns, rows


def _stock_movements(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    rows, _total = stock.movement_rows(
        db,
        date_from=params.get("date_from"),
        date_to=params.get("date_to"),
        movement_type=params.get("movement_type"),
        limit=5000,
    )
    columns: list[Column] = [
        ("occurred_on", "Date"),
        ("item_name", "Item"),
        ("movement_type", "Type"),
        ("quantity", "Qty"),
        ("previous_qty", "Before"),
        ("new_qty", "After"),
        ("employee_name", "Employee"),
        ("performed_by_name", "Performed by"),
        ("reason", "Reason"),
        ("reference", "Reference"),
        ("purchase_order", "PO"),
        ("invoice_number", "Invoice"),
    ]
    return columns, rows


def _seat_rows(db: Session) -> list[dict]:
    rows = []
    for seat in seats.derive_seats(db):
        primary = seat["primary"] or {}
        counts = seat["counts"]
        rows.append(
            {
                "id": seat["seat_id"] or f"{seat['user_id']}:{primary.get('asset_id')}",
                "seat_code": seat["seat_code"],
                "user_name": seat["user_name"],
                "employee_code": seat["employee_code"],
                "shift_display": seat["shift_display"],
                "primary_device": primary.get("asset_number"),
                "computer_name": primary.get("computer_name"),
                "seat_type_label": seat["seat_type_label"],
                "monitors": counts.get("monitor", 0),
                "mouse_3d": counts.get("mouse_3d", 0),
                "setup_status": seat["setup_status"],
                "missing_required": ", ".join(seat["missing_required"]),
                "shared_with": ", ".join(
                    f"{s['user_name']} ({s['shift_display'] or 'no shift'})" for s in seat["shared_with"]
                ),
                "conflicts": len(seat["conflicts"]),
            }
        )
    return rows


_SEAT_COLUMNS: list[Column] = [
    ("seat_code", "Seat"),
    ("user_name", "Employee"),
    ("employee_code", "Emp code"),
    ("shift_display", "Shift"),
    ("primary_device", "Primary device"),
    ("seat_type_label", "Type"),
    ("monitors", "Monitors"),
    ("mouse_3d", "3D mouse"),
    ("setup_status", "Status"),
    ("missing_required", "Missing required"),
    ("shared_with", "Shared with"),
]


def _virtual_seats(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    return _SEAT_COLUMNS, _seat_rows(db)


def _shared_workstations(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    return _SEAT_COLUMNS + [("conflicts", "Conflicts")], [r for r in _seat_rows(db) if r["shared_with"]]


def _available_workstations(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    data = availability.computer_availability(db, on_date=params.get("date_to"), only_available=True)
    shift_cols: list[Column] = [(f"shift_{s['shift_code']}", s["shift_display"]) for s in data["shifts"]]
    rows = []
    for row in data["computers"]:
        flat = {
            "id": row["asset_id"],
            "asset_number": row["asset_number"],
            "computer_name": row["computer_name"],
            "seat_type_label": row["seat_type_label"],
            "make_model": " ".join(v for v in [row["make"], row["model"]] if v),
            "location": row["location"],
            "occupants": ", ".join(
                f"{o['user_name']} ({o['shift_display'] or 'no shift'})" for o in row["occupants"]
            ),
        }
        for slot in row["shifts"]:
            flat[f"shift_{slot['shift_code']}"] = slot["status"]
        rows.append(flat)
    columns: list[Column] = [
        ("asset_number", "Asset #"),
        ("computer_name", "Computer"),
        ("seat_type_label", "Type"),
        ("make_model", "Make / model"),
        ("location", "Location"),
        ("occupants", "Current users"),
    ]
    return columns + shift_cols, rows


def _upcoming_demand(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    rows = [{"id": r["key"], **r} for r in stock.upcoming_demand(db)]
    columns: list[Column] = [
        ("label", "Requirement"),
        ("required", "Required (open onboarding)"),
        ("committed", "Already reserved"),
        ("available", "Available now"),
        ("incoming", "Incoming"),
        ("projected", "Projected after demand"),
        ("shortage", "Shortage"),
    ]
    return columns, rows


def _pools(db: Session) -> list[Any]:
    from sqlalchemy import select

    from app.models.it_operations import SoftwareLicensePool

    return [
        p for p in db.scalars(select(SoftwareLicensePool)).all()
        if (getattr(p, "status", None) or "active") == "active"
    ]


def _pool_label(db: Session, pool: Any, cache: dict) -> str:
    from app.models.it_operations import SoftwareCatalog

    if pool.software_id not in cache:
        soft = db.get(SoftwareCatalog, pool.software_id)
        cache[pool.software_id] = soft.name if soft else "Software"
    code = pool.entitlement_code
    return f"{cache[pool.software_id]} ({code})" if code else cache[pool.software_id]


def _license_allocation(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    names: dict = {}
    rows = []
    for pool in _pools(db):
        s = allocation.license_summary(db, pool, on_date=params.get("date_to"))
        rows.append({
            "id": str(pool.id),
            "license": _pool_label(db, pool, names),
            "metric": s["metric_label"],
            "rights_owned": s["rights_owned"],
            "authorized_users": s["authorized_users"],
            "rights_allocated": s["rights_allocated"],
            "active_usage": s["active_usage"],
            "available_rights": "Unlimited" if s["available_rights"] is None else s["available_rights"],
            "compliance_status": s["compliance_status"],
            "compliance_reason": s["compliance_reason"],
            "expiry_date": pool.expiry_date.isoformat() if pool.expiry_date else None,
        })
    columns: list[Column] = [
        ("license", "License"),
        ("metric", "Metric"),
        ("rights_owned", "Rights owned"),
        ("authorized_users", "Authorized users"),
        ("rights_allocated", "Allocated / scheduled peak"),
        ("active_usage", "Active usage"),
        ("available_rights", "Available"),
        ("compliance_status", "Compliance"),
        ("compliance_reason", "Detail"),
        ("expiry_date", "Expiry"),
    ]
    return columns, rows


def _license_schedule(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    names: dict = {}
    rows = []
    for pool in _pools(db):
        sched = allocation.license_schedule(db, pool, on_date=params.get("date_to"))
        label = _pool_label(db, pool, names)
        metric = sched["summary"]["metric_label"]
        for entry in sched["scheduled"]:
            rows.append({"id": f"{pool.id}:{entry['id']}", "license": label, "metric": metric,
                         "user_name": entry.get("user_name"), "kind": entry["kind"],
                         "window": entry.get("window"), "dates": entry.get("dates")})
        for entry in sched["authorized_only"]:
            rows.append({"id": f"{pool.id}:{entry['id']}", "license": label, "metric": metric,
                         "user_name": entry.get("user_name"), "kind": "authorization",
                         "window": entry.get("window"), "dates": entry.get("dates")})
    columns: list[Column] = [
        ("license", "License"),
        ("metric", "Metric"),
        ("user_name", "Employee"),
        ("kind", "Type"),
        ("window", "Window"),
        ("dates", "Dates"),
    ]
    return columns, rows


def _license_conflicts(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    from sqlalchemy import select

    from app.models.it_operations import SoftwareAssignment

    names: dict = {}
    rows = []
    for pool in _pools(db):
        s = allocation.license_summary(db, pool, on_date=params.get("date_to"))
        if s["compliance_status"] in {"OVER_ALLOCATED", "EXPIRED"} or s["metric"] == allocation.METRIC_UNSPECIFIED:
            rows.append({"id": f"pool:{pool.id}", "license": _pool_label(db, pool, names),
                         "issue": s["compliance_status"] if s["metric"] != allocation.METRIC_UNSPECIFIED
                         else "METRIC NOT CONFIGURED",
                         "detail": s["compliance_reason"] if s["metric"] != allocation.METRIC_UNSPECIFIED
                         else s["metric_rule"],
                         "user_name": None, "override_reason": None})
    overridden = db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.released_date.is_(None), SoftwareAssignment.override_reason.is_not(None)
        )
    ).all()
    user_names = allocation._names(db, [r.user_id for r in overridden])
    for r in overridden:
        pool = next((p for p in _pools(db) if p.id == r.license_pool_id), None)
        rows.append({"id": f"sw:{r.id}", "license": _pool_label(db, pool, names) if pool else None,
                     "issue": "OVERRIDDEN CONFLICT", "detail": "Assigned despite a conflict.",
                     "user_name": user_names.get(r.user_id), "override_reason": r.override_reason})
    columns: list[Column] = [
        ("license", "License"),
        ("issue", "Issue"),
        ("detail", "Detail"),
        ("user_name", "Employee"),
        ("override_reason", "Override reason"),
    ]
    return columns, rows


def _utilization_by_shift(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    data = availability.computer_availability(db, on_date=params.get("date_to"))
    rows = []
    for shift in data["shifts"]:
        code = shift["shift_code"]
        slots = [slot for row in data["computers"] for slot in row["shifts"] if slot["shift_code"] == code]
        usable = [s for s in slots if s["status"] != "UNAVAILABLE"]
        free = sum(1 for s in usable if s["status"] == "AVAILABLE")
        occupied = len(usable) - free
        rows.append({
            "id": code,
            "shift": shift["shift_display"],
            "computers": len(slots),
            "usable": len(usable),
            "occupied": occupied,
            "free": free,
            "utilization": f"{round(occupied * 100 / len(usable))}%" if usable else "—",
        })
    columns: list[Column] = [
        ("shift", "Shift"),
        ("computers", "Computers"),
        ("usable", "Usable (lifecycle OK)"),
        ("occupied", "Occupied / conflicting"),
        ("free", "Free"),
        ("utilization", "Utilization"),
    ]
    return columns, rows


def _legacy_assignments(db: Session, _params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    from app.services import resource_assignment_service as assignments

    review = assignments.legacy_review(db)
    rows = [{"id": r["assignment_id"], **r} for r in review["assignments"]]
    columns: list[Column] = [
        ("asset_number", "Asset #"),
        ("role_label", "Component"),
        ("user_name", "Employee"),
        ("assigned_date", "Assigned"),
        ("status", "Status"),
        ("reason", "Reason"),
    ]
    return columns, rows


def _assignment_history(db: Session, params: dict[str, Any]) -> tuple[list[Column], list[dict]]:
    from sqlalchemy import select

    from app.models.it_operations import Asset, AssetAssignment

    stmt = select(AssetAssignment).order_by(AssetAssignment.assigned_date.desc()).limit(5000)
    if params.get("date_from"):
        stmt = stmt.where(AssetAssignment.assigned_date >= params["date_from"])
    if params.get("date_to"):
        stmt = stmt.where(AssetAssignment.assigned_date <= params["date_to"])
    records = db.scalars(stmt).all()
    shift_map = allocation._shift_map(db, records)
    user_names = allocation._names(
        db, [r.assigned_to_user_id for r in records] + [r.released_by_user_id for r in records]
    )
    assets = {a.id: a for a in db.scalars(select(Asset).where(Asset.id.in_({r.asset_id for r in records}))).all()} \
        if records else {}
    rows = []
    for r in records:
        window = allocation.window_for_row(r, shift_map)
        rows.append({
            "id": str(r.id),
            "asset_number": assets[r.asset_id].asset_number if r.asset_id in assets else None,
            "user_name": user_names.get(r.assigned_to_user_id),
            "assignment_type": r.assignment_type,
            "window": "Legacy / needs review" if window.legacy else window.label,
            "assigned_date": r.assigned_date.isoformat() if r.assigned_date else None,
            "planned_end_date": r.planned_end_date.isoformat() if r.planned_end_date else None,
            "returned_date": r.returned_date.isoformat() if r.returned_date else None,
            "released_by": user_names.get(r.released_by_user_id) if r.released_by_user_id else None,
            "purpose": r.purpose,
            "override_reason": r.override_reason,
        })
    columns: list[Column] = [
        ("asset_number", "Asset #"),
        ("user_name", "Employee"),
        ("assignment_type", "Type"),
        ("window", "Window"),
        ("assigned_date", "From"),
        ("planned_end_date", "Planned end"),
        ("returned_date", "Released"),
        ("released_by", "Released by"),
        ("purpose", "Purpose"),
        ("override_reason", "Override reason"),
    ]
    return columns, rows


REPORTS: dict[str, tuple[str, Callable[[Session, dict[str, Any]], tuple[list[Column], list[dict]]]]] = {
    "consumable_stock": ("Consumable stock", _consumable_stock),
    "low_stock": ("Low stock", _low_stock),
    "reorder": ("Reorder report", _reorder),
    "stock_movements": ("Stock movements", _stock_movements),
    "virtual_seats": ("Virtual seats", _virtual_seats),
    "available_workstations": ("Available workstations", _available_workstations),
    "shared_workstations": ("Shared workstations", _shared_workstations),
    "upcoming_demand": ("Upcoming onboarding demand", _upcoming_demand),
    "computer_utilization_by_shift": ("Computer utilization by shift", _utilization_by_shift),
    "license_allocation": ("License allocation & compliance", _license_allocation),
    "license_schedule": ("License schedule (shift usage)", _license_schedule),
    "license_conflicts": ("License conflicts & overrides", _license_conflicts),
    "legacy_assignments": ("Legacy assignments needing review", _legacy_assignments),
    "assignment_history": ("Asset assignment history", _assignment_history),
}


def catalog() -> list[dict[str, str]]:
    return [{"key": key, "title": title} for key, (title, _fn) in REPORTS.items()]


def run_report(
    db: Session,
    key: str,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    movement_type: str | None = None,
) -> dict[str, Any]:
    if key not in REPORTS:
        raise ProTrackValidationError(f"Unknown report '{key}'.", status_code=404)
    title, fn = REPORTS[key]
    columns, rows = fn(db, {"date_from": date_from, "date_to": date_to, "movement_type": movement_type})
    return {
        "key": key,
        "title": title,
        "columns": [{"field": field, "header": header} for field, header in columns],
        "rows": [{"id": r.get("id") or str(i), **r} for i, r in enumerate(rows)],
    }
