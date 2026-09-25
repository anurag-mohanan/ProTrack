"""Computer availability by type and shift — batch view over the single shift rule.

Uses ``workstation_package_service.evaluate_asset_shift`` (the same rule used by
asset assignment validation, packages and inventory enrichment), so every screen
answers "which computer can I assign for this shift?" identically.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.it_operations import (
    SHIFT_AVAIL_AVAILABLE,
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    WorkstationPackageMember,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_inventory_rules as rules
from app.services import resource_shift_service as shifts
from app.services import workstation_package_service as engine
from app.services.virtual_seat_service import seat_type_for

_INACTIVE = frozenset({"retired", "disposed", "returned_to_customer", "lost"})


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def computer_availability(
    db: Session,
    *,
    on_date: date | None = None,
    seat_type: str | None = None,
    shift_id: UUID | None = None,
    only_available: bool = False,
    search: str | None = None,
) -> dict[str, Any]:
    when = on_date or date.today()
    shifts.ensure_company_standard_shifts(db)
    all_shifts = list(
        db.scalars(
            select(ResourceShift).where(ResourceShift.is_active.is_(True)).order_by(ResourceShift.start_time)
        ).all()
    )
    shift_map = {s.id: s for s in all_shifts}
    target_shifts = [s for s in all_shifts if shift_id is None or s.id == shift_id]

    computers = [
        (asset, asset_type)
        for asset, asset_type in db.execute(
            select(Asset, AssetType)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(Asset.is_deleted.is_(False), Asset.status.not_in(_INACTIVE))
            .order_by(Asset.asset_number)
        ).all()
        if rules.role_for_asset_type(asset_type) == rules.ROLE_COMPUTER
    ]
    asset_ids = [a.id for a, _ in computers]
    open_rows: dict[UUID, list[AssetAssignment]] = defaultdict(list)
    if asset_ids:
        for row in db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.assigned_date <= when,
                or_(AssetAssignment.returned_date.is_(None), AssetAssignment.returned_date > when),
            )
        ).all():
            open_rows[row.asset_id].append(row)
    user_ids = {r.assigned_to_user_id for rows in open_rows.values() for r in rows}
    names = {u.id: _name(u) for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    extra_shift_ids = {r.shift_id for rows in open_rows.values() for r in rows if r.shift_id} - set(shift_map)
    if extra_shift_ids:
        shift_map.update(
            {s.id: s for s in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(extra_shift_ids))).all()}
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
    computer_names = (
        {c.asset_id: c.computer_name for c in db.scalars(select(Computer).where(Computer.asset_id.in_(asset_ids))).all()}
        if asset_ids
        else {}
    )

    q = (search or "").strip().lower()
    rows_out = []
    summary: dict[str, dict[str, Any]] = {}
    for asset, asset_type in computers:
        code = seat_type_for(asset, asset_type)
        if seat_type and code != seat_type:
            continue
        occupants = open_rows.get(asset.id, [])
        if q:
            haystack = " ".join(
                str(v or "")
                for v in [asset.asset_number, computer_names.get(asset.id), asset.make, asset.model, asset.serial_number]
                + [names.get(o.assigned_to_user_id) for o in occupants]
            ).lower()
            if q not in haystack:
                continue
        slots = []
        for shift in target_shifts:
            blocked = engine.evaluate_asset_shift(
                asset, shift, occupants, shift_lookup=shift_map, name_lookup=names
            )
            if blocked is None and asset.id in packaged:
                blocked = engine._package_blocks_asset(db, asset.id, shift_id=shift.id, on_date=when)
            result = blocked or {"status": SHIFT_AVAIL_AVAILABLE, "reason": None, "assignee_name": None}
            slots.append(
                {
                    "shift_id": str(shift.id),
                    "shift_code": shift.code,
                    "shift_display": shifts.format_shift_label(shift),
                    "status": result["status"],
                    "reason": result.get("reason"),
                    "assignee_name": result.get("assignee_name"),
                }
            )
        if only_available and not any(s["status"] == SHIFT_AVAIL_AVAILABLE for s in slots):
            continue
        bucket = summary.setdefault(
            code,
            {
                "seat_type": code,
                "label": rules.SEAT_TYPE_LABELS.get(code, code),
                "total": 0,
                "by_shift": {s.code: 0 for s in target_shifts},
            },
        )
        bucket["total"] += 1
        for slot in slots:
            if slot["status"] == SHIFT_AVAIL_AVAILABLE:
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
                        "shift_display": shifts.format_shift_label(shift_map[o.shift_id]) if o.shift_id in shift_map else None,
                    }
                    for o in occupants
                ],
                "shifts": slots,
            }
        )
    return {
        "on_date": when,
        "shifts": [
            {"shift_id": str(s.id), "shift_code": s.code, "shift_display": shifts.format_shift_label(s)}
            for s in target_shifts
        ],
        "summary": sorted(summary.values(), key=lambda row: row["label"]),
        "computers": rows_out,
    }
