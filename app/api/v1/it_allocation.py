"""Shift-aware resource allocation APIs (check, schedules, setup, reservations, licenses, review)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_IT_OPERATIONS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_MANAGE_IT_SETTINGS,
    SPECIAL_MANAGE_IT_SOFTWARE,
    SPECIAL_VIEW_IT_OPERATIONS,
)
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import get_role_name, is_admin, user_has_module, user_has_special
from app.models.it_operations import Asset, SoftwareLicensePool
from app.models.models import User
from app.schemas.it_allocation import (
    AllocationCheckRequest,
    LegacyResolveRequest,
    LicenseCheckoutRequest,
    ReservationCreate,
    ReservationReleaseRequest,
    SetupAssignRequest,
    SharingPolicyUpdate,
)
from app.services import it_software_service
from app.services import resource_allocation_engine as allocation
from app.services import resource_assignment_service as assignments

router = APIRouter(prefix="/it/allocation", tags=["it-allocation"], dependencies=[Depends(get_current_user)])


def _fail(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or 422, detail=exc.detail)


def _has(db: Session, user: User, *specials: str) -> bool:
    if is_admin(db, user):
        return True
    role = get_role_name(db, user)
    return any(user_has_special(user, role, s) for s in specials)


def _require_view(db: Session, user: User) -> None:
    role = get_role_name(db, user)
    if is_admin(db, user) or user_has_module(user, role, MODULE_IT_OPERATIONS) or user_has_special(
        user, role, SPECIAL_VIEW_IT_OPERATIONS
    ):
        return
    raise HTTPException(status_code=403, detail="IT Operations access required.")


def _require(db: Session, user: User, *specials: str, message: str) -> None:
    if not _has(db, user, *specials):
        raise HTTPException(status_code=403, detail=message)


def _require_resource_permission(db: Session, user: User, resource_types: set[str]) -> None:
    if "asset" in resource_types:
        _require(db, user, SPECIAL_ASSIGN_IT_ASSETS, SPECIAL_MANAGE_IT_ASSETS,
                 message="Requires assign_it_assets permission.")
    if "license" in resource_types:
        _require(db, user, SPECIAL_MANAGE_IT_SOFTWARE, message="Requires manage_it_software permission.")


def _override(db: Session, user: User, requested: bool) -> bool:
    if requested:
        _require(db, user, SPECIAL_MANAGE_IT_ASSETS,
                 message="Overriding a schedule conflict requires the manage IT assets permission.")
    return requested


def _session_row(db: Session, row: Any) -> dict[str, Any]:
    names = allocation._names(db, [row.user_id, row.checked_out_by_user_id, row.checked_in_by_user_id])
    return {
        "id": str(row.id),
        "license_pool_id": str(row.license_pool_id),
        "assignment_id": str(row.assignment_id) if row.assignment_id else None,
        "user_id": str(row.user_id),
        "user_name": names.get(row.user_id),
        "asset_id": str(row.asset_id) if row.asset_id else None,
        "checked_out_at": row.checked_out_at.isoformat(),
        "checked_in_at": row.checked_in_at.isoformat() if row.checked_in_at else None,
        "source": row.source,
        "checked_out_by_name": names.get(row.checked_out_by_user_id),
        "checked_in_by_name": names.get(row.checked_in_by_user_id) if row.checked_in_by_user_id else None,
        "notes": row.notes,
        "is_active": row.checked_in_at is None,
    }


# --- Check & schedules ------------------------------------------------------------------


@router.post("/check")
def check_allocation(
    payload: AllocationCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live check used by assign dialogs; the save endpoints re-run the same evaluation."""
    _require_view(db, current_user)
    try:
        req = allocation.build_request(
            db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            shift_id=payload.shift_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            user_id=payload.user_id,
            asset_id=payload.asset_id,
            exclude_ids=[payload.exclude_assignment_id] if payload.exclude_assignment_id else [],
        )
        result = allocation.calculate_resource_availability(
            db, resource_type=payload.resource_type, resource_id=payload.resource_id, req=req
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    result["can_override"] = bool(result.get("overridable")) and _has(db, current_user, SPECIAL_MANAGE_IT_ASSETS)
    return result


@router.get("/schedule/asset/{asset_id}")
def asset_schedule(
    asset_id: UUID,
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    asset = db.get(Asset, asset_id)
    if asset is None or asset.is_deleted:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return allocation.asset_schedule(db, asset, on_date=on_date)


@router.get("/schedule/license/{pool_id}")
def license_schedule(
    pool_id: UUID,
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    pool = db.get(SoftwareLicensePool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="License pool not found.")
    return allocation.license_schedule(db, pool, on_date=on_date)


# --- Bulk setup ------------------------------------------------------------------------


@router.post("/setup")
def assign_setup(
    payload: SetupAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Computer + peripherals + licenses for one employee/window in one transaction."""
    types = {line.resource_type for line in payload.lines}
    if payload.dry_run:
        _require_view(db, current_user)
    else:
        _require_resource_permission(db, current_user, types)
    try:
        return assignments.assign_setup(
            db,
            actor=current_user,
            user_id=payload.user_id,
            lines=[line.model_dump() for line in payload.lines],
            start_date=payload.start_date,
            end_date=payload.end_date,
            shift_id=payload.shift_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            purpose=payload.purpose,
            assignment_type=payload.assignment_type,
            allow_partial=payload.allow_partial,
            dry_run=payload.dry_run,
            force_override=_override(db, current_user, payload.force_override and not payload.dry_run),
            override_reason=payload.override_reason,
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc


# --- Reservations ------------------------------------------------------------------------


@router.get("/reservations")
def list_reservations(
    status: str | None = Query("ACTIVE"),
    resource_type: str | None = Query(None),
    asset_id: UUID | None = Query(None),
    license_pool_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return assignments.list_reservations(
        db,
        status=None if (status or "").upper() == "ALL" else status,
        resource_type=resource_type,
        asset_id=asset_id,
        license_pool_id=license_pool_id,
        user_id=user_id,
    )


@router.post("/reservations", status_code=201)
def create_reservation(
    payload: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_resource_permission(db, current_user, {payload.resource_type})
    try:
        row = assignments.create_reservation(
            db,
            actor=current_user,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            user_id=payload.user_id,
            reserved_for=payload.reserved_for,
            provisioning_request_id=payload.provisioning_request_id,
            shift_id=payload.shift_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            start_date=payload.start_date,
            end_date=payload.end_date,
            reason=payload.reason,
            force_override=_override(db, current_user, payload.force_override),
            override_reason=payload.override_reason,
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    return assignments.reservation_row(db, row)


@router.post("/reservations/{reservation_id}/release")
def release_reservation(
    reservation_id: UUID,
    payload: ReservationReleaseRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.it_operations import ResourceReservation

    row = db.get(ResourceReservation, reservation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    _require_resource_permission(db, current_user, {row.resource_type})
    try:
        row = assignments.release_reservation(
            db, reservation_id, actor=current_user, reason=payload.reason if payload else None
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    return assignments.reservation_row(db, row)


# --- License usage (check-out / release) ----------------------------------------------------


@router.get("/licenses/{pool_id}/sessions")
def list_license_sessions(
    pool_id: UUID,
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return [_session_row(db, r) for r in it_software_service.list_usage_sessions(db, pool_id, active_only=active_only)]


@router.post("/licenses/{pool_id}/checkout", status_code=201)
def checkout_license(
    pool_id: UUID,
    payload: LicenseCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require(db, current_user, SPECIAL_MANAGE_IT_SOFTWARE, message="Requires manage_it_software permission.")
    pool = db.get(SoftwareLicensePool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="License pool not found.")
    try:
        row = it_software_service.checkout_license(
            db, pool, user_id=payload.user_id, actor=current_user, asset_id=payload.asset_id, notes=payload.notes
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    return _session_row(db, row)


@router.post("/license-sessions/{session_id}/checkin")
def checkin_license(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require(db, current_user, SPECIAL_MANAGE_IT_SOFTWARE, message="Requires manage_it_software permission.")
    try:
        row = it_software_service.checkin_license(db, session_id, actor=current_user)
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    return _session_row(db, row)


# --- Legacy reconciliation -------------------------------------------------------------------


@router.get("/legacy")
def legacy_review(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    return assignments.legacy_review(db)


@router.post("/legacy/{assignment_id}/resolve")
def resolve_legacy(
    assignment_id: UUID,
    payload: LegacyResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require(db, current_user, SPECIAL_MANAGE_IT_ASSETS, message="Requires manage_it_assets permission.")
    try:
        row = assignments.resolve_legacy_assignment(
            db,
            assignment_id,
            actor=current_user,
            mode=payload.mode,
            shift_id=payload.shift_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            force_override=payload.force_override,
            override_reason=payload.override_reason,
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
    return {"assignment_id": str(row.id), "shift_id": str(row.shift_id) if row.shift_id else None,
            "start_time": row.start_time, "end_time": row.end_time}


# --- Sharing policy -------------------------------------------------------------------------


@router.get("/sharing-policy")
def list_sharing_policy(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_view(db, current_user)
    return assignments.list_sharing_policies(db)


@router.put("/sharing-policy/{asset_type_id}")
def update_sharing_policy(
    asset_type_id: UUID,
    payload: SharingPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require(db, current_user, SPECIAL_MANAGE_IT_SETTINGS, message="Requires manage_it_settings permission.")
    try:
        return assignments.update_sharing_policy(
            db,
            asset_type_id,
            actor=current_user,
            is_shareable=payload.is_shareable,
            requires_shift=payload.requires_shift,
            fields_set=set(payload.model_fields_set),
        )
    except ProTrackValidationError as exc:
        raise _fail(exc) from exc
