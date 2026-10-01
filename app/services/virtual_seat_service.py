"""Virtual Seats — logical workstations derived from authoritative asset assignments.

A seat exists when an employee has an open ``AssetAssignment`` of a primary
computing device (workstation or laptop). Its components are the employee's
other open asset assignments plus consumables issued to them. Nothing here
creates or copies physical assets; ``VirtualSeat`` rows only give each derived
seat a stable code (VSEAT-001) and an audit trail.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    ASSIGNMENT_TYPE_PRIMARY,
    STOCK_MOVEMENT_ISSUE,
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    InventoryItem,
    StockMovement,
    VirtualSeat,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_inventory_rules as rules
from app.services import resource_allocation_engine as allocation
from app.services import resource_shift_service as shifts
from app.services.activity_service import log_activity

MODULE = "it_operations"
SEAT_ACTIVE = "active"
SEAT_ENDED = "ended"
SETUP_COMPLETE = "complete"
SETUP_INCOMPLETE = "incomplete"
SETUP_NO_PRIMARY = "no_primary_device"


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _licenses_by_user(db: Session, user_ids: set[UUID], *, on_date: date) -> dict[UUID, list[dict[str, Any]]]:
    """Active license allocations per employee with their scheduled window (None = unscheduled)."""
    from app.models.it_operations import SoftwareAssignment, SoftwareCatalog, SoftwareLicensePool

    if not user_ids:
        return {}
    rows = db.execute(
        select(SoftwareAssignment, SoftwareLicensePool, SoftwareCatalog)
        .join(SoftwareLicensePool, SoftwareLicensePool.id == SoftwareAssignment.license_pool_id)
        .join(SoftwareCatalog, SoftwareCatalog.id == SoftwareLicensePool.software_id)
        .where(
            SoftwareAssignment.user_id.in_(user_ids),
            or_(SoftwareAssignment.released_date.is_(None), SoftwareAssignment.released_date > on_date),
        )
    ).all()
    shift_ids = {a.shift_id for a, _, _ in rows if a.shift_id}
    shift_map = (
        {s.id: s for s in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(shift_ids))).all()}
        if shift_ids
        else {}
    )
    out: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for assignment, pool, software in rows:
        start = assignment.assigned_date or on_date
        if not allocation.dates_overlap(start, allocation._row_dates(assignment)[1], on_date, on_date):
            continue
        window = allocation.window_for_row(assignment, shift_map) if allocation.is_scheduled(assignment) else None
        metric = allocation.license_metric(pool)
        out[assignment.user_id].append(
            {
                "assignment_id": str(assignment.id),
                "license_pool_id": str(pool.id),
                "software_name": software.name,
                "metric": metric,
                "metric_label": allocation.METRIC_INFO[metric]["label"],
                "window_label": window.label if window else (
                    "Authorized (unscheduled)" if metric == allocation.METRIC_CONCURRENT else "All hours"
                ),
                "window": window,
            }
        )
    return out


def seat_type_for(asset: Asset, asset_type: AssetType | None) -> str:
    if asset.computer_type in rules.SEAT_TYPE_LABELS:
        return asset.computer_type
    return rules.UNCLASSIFIED_LAPTOP if rules.is_laptop_type(asset_type) else rules.UNCLASSIFIED_DESKTOP


def _open_rows(
    db: Session, *, on_date: date, user_ids: set[UUID] | None
) -> list[tuple[AssetAssignment, Asset, AssetType]]:
    stmt = (
        select(AssetAssignment, Asset, AssetType)
        .join(Asset, Asset.id == AssetAssignment.asset_id)
        .join(AssetType, AssetType.id == Asset.asset_type_id)
        .where(
            Asset.is_deleted.is_(False),
            AssetAssignment.assigned_date <= on_date,
            or_(AssetAssignment.returned_date.is_(None), AssetAssignment.returned_date > on_date),
            or_(AssetAssignment.planned_end_date.is_(None), AssetAssignment.planned_end_date >= on_date),
        )
    )
    if user_ids is not None:
        if not user_ids:
            return []
        stmt = stmt.where(AssetAssignment.assigned_to_user_id.in_(user_ids))
    return [tuple(row) for row in db.execute(stmt).all()]  # type: ignore[misc]


def _asset_occupants(
    db: Session, asset_ids: set[UUID], *, on_date: date
) -> dict[UUID, list[AssetAssignment]]:
    if not asset_ids:
        return {}
    rows = db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.asset_id.in_(asset_ids),
            AssetAssignment.assigned_date <= on_date,
            or_(AssetAssignment.returned_date.is_(None), AssetAssignment.returned_date > on_date),
            or_(AssetAssignment.planned_end_date.is_(None), AssetAssignment.planned_end_date >= on_date),
        )
    ).all()
    out: dict[UUID, list[AssetAssignment]] = defaultdict(list)
    for row in rows:
        out[row.asset_id].append(row)
    return out


def consumables_by_user(
    db: Session, user_ids: set[UUID] | None
) -> dict[UUID, list[dict[str, Any]]]:
    """Consumables issued to employees and still held (non-returnable issues always count)."""
    stmt = (
        select(StockMovement, InventoryItem)
        .join(InventoryItem, InventoryItem.id == StockMovement.item_id)
        .where(
            StockMovement.movement_type == STOCK_MOVEMENT_ISSUE,
            StockMovement.employee_user_id.is_not(None),
        )
    )
    if user_ids is not None:
        if not user_ids:
            return {}
        stmt = stmt.where(StockMovement.employee_user_id.in_(user_ids))
    held: dict[tuple[UUID, UUID], dict[str, Any]] = {}
    for movement, item in db.execute(stmt).all():
        qty = abs(movement.quantity) - (movement.returned_qty or 0)
        if qty <= 0:
            continue
        key = (movement.employee_user_id, item.id)
        row = held.setdefault(
            key,
            {
                "item_id": str(item.id),
                "name": item.name,
                "kind": rules.kind_for_stock_item(item.item_kind, item.name, item.category),
                "quantity": 0,
                "last_issued_on": None,
                "returnable": bool(item.is_returnable),
            },
        )
        row["quantity"] += qty
        issued = str(movement.occurred_on)
        if row["last_issued_on"] is None or issued > row["last_issued_on"]:
            row["last_issued_on"] = issued
    out: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for (user_id, _item_id), row in held.items():
        out[user_id].append(row)
    return out


def _completeness(
    seat_type: str,
    counts: dict[str, int],
    requirements: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str, list[str], list[str]]:
    lines = []
    missing_required: list[str] = []
    missing_optional: list[str] = []
    for req in requirements.get(seat_type, []):
        role = req["role"]
        have = counts.get(role, 0)
        required = int(req.get("required") or 0)
        recommended = int(req.get("recommended") or 0)
        if have < required:
            state = "missing_required"
            missing_required.append(rules.ROLE_LABELS.get(role, role))
        elif have < recommended:
            state = "missing_optional"
            missing_optional.append(rules.ROLE_LABELS.get(role, role))
        else:
            state = "ok"
        lines.append(
            {
                "role": role,
                "label": rules.ROLE_LABELS.get(role, role),
                "required": required,
                "recommended": recommended,
                "have": have,
                "state": state,
            }
        )
    status = SETUP_INCOMPLETE if missing_required else SETUP_COMPLETE
    return lines, status, missing_required, missing_optional


def _primary_sort_key(entry: tuple[AssetAssignment, Asset, AssetType]):
    assignment, _asset, asset_type = entry
    return (
        assignment.assignment_type != ASSIGNMENT_TYPE_PRIMARY,
        rules.is_laptop_type(asset_type),
        assignment.assigned_date,
        str(assignment.id),
    )


def derive_seats(
    db: Session,
    *,
    on_date: date | None = None,
    user_ids: set[UUID] | None = None,
    include_no_primary: bool = True,
) -> list[dict[str, Any]]:
    """Compute seats live from open assignments (batched; no per-row queries)."""
    when = on_date or date.today()
    rows = _open_rows(db, on_date=when, user_ids=user_ids)
    by_user: dict[UUID, list[tuple[AssetAssignment, Asset, AssetType]]] = defaultdict(list)
    for entry in rows:
        by_user[entry[0].assigned_to_user_id].append(entry)

    consumables = consumables_by_user(db, set(by_user) if user_ids is None else user_ids)
    all_users = set(by_user) | set(consumables)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(all_users))).all()} if all_users else {}

    primary_asset_ids = {
        asset.id for entry in rows for asset in [entry[1]] if rules.role_for_asset_type(entry[2]) == rules.ROLE_COMPUTER
    }
    occupants = _asset_occupants(db, primary_asset_ids, on_date=when)
    other_user_ids = {r.assigned_to_user_id for rs in occupants.values() for r in rs} - set(users)
    if other_user_ids:
        users.update({u.id: u for u in db.scalars(select(User).where(User.id.in_(other_user_ids))).all()})
    shift_ids = {e[0].shift_id for e in rows if e[0].shift_id} | {
        r.shift_id for rs in occupants.values() for r in rs if r.shift_id
    }
    shift_map = (
        {s.id: s for s in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(shift_ids))).all()}
        if shift_ids
        else {}
    )
    computer_names = (
        {
            c.asset_id: c.computer_name
            for c in db.scalars(select(Computer).where(Computer.asset_id.in_(primary_asset_ids))).all()
        }
        if primary_asset_ids
        else {}
    )
    records = {
        (r.user_id, r.shift_id, r.primary_asset_id): r
        for r in db.scalars(select(VirtualSeat).where(VirtualSeat.status == SEAT_ACTIVE)).all()
    }
    requirements = rules.seat_requirements(db)

    def shift_label(shift_id: UUID | None) -> str | None:
        sh = shift_map.get(shift_id) if shift_id else None
        return shifts.format_shift_label(sh) if sh else None

    def window_label(row: AssetAssignment) -> str:
        return shift_label(row.shift_id) or allocation.window_for_row(row, shift_map).label

    licenses = _licenses_by_user(db, all_users, on_date=when)

    def component_row(assignment: AssetAssignment, asset: Asset, asset_type: AssetType) -> dict[str, Any]:
        role = rules.role_for_asset_type(asset_type)
        return {
            "asset_id": str(asset.id),
            "asset_number": asset.asset_number,
            "role": role,
            "role_label": rules.ROLE_LABELS.get(role, role),
            "asset_type": asset_type.name,
            "make": asset.make,
            "model": asset.model,
            "status": asset.status,
            "assignment_id": str(assignment.id),
            "assigned_date": str(assignment.assigned_date),
            "shift_display": window_label(assignment),
        }

    seats: list[dict[str, Any]] = []
    for user_id in sorted(all_users, key=lambda uid: (_full_name(users.get(uid)) or "", str(uid))):
        user = users.get(user_id)
        entries = by_user.get(user_id, [])
        primaries = sorted(
            [e for e in entries if rules.role_for_asset_type(e[2]) == rules.ROLE_COMPUTER],
            key=_primary_sort_key,
        )
        peripherals = [
            e
            for e in entries
            if rules.role_for_asset_type(e[2]) not in {rules.ROLE_COMPUTER, rules.ROLE_NETWORK}
        ]
        held = consumables.get(user_id, [])
        components = [component_row(*e) for e in peripherals]
        counts: dict[str, int] = defaultdict(int)
        for comp in components:
            counts[comp["role"]] += 1
        for item in held:
            counts[item["kind"]] += int(item["quantity"])

        base = {
            "user_id": str(user_id),
            "user_name": _full_name(user),
            "employee_code": getattr(user, "employee_code", None),
            "user_active": bool(user and user.is_active and not user.is_deleted),
        }
        if not primaries:
            if include_no_primary and (components or held):
                seats.append(
                    {
                        **base,
                        "seat_id": None,
                        "seat_code": None,
                        "shift_id": None,
                        "shift_display": None,
                        "window": None,
                        "needs_review": False,
                        "licenses": [{k: v for k, v in lic.items() if k != "window"}
                                     for lic in licenses.get(user_id, [])],
                        "primary": None,
                        "seat_type": None,
                        "seat_type_label": None,
                        "shared_with": [],
                        "conflicts": [],
                        "components": components,
                        "consumables": held,
                        "counts": dict(counts),
                        "requirements": [],
                        "setup_status": SETUP_NO_PRIMARY,
                        "missing_required": [rules.ROLE_LABELS[rules.ROLE_COMPUTER]],
                        "missing_optional": [],
                        "is_main_seat": True,
                    }
                )
            continue

        for index, (assignment, asset, asset_type) in enumerate(primaries):
            is_main = index == 0
            seat_type = seat_type_for(asset, asset_type)
            seat_counts = dict(counts) if is_main else {}
            req_lines, status, missing_required, missing_optional = _completeness(
                seat_type, seat_counts, requirements
            )
            shared_with = []
            conflicts = []
            seat_window = allocation.window_for_row(assignment, shift_map)
            for other in occupants.get(asset.id, []):
                if other.id == assignment.id:
                    continue
                other_window = allocation.window_for_row(other, shift_map)
                entry = {
                    "user_id": str(other.assigned_to_user_id),
                    "user_name": _full_name(users.get(other.assigned_to_user_id)),
                    "shift_display": window_label(other),
                }
                if other.assigned_to_user_id != user_id:
                    shared_with.append(entry)
                if other.assigned_to_user_id != user_id and allocation.windows_overlap(seat_window, other_window):
                    conflicts.append(
                        {**entry, "reason": f"Overlapping hours on the same device "
                                            f"({allocation.describe_overlap(seat_window, other_window)})"}
                    )
            seat_licenses = [
                lic for lic in licenses.get(user_id, [])
                if lic["window"] is None or allocation.windows_overlap(lic["window"], seat_window)
            ]
            record = records.get((user_id, assignment.shift_id, asset.id))
            seats.append(
                {
                    **base,
                    "seat_id": str(record.id) if record else None,
                    "seat_code": record.code if record else None,
                    "shift_id": str(assignment.shift_id) if assignment.shift_id else None,
                    "shift_display": window_label(assignment),
                    "window": seat_window.times,
                    "needs_review": seat_window.legacy,
                    "licenses": [{k: v for k, v in lic.items() if k != "window"} for lic in seat_licenses],
                    "primary": {
                        "asset_id": str(asset.id),
                        "asset_number": asset.asset_number,
                        "computer_name": computer_names.get(asset.id),
                        "asset_type": asset_type.name,
                        "make": asset.make,
                        "model": asset.model,
                        "status": asset.status,
                        "is_laptop": rules.is_laptop_type(asset_type),
                        "assignment_id": str(assignment.id),
                        "assignment_type": assignment.assignment_type,
                        "assigned_date": str(assignment.assigned_date),
                    },
                    "seat_type": seat_type,
                    "seat_type_label": rules.SEAT_TYPE_LABELS.get(seat_type, seat_type),
                    "shared_with": shared_with,
                    "conflicts": conflicts,
                    "components": components if is_main else [],
                    "consumables": held if is_main else [],
                    "counts": seat_counts,
                    "requirements": req_lines,
                    "setup_status": status,
                    "missing_required": missing_required,
                    "missing_optional": missing_optional,
                    "is_main_seat": is_main,
                }
            )
    return seats


# --- Stable identity + audit ---------------------------------------------------------


def _next_code(db: Session) -> str:
    highest = 0
    for code in db.scalars(select(VirtualSeat.code)).all():
        tail = (code or "").rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"VSEAT-{highest + 1:03d}"


def _snapshot(seat: dict[str, Any]) -> list[str]:
    return sorted(c["asset_number"] for c in seat.get("components") or [])


def sync_seats(
    db: Session,
    *,
    actor: User | None,
    user_ids: set[UUID] | None = None,
    source: str = "assignment",
    on_date: date | None = None,
) -> int:
    """Align VirtualSeat identity rows with the derived seats; audit every change.

    Returns the number of identity rows created, changed or ended.
    """
    when = on_date or date.today()
    derived = [
        s for s in derive_seats(db, on_date=when, user_ids=user_ids, include_no_primary=False)
    ]
    stmt = select(VirtualSeat).where(VirtualSeat.status == SEAT_ACTIVE)
    if user_ids is not None:
        if not user_ids:
            return 0
        stmt = stmt.where(VirtualSeat.user_id.in_(user_ids))
    active = list(db.scalars(stmt).all())
    changes = 0

    def audit(record: VirtualSeat, action: ActivityAction, old: Any, new: Any) -> None:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_virtual_seat,
            entity_id=record.id,
            action=action,
            old_value=old,
            new_value={**(new or {}), "seat_code": record.code, "source": source},
            outcome="success",
            module=MODULE,
            commit=False,
        )

    remaining = list(derived)
    # 1) exact matches (same employee, shift slot and device)
    for record in list(active):
        match = next(
            (
                s
                for s in remaining
                if s["user_id"] == str(record.user_id)
                and s["shift_id"] == (str(record.shift_id) if record.shift_id else None)
                and s["primary"]["asset_id"] == str(record.primary_asset_id)
            ),
            None,
        )
        if match is None:
            continue
        remaining.remove(match)
        active.remove(record)
        snap = _snapshot(match)
        before = json.loads(record.component_snapshot or "[]")
        if snap != before:
            record.component_snapshot = json.dumps(snap)
            db.add(record)
            audit(
                record,
                ActivityAction.it_virtual_seat_components_changed,
                {"components": before},
                {
                    "components": snap,
                    "added": sorted(set(snap) - set(before)),
                    "removed": sorted(set(before) - set(snap)),
                },
            )
            changes += 1
    # 2) same employee + shift slot, different device → primary device changed
    for record in list(active):
        match = next(
            (
                s
                for s in remaining
                if s["user_id"] == str(record.user_id)
                and s["shift_id"] == (str(record.shift_id) if record.shift_id else None)
            ),
            None,
        )
        if match is None:
            continue
        remaining.remove(match)
        active.remove(record)
        old_asset = db.get(Asset, record.primary_asset_id)
        record.primary_asset_id = UUID(match["primary"]["asset_id"])
        record.primary_assignment_id = UUID(match["primary"]["assignment_id"])
        record.component_snapshot = json.dumps(_snapshot(match))
        db.add(record)
        audit(
            record,
            ActivityAction.it_virtual_seat_primary_changed,
            {"primary_device": old_asset.asset_number if old_asset else None},
            {"primary_device": match["primary"]["asset_number"]},
        )
        changes += 1
    # 3) seats that no longer exist
    for record in active:
        record.status = SEAT_ENDED
        record.ended_on = when
        db.add(record)
        audit(record, ActivityAction.it_virtual_seat_ended, None, {"ended_on": str(when)})
        changes += 1
    # 4) new seats
    for seat in remaining:
        db.flush()
        record = VirtualSeat(
            id=uuid4(),
            code=_next_code(db),
            user_id=UUID(seat["user_id"]),
            shift_id=UUID(seat["shift_id"]) if seat["shift_id"] else None,
            primary_asset_id=UUID(seat["primary"]["asset_id"]),
            primary_assignment_id=UUID(seat["primary"]["assignment_id"]),
            status=SEAT_ACTIVE,
            started_on=when,
            component_snapshot=json.dumps(_snapshot(seat)),
        )
        db.add(record)
        db.flush()
        audit(
            record,
            ActivityAction.it_virtual_seat_created,
            None,
            {
                "employee": seat["user_name"],
                "primary_device": seat["primary"]["asset_number"],
                "shift": seat["shift_display"],
                "components": _snapshot(seat),
            },
        )
        changes += 1
    if changes:
        db.flush()
    return changes


def list_seats(
    db: Session,
    *,
    actor: User | None,
    on_date: date | None = None,
    search: str | None = None,
    setup_status: str | None = None,
    seat_type: str | None = None,
    shift_id: UUID | None = None,
    shared_only: bool = False,
) -> list[dict[str, Any]]:
    """Seats for the IT view. Identity rows are reconciled first so codes are stable."""
    if (on_date or date.today()) == date.today() and sync_seats(db, actor=actor, source="reconcile"):
        db.commit()
    seats = derive_seats(db, on_date=on_date)
    q = (search or "").strip().lower()
    out = []
    for seat in seats:
        if setup_status and seat["setup_status"] != setup_status:
            continue
        if seat_type and seat["seat_type"] != seat_type:
            continue
        if shift_id and seat["shift_id"] != str(shift_id):
            continue
        if shared_only and not seat["shared_with"]:
            continue
        if q:
            haystack = " ".join(
                str(v or "")
                for v in [
                    seat["user_name"],
                    seat["employee_code"],
                    seat["seat_code"],
                    (seat["primary"] or {}).get("asset_number"),
                    (seat["primary"] or {}).get("computer_name"),
                    *[c["asset_number"] for c in seat["components"]],
                ]
            ).lower()
            if q not in haystack:
                continue
        out.append(seat)
    return out


def seats_for_user(db: Session, user_id: UUID, *, on_date: date | None = None) -> list[dict[str, Any]]:
    return derive_seats(db, on_date=on_date, user_ids={user_id})


def seat_history(db: Session, seat_id: UUID) -> list[dict[str, Any]]:
    from app.models.models import Activity

    rows = db.scalars(
        select(Activity)
        .where(Activity.entity_type == EntityType.it_virtual_seat, Activity.entity_id == seat_id)
        .order_by(Activity.created_at.desc())
    ).all()
    out = []
    for row in rows:
        actor = db.get(User, row.user_id) if row.user_id else None
        try:
            new_value = json.loads(row.new_value) if row.new_value else None
        except ValueError:
            new_value = row.new_value
        try:
            old_value = json.loads(row.old_value) if row.old_value else None
        except ValueError:
            old_value = row.old_value
        out.append(
            {
                "id": str(row.id),
                "action": row.action.value if hasattr(row.action, "value") else str(row.action),
                "at": row.created_at.isoformat() if row.created_at else None,
                "actor_name": _full_name(actor),
                "old_value": old_value,
                "new_value": new_value,
            }
        )
    return out


def seat_summary(seats: list[dict[str, Any]]) -> dict[str, int]:
    real = [s for s in seats if s["primary"]]
    return {
        "total_seats": len(real),
        "complete": sum(1 for s in real if s["setup_status"] == SETUP_COMPLETE),
        "incomplete": sum(1 for s in real if s["setup_status"] == SETUP_INCOMPLETE),
        "no_primary_device": sum(1 for s in seats if s["setup_status"] == SETUP_NO_PRIMARY),
        "shared_devices": len({s["primary"]["asset_id"] for s in real if s["shared_with"]}),
        "conflicts": sum(1 for s in real if s["conflicts"]),
    }
