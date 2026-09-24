"""Workstation package APIs — inventory, find available, assign, build."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_special
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_IT_OPERATIONS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_VIEW_IT_OPERATIONS,
)
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import get_role_name, is_admin, user_has_module, user_has_special
from app.models.models import User
from app.schemas.workstation_packages import (
    BuildPackageAndAssignRequest,
    FindAvailableComputerRequest,
    PackageAssignRequest,
    PackageMemberReplace,
    PackageReturnRequest,
    WorkstationPackageCreate,
)
from app.services import workstation_package_service as packages

router = APIRouter(prefix="/it/workstation-packages", tags=["workstation-packages"])


def _handle(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


def _require_it(db: Session, user: User) -> None:
    role = get_role_name(db, user)
    if (
        is_admin(db, user)
        or user_has_module(user, role, MODULE_IT_OPERATIONS)
        or user_has_special(user, role, SPECIAL_VIEW_IT_OPERATIONS)
    ):
        return
    raise HTTPException(status_code=403, detail="IT access required")


@router.get("")
def list_workstation_packages(
    status_filter: str | None = Query(None, alias="status"),
    computer_type: str | None = Query(None),
    shift_id: UUID | None = Query(None),
    on_date: date | None = Query(None),
    availability: str | None = Query(None),
    min_monitors: int | None = Query(None, ge=0),
    mouse_3d: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it(db, current_user)
    return packages.list_packages(
        db,
        status=status_filter,
        computer_type=computer_type,
        shift_id=shift_id,
        on_date=on_date,
        availability=availability,
        min_monitors=min_monitors,
        mouse_3d=mouse_3d,
    )


@router.get("/capacity")
def workstation_capacity(
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it(db, current_user)
    return packages.capacity_by_computer_type(db, on_date=on_date)


@router.get("/for-user/{user_id}")
def packages_for_user(
    user_id: UUID,
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        _require_it(db, current_user)
    return packages.packages_for_user(db, user_id, on_date=on_date)


@router.get("/{package_id}")
def get_workstation_package(
    package_id: UUID,
    on_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it(db, current_user)
    package = packages.get_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    when = on_date or date.today()
    members = packages.active_members(db, package.id, on_date=when)
    avail = {"status": "MULTI", "reason": None, "member_issues": [], "assignees": []}
    return packages._package_summary(db, package, members, avail, on_date=when)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def create_workstation_package(
    payload: WorkstationPackageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        package = packages.create_package(
            db,
            actor=current_user,
            code=payload.code,
            name=payload.name,
            primary_computer_asset_id=payload.primary_computer_asset_id,
            computer_type=payload.computer_type,
            members=[m.model_dump() for m in payload.members],
            notes=payload.notes,
            effective_from=payload.effective_from,
        )
    except ProTrackValidationError as exc:
        raise _handle(exc) from exc
    when = payload.effective_from or date.today()
    members = packages.active_members(db, package.id, on_date=when)
    avail = {"status": "MULTI", "reason": None, "member_issues": [], "assignees": []}
    return packages._package_summary(db, package, members, avail, on_date=when)


@router.post(
    "/{package_id}/replace-member",
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def replace_package_member(
    package_id: UUID,
    payload: PackageMemberReplace,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    package = packages.get_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    try:
        package = packages.replace_member(
            db,
            package,
            actor=current_user,
            old_asset_id=payload.old_asset_id,
            new_asset_id=payload.new_asset_id,
            reason=payload.reason,
            on_date=payload.on_date,
        )
    except ProTrackValidationError as exc:
        raise _handle(exc) from exc
    when = payload.on_date or date.today()
    members = packages.active_members(db, package.id, on_date=when)
    avail = {"status": "MULTI", "reason": None, "member_issues": [], "assignees": []}
    return packages._package_summary(db, package, members, avail, on_date=when)


@router.post(
    "/find-available",
)
def find_available_computer(
    payload: FindAvailableComputerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find Available Computer — searches complete workstation packages."""
    _require_it(db, current_user)
    return packages.find_available_packages(
        db,
        on_date=payload.on_date,
        shift_id=payload.shift_id,
        computer_type=payload.computer_type,
        monitor_quantity=payload.monitor_quantity,
        mouse_3d_required=payload.mouse_3d_required,
    )


@router.post(
    "/{package_id}/assign",
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def assign_workstation_package(
    package_id: UUID,
    payload: PackageAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    package = packages.get_package(db, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    try:
        asg = packages.assign_package(
            db,
            package,
            actor=current_user,
            user_id=payload.user_id,
            shift_id=payload.shift_id,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            notes=payload.notes,
            force_override=payload.force_override,
            override_reason=payload.override_reason,
            provisioning_request_id=payload.provisioning_request_id,
        )
    except ProTrackValidationError as exc:
        raise _handle(exc) from exc
    return {
        "id": str(asg.id),
        "package_id": str(asg.package_id),
        "user_id": str(asg.user_id),
        "shift_id": str(asg.shift_id),
        "effective_from": str(asg.effective_from),
        "effective_to": str(asg.effective_to) if asg.effective_to else None,
        "status": asg.status,
    }


@router.post(
    "/assignments/{assignment_id}/return",
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def return_workstation_package(
    assignment_id: UUID,
    payload: PackageReturnRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.it_operations import WorkstationPackageAssignment

    asg = db.get(WorkstationPackageAssignment, assignment_id)
    if asg is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    body = payload or PackageReturnRequest()
    try:
        updated = packages.return_package_assignment(
            db,
            asg,
            actor=current_user,
            returned_date=body.returned_date,
            notes=body.notes,
        )
    except ProTrackValidationError as exc:
        raise _handle(exc) from exc
    return {
        "id": str(updated.id),
        "status": updated.status,
        "effective_to": str(updated.effective_to) if updated.effective_to else None,
    }


@router.post(
    "/build-and-assign",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def build_package_and_assign(
    payload: BuildPackageAndAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create package from available assets and assign in one flow (revalidated)."""
    when = payload.on_date or date.today()
    try:
        # Revalidate each asset before create
        from app.models.it_operations import Asset

        computer = db.get(Asset, payload.primary_computer_asset_id)
        if computer is None:
            raise ProTrackValidationError("Computer not found.")
        comp_avail = packages.asset_shift_availability(
            db, computer, shift_id=payload.shift_id, on_date=when
        )
        if comp_avail["status"] != "AVAILABLE":
            raise ProTrackValidationError(
                comp_avail.get("reason") or "Computer not available.",
                status_code=409,
            )
        for asset_id in payload.member_asset_ids:
            asset = db.get(Asset, asset_id)
            if asset is None:
                raise ProTrackValidationError(f"Asset not found: {asset_id}")
            a = packages.asset_shift_availability(
                db, asset, shift_id=payload.shift_id, on_date=when
            )
            if a["status"] != "AVAILABLE":
                raise ProTrackValidationError(
                    a.get("reason") or f"{asset.asset_number} not available.",
                    status_code=409,
                )

        package = packages.create_package(
            db,
            actor=current_user,
            code=payload.code,
            name=payload.name or payload.code,
            primary_computer_asset_id=payload.primary_computer_asset_id,
            computer_type=payload.computer_type,
            members=[{"asset_id": aid} for aid in payload.member_asset_ids],
            notes=payload.notes,
            effective_from=when,
            commit=False,
        )
        asg = packages.assign_package(
            db,
            package,
            actor=current_user,
            user_id=payload.user_id,
            shift_id=payload.shift_id,
            effective_from=when,
            notes=payload.notes,
            provisioning_request_id=payload.provisioning_request_id,
            commit=True,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _handle(exc) from exc
    return {
        "package_id": str(package.id),
        "package_code": package.code,
        "assignment_id": str(asg.id),
    }
