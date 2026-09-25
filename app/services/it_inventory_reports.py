"""Tabular inventory / virtual-seat reports built on the stock, seat and availability services."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.services import it_availability_service as availability
from app.services import it_stock_service as stock
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


REPORTS: dict[str, tuple[str, Callable[[Session, dict[str, Any]], tuple[list[Column], list[dict]]]]] = {
    "consumable_stock": ("Consumable stock", _consumable_stock),
    "low_stock": ("Low stock", _low_stock),
    "reorder": ("Reorder report", _reorder),
    "stock_movements": ("Stock movements", _stock_movements),
    "virtual_seats": ("Virtual seats", _virtual_seats),
    "available_workstations": ("Available workstations", _available_workstations),
    "shared_workstations": ("Shared workstations", _shared_workstations),
    "upcoming_demand": ("Upcoming onboarding demand", _upcoming_demand),
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
