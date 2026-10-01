"""Computer / peripheral availability by type and shift — batch view over the engine.

Every slot is decided by ``resource_allocation_engine.evaluate_asset`` (the same
rule that validates asset assignment), so the dashboard, Find Available Computer,
Virtual Seats and reports all answer "which computer can I assign for this
window?" identically.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    ResourceReservation,
    WorkstationPackageMember,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_inventory_rules as rules
from app.services import resource_allocation_engine as allocation
from app.services import resource_shift_service as shifts
from app.services.virtual_seat_service import seat_type_for

_INACTIVE = frozenset({"retired", "disposed", "returned_to_customer", "lost"})
_ENGINE_SLOT = {
    allocation.AVAILABLE: "AVAILABLE",
    allocation.ASSIGNED: "ASSIGNED",
    allocation.CONFLICT: "CONFLICT",
    allocation.RESERVED: "RESERVED",
    allocation.UNAVAILABLE: "UNAVAILABLE",
}


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _load_assets(db: Session, roles: set[str]) -> list[tuple[Asset, AssetType, str]]:
    return [
        (asset, asset_type, role)
        for asset, asset_type in db.execute(
            select(Asset, AssetType)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(Asset.is_deleted.is_(False), Asset.status.not_in(_INACTIVE))
            .order_by(Asset.asset_number)
        ).all()
        if (role := rules.role_for_asset_type(asset_type)) in roles
    ]


def _context(db: Session, asset_ids: list[UUID], when: date, shift_map: dict[UUID, ResourceShift]):
    rows: dict[UUID, list[AssetAssignment]] = defaultdict(list)
    reservations: dict[UUID, list[ResourceReservation]] = defaultdict(list)
    if asset_ids:
        for row in db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.asset_id.in_(asset_ids),
                or_(AssetAssignment.returned_date.is_(None), AssetAssignment.returned_date > when),
            )
        ).all():
            rows[row.asset_id].append(row)
        for res in db.scalars(
            select(ResourceReservation).where(
                ResourceReservation.asset_id.in_(asset_ids), ResourceReservation.status == "ACTIVE"
            )
        ).all():
            if allocation.dates_overlap(res.start_date, res.end_date, when, when):
                reservations[res.asset_id].append(res)
    user_ids = {r.assigned_to_user_id for rs in rows.values() for r in rs}
    user_ids |= {r.user_id for rs in reservations.values() for r in rs if r.user_id}
    names = (
        {u.id: _name(u) for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    extra = {r.shift_id for rs in rows.values() for r in rs if r.shift_id} - set(shift_map)
    extra |= {r.shift_id for rs in reservations.values() for r in rs if r.shift_id} - set(shift_map)
    if extra:
        shift_map.update(
            {s.id: s for s in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(extra))).all()}
        )
    packaged = set(
        db.scalars(
            select(WorkstationPackageMember.asset_id).where(
                WorkstationPackageMember.asset_id.in_(asset_ids),
                WorkstationPackageMember.follows_workstation.is_(True),
                WorkstationPackageMember.effective_from <= when,
                or_(
                    WorkstationPackageMember.effective_to.is_(None),
                    WorkstationPackageMember.effective_to >= when,
                ),
            )
        ).all()
    ) if asset_ids else set()
    return rows, reservations, names, packaged


def _slot(
    db: Session,
    asset: Asset,
    window: allocation.Window,
    when: date,
    *,
    rows: list[AssetAssignment],
    reservations: list[ResourceReservation],
    shift_map: dict[UUID, ResourceShift],
    names: dict[UUID, str | None],
    packaged: bool,
) -> dict[str, Any]:
    request = allocation.AllocationRequest(start_date=when, end_date=when, window=window)
    result = allocation.evaluate_asset(
        db,
        asset,
        request,
        rows=rows,
        reservations=reservations,
        shift_map=shift_map,
        names={k: v for k, v in names.items() if v},
        check_packages=packaged,
    )
    first = (result["conflicting_assignments"] or [{}])[0]
    return {
        "status": _ENGINE_SLOT.get(result["status"], "UNAVAILABLE"),
        "reason": None if result["available"] else result["reason"],
        "reason_code": result["reason_code"],
        "assignee_name": first.get("user_name") if not result["available"] else None,
    }


def computer_availability(
    db: Session,
    *,
    on_date: date | None = None,
    seat_type: str | None = None,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    only_available: bool = False,
    search: str | None = None,
) -> dict[str, Any]:
    """Computers × shift slots (or one custom window) with the engine's verdict."""
    when = on_date or date.today()
    shifts.ensure_company_standard_shifts(db)
    all_shifts = list(
        db.scalars(
            select(ResourceShift).where(ResourceShift.is_active.is_(True)).order_by(ResourceShift.start_time)
        ).all()
    )
    shift_map = {s.id: s for s in all_shifts}
    custom = bool(start_time and end_time)
    if custom:
        base_shift = shift_map.get(shift_id) if shift_id else None
        custom_window = allocation.window_from_times(start_time, end_time, shift=base_shift)
        slots_def = [("CUSTOM", custom_window.label, custom_window, shift_id)]
    else:
        slots_def = [
            (s.code, shifts.format_shift_label(s), allocation.window_for_shift(s), s.id)
            for s in all_shifts
            if shift_id is None or s.id == shift_id
        ]

    computers = _load_assets(db, {rules.ROLE_COMPUTER})
    asset_ids = [a.id for a, _, _ in computers]
    rows, reservations, names, packaged = _context(db, asset_ids, when, shift_map)
    computer_names = (
        {c.asset_id: c.computer_name for c in db.scalars(select(Computer).where(Computer.asset_id.in_(asset_ids))).all()}
        if asset_ids
        else {}
    )

    q = (search or "").strip().lower()
    rows_out = []
    summary: dict[str, dict[str, Any]] = {}
    for asset, asset_type, _role in computers:
        code = seat_type_for(asset, asset_type)
        if seat_type and code != seat_type:
            continue
        occupants = [
            r for r in rows.get(asset.id, [])
            if allocation.dates_overlap(*allocation._row_dates(r), when, when)
        ]
        if q:
            haystack = " ".join(
                str(v or "")
                for v in [asset.asset_number, computer_names.get(asset.id), asset.make, asset.model, asset.serial_number]
                + [names.get(o.assigned_to_user_id) for o in occupants]
            ).lower()
            if q not in haystack:
                continue
        slots = []
        for slot_code, slot_label, window, slot_shift_id in slots_def:
            verdict = _slot(
                db, asset, window, when,
                rows=occupants, reservations=reservations.get(asset.id, []),
                shift_map=shift_map, names=names, packaged=asset.id in packaged,
            )
            slots.append(
                {
                    "shift_id": str(slot_shift_id) if slot_shift_id else None,
                    "shift_code": slot_code,
                    "shift_display": slot_label,
                    "window": window.times,
                    **verdict,
                }
            )
        if only_available and not any(s["status"] == "AVAILABLE" for s in slots):
            continue
        bucket = summary.setdefault(
            code,
            {
                "seat_type": code,
                "label": rules.SEAT_TYPE_LABELS.get(code, code),
                "total": 0,
                "by_shift": {c: 0 for c, *_ in slots_def},
            },
        )
        bucket["total"] += 1
        for slot in slots:
            if slot["status"] == "AVAILABLE":
                bucket["by_shift"][slot["shift_code"]] += 1
        rows_out.append(
            {
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "computer_name": computer_names.get(asset.id),
                "asset_type": asset_type.name,
                "seat_type": code,
                "seat_type_label": rules.SEAT_TYPE_LABELS.get(code, code),
                "make": asset.make,
                "model": asset.model,
                "status": asset.status,
                "location": asset.location,
                "is_laptop": rules.is_laptop_type(asset_type),
                "occupants": [
                    {
                        "user_id": str(o.assigned_to_user_id),
                        "user_name": names.get(o.assigned_to_user_id),
                        "shift_display": allocation.window_for_row(o, shift_map).label,
                        "needs_review": allocation.window_for_row(o, shift_map).legacy,
                    }
                    for o in occupants
                ],
                "shifts": slots,
            }
        )
    return {
        "on_date": when,
        "custom_window": slots_def[0][2].times if custom else None,
        "shifts": [
            {"shift_id": str(sid) if sid else None, "shift_code": c, "shift_display": label}
            for c, label, _w, sid in slots_def
        ],
        "summary": sorted(summary.values(), key=lambda row: row["label"]),
        "computers": rows_out,
        "peripherals": peripheral_availability(
            db, on_date=when, windows=[(c, w) for c, _l, w, _s in slots_def], shift_map=shift_map
        ),
    }


def peripheral_availability(
    db: Session,
    *,
    on_date: date,
    windows: list[tuple[str, allocation.Window]],
    shift_map: dict[UUID, ResourceShift] | None = None,
) -> list[dict[str, Any]]:
    """Free reusable peripherals (monitors, 3D mice, docks) per window."""
    roles = {rules.ROLE_MONITOR, rules.ROLE_MOUSE_3D, rules.ROLE_DOCK}
    assets = _load_assets(db, roles)
    shift_map = dict(shift_map or {})
    rows, reservations, names, _ = _context(db, [a.id for a, _, _ in assets], on_date, shift_map)
    out = []
    for role in (rules.ROLE_MONITOR, rules.ROLE_MOUSE_3D, rules.ROLE_DOCK):
        subset = [a for a, _, r in assets if r == role]
        by_window = {}
        for code, window in windows:
            free = 0
            for asset in subset:
                verdict = _slot(
                    db, asset, window, on_date,
                    rows=rows.get(asset.id, []), reservations=reservations.get(asset.id, []),
                    shift_map=shift_map, names=names, packaged=False,
                )
                free += verdict["status"] == "AVAILABLE"
            by_window[code] = free
        out.append(
            {"role": role, "label": rules.ROLE_LABELS[role], "total": len(subset), "available_by_shift": by_window}
        )
    return out
