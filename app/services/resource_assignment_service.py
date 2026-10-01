"""Workflows on top of the allocation engine: reservations, bulk setup, legacy review, sharing policy.

Every decision here is made by ``resource_allocation_engine``; this module only
orchestrates transactions, persistence and audit.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    ResourceReservation,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, it_software_service
from app.services import resource_allocation_engine as allocation
from app.services.activity_service import log_activity

RESOURCE_ASSET = "asset"
RESOURCE_LICENSE = "license"
RESOURCE_TYPES = frozenset({RESOURCE_ASSET, RESOURCE_LICENSE})


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _require_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("Employee not found.", status_code=404)
    return user


def _resource(db: Session, resource_type: str, resource_id: UUID) -> Asset | SoftwareLicensePool:
    if resource_type == RESOURCE_ASSET:
        asset = db.get(Asset, resource_id)
        if asset is None or asset.is_deleted:
            raise ProTrackValidationError("Asset not found.", status_code=404)
        return asset
    if resource_type == RESOURCE_LICENSE:
        pool = db.get(SoftwareLicensePool, resource_id)
        if pool is None:
            raise ProTrackValidationError("License pool not found.", status_code=404)
        return pool
    raise ProTrackValidationError("resource_type must be 'asset' or 'license'.")


def _label(resource: Asset | SoftwareLicensePool, db: Session) -> str:
    if isinstance(resource, Asset):
        return resource.asset_number
    soft = it_software_service.get_software(db, resource.software_id)
    code = resource.entitlement_code or str(resource.id)[:8]
    return f"{soft.name} ({code})" if soft else code


# --- Reservations ---------------------------------------------------------------------


def reservation_row(db: Session, row: ResourceReservation) -> dict[str, Any]:
    shift = db.get(ResourceShift, row.shift_id) if row.shift_id else None
    window = allocation.window_for_row(row, {shift.id: shift} if shift else {})
    resource = db.get(Asset, row.asset_id) if row.asset_id else (
        db.get(SoftwareLicensePool, row.license_pool_id) if row.license_pool_id else None
    )
    names = allocation._names(db, [row.user_id, row.created_by_user_id, row.released_by_user_id])
    return {
        "id": str(row.id),
        "resource_type": row.resource_type,
        "asset_id": str(row.asset_id) if row.asset_id else None,
        "license_pool_id": str(row.license_pool_id) if row.license_pool_id else None,
        "resource_label": _label(resource, db) if resource is not None else None,
        "user_id": str(row.user_id) if row.user_id else None,
        "user_name": names.get(row.user_id) if row.user_id else None,
        "reserved_for": row.reserved_for,
        "provisioning_request_id": str(row.provisioning_request_id) if row.provisioning_request_id else None,
        "shift_id": str(row.shift_id) if row.shift_id else None,
        "shift_name": shift.name if shift else None,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "window_label": window.label,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "status": row.status,
        "reason": row.reason,
        "created_by_name": names.get(row.created_by_user_id),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "released_by_name": names.get(row.released_by_user_id) if row.released_by_user_id else None,
        "released_at": row.released_at.isoformat() if row.released_at else None,
        "release_reason": row.release_reason,
    }


def list_reservations(
    db: Session,
    *,
    status: str | None = "ACTIVE",
    resource_type: str | None = None,
    asset_id: UUID | None = None,
    license_pool_id: UUID | None = None,
    user_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = select(ResourceReservation).order_by(ResourceReservation.start_date.desc())
    if status:
        stmt = stmt.where(ResourceReservation.status == status.upper())
    if resource_type:
        stmt = stmt.where(ResourceReservation.resource_type == resource_type)
    if asset_id:
        stmt = stmt.where(ResourceReservation.asset_id == asset_id)
    if license_pool_id:
        stmt = stmt.where(ResourceReservation.license_pool_id == license_pool_id)
    if user_id:
        stmt = stmt.where(ResourceReservation.user_id == user_id)
    return [reservation_row(db, r) for r in db.scalars(stmt).all()]


def create_reservation(
    db: Session,
    *,
    actor: User,
    resource_type: str,
    resource_id: UUID,
    user_id: UUID | None = None,
    reserved_for: str | None = None,
    provisioning_request_id: UUID | None = None,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    reason: str | None = None,
    force_override: bool = False,
    override_reason: str | None = None,
) -> ResourceReservation:
    """Hold a resource for a window; validated by the engine like an assignment."""
    if user_id is None and not _clean(reserved_for):
        raise ProTrackValidationError("Reserve for an employee or describe who the reservation is for.")
    if user_id is not None:
        _require_user(db, user_id)
    resource = _resource(db, resource_type, resource_id)
    allocation.lock_resource(db, resource)
    req = allocation.build_request(
        db,
        start_date=start_date,
        end_date=end_date,
        shift_id=shift_id,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
    )
    if resource_type == RESOURCE_ASSET:
        result = allocation.evaluate_asset(db, resource, req)
    else:
        result = allocation.evaluate_license(db, resource, req)
    if result["reason_code"] == allocation.REASON_ALREADY_HOLDS:
        raise ProTrackValidationError(result["reason"], status_code=409)
    allocation.raise_if_blocked(result, override=force_override, override_reason=override_reason)

    if not (start_time and end_time) and shift_id is None:
        start_time, end_time = "00:00", "24:00"
    row = ResourceReservation(
        id=uuid4(),
        resource_type=resource_type,
        asset_id=resource.id if resource_type == RESOURCE_ASSET else None,
        license_pool_id=resource.id if resource_type == RESOURCE_LICENSE else None,
        user_id=user_id,
        reserved_for=_clean(reserved_for),
        provisioning_request_id=provisioning_request_id,
        shift_id=shift_id,
        start_time=start_time or None,
        end_time=end_time or None,
        start_date=req.start_date,
        end_date=req.end_date,
        status="ACTIVE",
        reason=_clean(reason),
        created_by_user_id=actor.id,
    )
    db.add(row)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_reservation,
        entity_id=row.id,
        action=ActivityAction.it_reservation_created,
        new_value={
            "resource_type": resource_type,
            "resource_id": str(resource.id),
            "resource": _label(resource, db),
            "user_id": str(user_id) if user_id else None,
            "reserved_for": row.reserved_for,
            "window": req.window.label,
            "dates": allocation.fmt_range(req.start_date, req.end_date),
            "reason": row.reason,
            "override_reason": _clean(override_reason) if not result["available"] else None,
        },
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def release_reservation(
    db: Session, reservation_id: UUID, *, actor: User, reason: str | None = None
) -> ResourceReservation:
    row = db.get(ResourceReservation, reservation_id)
    if row is None:
        raise ProTrackValidationError("Reservation not found.", status_code=404)
    if row.status != "ACTIVE":
        raise ProTrackValidationError(f"Reservation is already {row.status.lower()}.")
    row.status = "RELEASED"
    row.released_by_user_id = actor.id
    row.released_at = _now()
    row.release_reason = _clean(reason)
    db.add(row)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_reservation,
        entity_id=row.id,
        action=ActivityAction.it_reservation_released,
        old_value={"status": "ACTIVE"},
        new_value={"status": "RELEASED", "reason": row.release_reason},
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


# --- Bulk setup (computer + monitor + 3D mouse + licenses) ---------------------------


def assign_setup(
    db: Session,
    *,
    actor: User,
    user_id: UUID,
    lines: list[dict[str, Any]],
    start_date: date | None = None,
    end_date: date | None = None,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    purpose: str | None = None,
    assignment_type: str | None = None,
    allow_partial: bool = False,
    dry_run: bool = False,
    force_override: bool = False,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """Assign several resources to one employee/window in a single transaction.

    Each line goes through the same service path (and engine check) as a single
    assignment. Unless ``allow_partial`` is set, any failing line rolls back all
    lines. ``dry_run`` evaluates every line and writes nothing.
    """
    employee = _require_user(db, user_id)
    if not lines:
        raise ProTrackValidationError("Select at least one resource.")
    seen: set[tuple[str, UUID]] = set()
    for line in lines:
        key = (line["resource_type"], line["resource_id"])
        if key in seen:
            raise ProTrackValidationError("The same resource is listed twice.")
        seen.add(key)
    window = allocation.resolve_window(db, shift_id=shift_id, start_time=start_time, end_time=end_time)
    when = start_date or date.today()

    results: list[dict[str, Any]] = []
    for line in lines:
        rtype, rid = line["resource_type"], line["resource_id"]
        entry: dict[str, Any] = {"resource_type": rtype, "resource_id": str(rid)}
        try:
            resource = _resource(db, rtype, rid)
            entry["resource_label"] = _label(resource, db)
            if dry_run:
                req = allocation.build_request(
                    db, start_date=when, end_date=end_date, shift_id=shift_id,
                    start_time=start_time, end_time=end_time, user_id=user_id,
                    asset_id=line.get("asset_id"),
                )
                verdict = allocation.calculate_resource_availability(
                    db, resource_type=rtype, resource_id=rid, req=req
                )
                ok = verdict["available"] or verdict["reason_code"] == allocation.REASON_ALREADY_HOLDS
                entry.update(result="AVAILABLE" if verdict["available"] else verdict["status"],
                             ok=ok, reason=verdict["reason"], reason_code=verdict["reason_code"],
                             overridable=verdict.get("overridable", False),
                             conflicts=verdict.get("conflicting_assignments", []))
            elif rtype == RESOURCE_ASSET:
                row = it_asset_service.assign_asset(
                    db, resource, user_id=user_id, by_user=actor, assigned_date=when,
                    planned_end_date=end_date, shift_id=shift_id, start_time=start_time,
                    end_time=end_time, purpose=purpose, assignment_type=assignment_type,
                    force_override=force_override, override_reason=override_reason, commit=False,
                )
                entry.update(result="ASSIGNED", ok=True, assignment_id=str(row.id),
                             reason=f"Assigned {window.label}.")
            else:
                row = it_software_service.assign_license(
                    db, license_pool_id=rid, user_id=user_id, asset_id=line.get("asset_id"),
                    assigned_date=when, planned_end_date=end_date, shift_id=shift_id,
                    start_time=start_time, end_time=end_time, purpose=purpose, actor=actor,
                    force_override=force_override, override_reason=override_reason, commit=False,
                )
                entry.update(result="ASSIGNED", ok=True, assignment_id=str(row.id),
                             reason=f"License allocated {window.label}.")
        except ProTrackValidationError as exc:
            entry.update(result="FAILED", ok=False, reason=str(exc.detail), status_code=exc.status_code)
        results.append(entry)

    failures = [r for r in results if not r["ok"]]
    successes = [r for r in results if r["ok"]]
    if dry_run:
        db.rollback()
        return {"committed": False, "dry_run": True, "window": window.label,
                "employee": allocation._names(db, [employee.id]).get(employee.id),
                "all_available": not failures, "lines": results}
    if failures and (not allow_partial or not successes):
        db.rollback()
        for r in successes:
            r.update(result="ROLLED_BACK", ok=False, assignment_id=None,
                     reason="Rolled back — another line in this setup failed.")
        return {"committed": False, "dry_run": False, "window": window.label,
                "rolled_back": True, "lines": results}

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.user,
        entity_id=employee.id,
        action=ActivityAction.it_setup_assigned,
        new_value={
            "window": window.label,
            "dates": allocation.fmt_range(when, end_date),
            "purpose": _clean(purpose),
            "partial": bool(failures),
            "lines": [{k: r.get(k) for k in ("resource_type", "resource_label", "result", "reason")}
                      for r in results],
        },
        outcome="partial" if failures else "success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    return {"committed": True, "dry_run": False, "window": window.label,
            "rolled_back": False, "partial": bool(failures), "lines": results}


# --- Legacy reconciliation -------------------------------------------------------------


def user_allocations(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    """Open asset and license assignments of one employee with their engine window."""
    asset_rows = db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.assigned_to_user_id == user_id,
            AssetAssignment.returned_date.is_(None),
        ).order_by(AssetAssignment.assigned_date)
    ).all()
    license_rows = db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
        ).order_by(SoftwareAssignment.assigned_date)
    ).all()
    shift_map = allocation._shift_map(db, [*asset_rows, *license_rows])
    out: list[dict[str, Any]] = []

    asset_ids = {r.asset_id for r in asset_rows}
    assets = {a.id: a for a in db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()} if asset_ids else {}
    type_ids = {a.asset_type_id for a in assets.values() if a.asset_type_id}
    types = {t.id: t for t in db.scalars(select(AssetType).where(AssetType.id.in_(type_ids))).all()} \
        if type_ids else {}
    sharers: dict[UUID, int] = {}
    if asset_ids:
        for other in db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.returned_date.is_(None),
                AssetAssignment.assigned_to_user_id != user_id,
            )
        ).all():
            sharers[other.asset_id] = sharers.get(other.asset_id, 0) + 1
    for r in asset_rows:
        asset = assets.get(r.asset_id)
        if asset is None or asset.is_deleted:
            continue
        window = allocation.window_for_row(r, shift_map)
        at = types.get(asset.asset_type_id)
        out.append({
            "resource_type": RESOURCE_ASSET,
            "assignment_id": str(r.id),
            "resource_id": str(asset.id),
            "resource_label": asset.asset_number,
            "category": at.name if at else None,
            "shareable": allocation.sharing_policy(at)["shareable"],
            "window_label": "LEGACY / NEEDS REVIEW" if window.legacy else window.label,
            "times": window.times,
            "shift_name": window.shift_name,
            "legacy": window.legacy,
            "allocation_kind": "all_hours" if window.all_day else "scheduled",
            "shared_with": sharers.get(asset.id, 0),
            "dates": allocation.fmt_range(*allocation._row_dates(r)),
        })

    pool_ids = {r.license_pool_id for r in license_rows}
    pools = {p.id: p for p in db.scalars(
        select(SoftwareLicensePool).where(SoftwareLicensePool.id.in_(pool_ids))
    ).all()} if pool_ids else {}
    software = {s.id: s for s in db.scalars(
        select(SoftwareCatalog).where(SoftwareCatalog.id.in_({p.software_id for p in pools.values()}))
    ).all()} if pools else {}
    for r in license_rows:
        pool = pools.get(r.license_pool_id)
        if pool is None:
            continue
        metric = allocation.license_metric(pool)
        scheduled = allocation.is_scheduled(r)
        window = allocation.window_for_row(r, shift_map) if scheduled else None
        sw = software.get(pool.software_id)
        if metric == allocation.METRIC_CONCURRENT:
            kind, label = ("scheduled", window.label) if window else ("authorization", "Authorized (unscheduled)")
        else:
            kind, label = "allocated", window.label if window else "Named right (any time)"
        out.append({
            "resource_type": RESOURCE_LICENSE,
            "assignment_id": str(r.id),
            "resource_id": str(pool.id),
            "resource_label": sw.name if sw else (pool.entitlement_code or "License"),
            "category": allocation.license_summary(db, pool)["metric_label"],
            "shareable": metric == allocation.METRIC_CONCURRENT,
            "window_label": label,
            "times": window.times if window else None,
            "shift_name": window.shift_name if window else None,
            "legacy": False,
            "allocation_kind": kind,
            "shared_with": 0,
            "dates": allocation.fmt_range(*allocation._row_dates(r)),
        })
    return out


def legacy_review(db: Session) -> dict[str, Any]:
    """Open assignments without shift/time (treated as all-hours) and unconfigured licenses."""
    rows = db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.returned_date.is_(None),
            AssetAssignment.shift_id.is_(None),
            AssetAssignment.start_time.is_(None),
            AssetAssignment.end_time.is_(None),
        ).order_by(AssetAssignment.assigned_date)
    ).all()
    assets = {a.id: a for a in db.scalars(select(Asset).where(Asset.id.in_({r.asset_id for r in rows}))).all()} \
        if rows else {}
    type_ids = {a.asset_type_id for a in assets.values() if a.asset_type_id}
    types = {t.id: t for t in db.scalars(select(AssetType).where(AssetType.id.in_(type_ids))).all()} \
        if type_ids else {}
    names = allocation._names(db, [r.assigned_to_user_id for r in rows])
    assignments = []
    for r in rows:
        asset = assets.get(r.asset_id)
        if asset is None or asset.is_deleted:
            continue
        policy = allocation.sharing_policy(types.get(asset.asset_type_id))
        assignments.append({
            "assignment_id": str(r.id),
            "asset_id": str(asset.id),
            "asset_number": asset.asset_number,
            "asset_name": getattr(asset, "name", None) or getattr(asset, "model", None),
            "asset_type": types[asset.asset_type_id].name if asset.asset_type_id in types else None,
            "role_label": policy["role_label"],
            "shareable": policy["shareable"],
            "requires_shift": policy["requires_shift"],
            "user_id": str(r.assigned_to_user_id),
            "user_name": names.get(r.assigned_to_user_id),
            "assigned_date": r.assigned_date.isoformat() if r.assigned_date else None,
            "assignment_type": r.assignment_type,
            "status": "LEGACY / NEEDS REVIEW",
            "reason": "No shift or time window recorded — treated as occupying all hours.",
        })
    pools = []
    for pool in db.scalars(select(SoftwareLicensePool)).all():
        if (getattr(pool, "status", None) or "active") != "active":
            continue
        summary = allocation.license_summary(db, pool)
        issue = None
        if summary["metric"] == allocation.METRIC_UNSPECIFIED:
            issue = "License metric not configured — every assignment consumes a right."
        elif summary["compliance_status"] in {"OVER_ALLOCATED", "EXPIRED"}:
            issue = summary["compliance_reason"]
        if issue:
            pools.append({
                "license_pool_id": str(pool.id),
                "label": _label(pool, db),
                "metric": summary["metric"],
                "metric_label": summary["metric_label"],
                "compliance_status": summary["compliance_status"],
                "rights_owned": summary["rights_owned"],
                "rights_allocated": summary["rights_allocated"],
                "issue": issue,
            })
    return {"assignments": assignments, "license_pools": pools,
            "counts": {"assignments": len(assignments), "license_pools": len(pools)}}


def resolve_legacy_assignment(
    db: Session,
    assignment_id: UUID,
    *,
    actor: User,
    mode: str,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    force_override: bool = False,
    override_reason: str | None = None,
) -> AssetAssignment:
    """Record the real window of a legacy assignment after the engine confirms it fits."""
    row = db.get(AssetAssignment, assignment_id)
    if row is None:
        raise ProTrackValidationError("Assignment not found.", status_code=404)
    if row.returned_date is not None:
        raise ProTrackValidationError("Assignment is already closed.")
    if mode == "shift":
        if shift_id is None:
            raise ProTrackValidationError("Select the shift.")
        start_time = end_time = None
    elif mode == "times":
        if not (start_time and end_time):
            raise ProTrackValidationError("Provide both start time and end time.")
        shift_id = None
    elif mode == "all_hours":
        shift_id, start_time, end_time = None, "00:00", "24:00"
    else:
        raise ProTrackValidationError("mode must be 'shift', 'times' or 'all_hours'.")

    asset = db.get(Asset, row.asset_id)
    allocation.lock_resource(db, asset)
    req = allocation.build_request(
        db,
        start_date=max(row.assigned_date or date.today(), date.today()),
        end_date=row.planned_end_date,
        shift_id=shift_id,
        start_time=start_time,
        end_time=end_time,
        exclude_ids=[row.id],
    )
    result = allocation.evaluate_asset(db, asset, req)
    allocation.raise_if_blocked(result, override=force_override, override_reason=override_reason)

    old = {"shift_id": None, "start_time": None, "end_time": None, "window": "Legacy / all hours"}
    row.shift_id = shift_id
    row.start_time = start_time
    row.end_time = end_time
    if not result["available"]:
        row.override_reason = _clean(override_reason)
    db.add(row)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_assignment_reviewed,
        old_value=old,
        new_value={
            "assignment_id": str(row.id),
            "shift_id": str(shift_id) if shift_id else None,
            "start_time": start_time,
            "end_time": end_time,
            "window": req.window.label,
            "override_reason": row.override_reason if not result["available"] else None,
        },
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


# --- Sharing policy ---------------------------------------------------------------------


def list_sharing_policies(db: Session) -> list[dict[str, Any]]:
    types = db.scalars(select(AssetType).order_by(AssetType.name)).all()
    return [
        {"asset_type_id": str(t.id), "code": t.code, "name": t.name, "is_active": t.is_active,
         **allocation.sharing_policy(t)}
        for t in types
    ]


def update_sharing_policy(
    db: Session,
    asset_type_id: UUID,
    *,
    actor: User,
    is_shareable: bool | None,
    requires_shift: bool | None,
    fields_set: set[str],
) -> dict[str, Any]:
    """Set (or reset to the role default with ``null``) the sharing flags of an asset type."""
    at = db.get(AssetType, asset_type_id)
    if at is None:
        raise ProTrackValidationError("Asset type not found.", status_code=404)
    before = allocation.sharing_policy(at)
    if "is_shareable" in fields_set:
        at.is_shareable = is_shareable
    if "requires_shift" in fields_set:
        at.requires_shift = requires_shift
    after = allocation.sharing_policy(at)
    if not after["shareable"] and before["shareable"]:
        shared = db.scalars(
            select(AssetAssignment.asset_id)
            .join(Asset, Asset.id == AssetAssignment.asset_id)
            .where(Asset.asset_type_id == at.id, AssetAssignment.returned_date.is_(None))
            .group_by(AssetAssignment.asset_id)
        ).all()
        crowded = [
            aid for aid in shared
            if len({r.assigned_to_user_id for r in db.scalars(
                select(AssetAssignment).where(
                    AssetAssignment.asset_id == aid, AssetAssignment.returned_date.is_(None)
                )
            ).all()}) > 1
        ]
        if crowded:
            db.rollback()
            raise ProTrackValidationError(
                f"{len(crowded)} {at.name} asset(s) are currently shared by several employees. "
                "Release the extra assignments before making this type exclusive.",
                status_code=409,
            )
    db.add(at)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset_type,
        entity_id=at.id,
        action=ActivityAction.it_sharing_policy_updated,
        old_value={"shareable": before["shareable"], "requires_shift": before["requires_shift"]},
        new_value={"shareable": after["shareable"], "requires_shift": after["requires_shift"],
                   "configured": after["configured"]},
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(at)
    return {"asset_type_id": str(at.id), "code": at.code, "name": at.name, "is_active": at.is_active, **after}
