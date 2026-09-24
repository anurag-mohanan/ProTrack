"""Physical workstation packages — availability, find, assign, build, return."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    ASSIGNMENT_TYPE_SHIFT_SHARED,
    COMPUTER_TYPE_LABELS,
    COMPUTER_TYPES,
    LAPTOP_COMPUTER_TYPES,
    MEMBER_ROLE_3D_MOUSE,
    MEMBER_ROLE_PRIMARY_COMPUTER,
    MEMBER_ROLE_PRIMARY_MONITOR,
    MEMBER_ROLE_SECONDARY_MONITOR,
    MEMBER_ROLES,
    PACKAGE_STATUS_ACTIVE,
    PACKAGE_STATUS_INCOMPLETE,
    PACKAGE_STATUS_MAINTENANCE,
    PACKAGE_STATUS_RETIRED,
    PACKAGE_STATUSES,
    SHIFT_AVAIL_ASSIGNED,
    SHIFT_AVAIL_AVAILABLE,
    SHIFT_AVAIL_CONFLICT,
    SHIFT_AVAIL_PARTIAL,
    SHIFT_AVAIL_UNAVAILABLE,
    Asset,
    AssetAssignment,
    AssetType,
    WorkstationPackage,
    WorkstationPackageAssignment,
    WorkstationPackageMember,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service
from app.services import it_provisioning_service as provisioning
from app.services import resource_shift_service as shifts
from app.services.activity_service import log_activity

MODULE = "it_operations"
UNAVAILABLE_MSG = "This workstation package is no longer available for the selected shift."


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _asset_blob(db: Session, asset: Asset | None) -> str:
    if asset is None:
        return ""
    at = asset.asset_type or db.get(AssetType, asset.asset_type_id)
    return f"{(at.code if at else '')} {(at.name if at else '')} {(at.category if at else '')}".upper()


def infer_member_role(db: Session, asset: Asset, *, is_primary_computer: bool = False) -> str:
    if is_primary_computer:
        return MEMBER_ROLE_PRIMARY_COMPUTER
    blob = _asset_blob(db, asset)
    if "MONITOR" in blob or "DISPLAY" in blob:
        return MEMBER_ROLE_SECONDARY_MONITOR
    if "3D" in blob or "SPACEMOUSE" in blob:
        return MEMBER_ROLE_3D_MOUSE
    if "LAPTOP" in blob or (asset.asset_type and asset.asset_type.category == "computer"):
        return MEMBER_ROLE_PRIMARY_COMPUTER
    return "OTHER"


def active_members(
    db: Session, package_id: UUID, *, on_date: date | None = None
) -> list[WorkstationPackageMember]:
    when = on_date or date.today()
    rows = db.scalars(
        select(WorkstationPackageMember).where(
            WorkstationPackageMember.package_id == package_id,
            WorkstationPackageMember.effective_from <= when,
            or_(
                WorkstationPackageMember.effective_to.is_(None),
                WorkstationPackageMember.effective_to >= when,
            ),
        )
    ).all()
    return list(rows)


def open_package_assignments(
    db: Session,
    package_id: UUID,
    *,
    on_date: date | None = None,
) -> list[WorkstationPackageAssignment]:
    when = on_date or date.today()
    return list(
        db.scalars(
            select(WorkstationPackageAssignment).where(
                WorkstationPackageAssignment.package_id == package_id,
                WorkstationPackageAssignment.status == "ACTIVE",
                WorkstationPackageAssignment.effective_from <= when,
                or_(
                    WorkstationPackageAssignment.effective_to.is_(None),
                    WorkstationPackageAssignment.effective_to >= when,
                ),
            )
        ).all()
    )


def open_asset_assignments_on_date(
    db: Session, asset_id: UUID, *, on_date: date
) -> list[AssetAssignment]:
    return list(
        db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.assigned_date <= on_date,
                or_(
                    AssetAssignment.returned_date.is_(None),
                    AssetAssignment.returned_date >= on_date,
                ),
            )
        ).all()
    )


def asset_shift_availability(
    db: Session,
    asset: Asset,
    *,
    shift_id: UUID,
    on_date: date,
) -> dict[str, Any]:
    """Compute availability of one asset for a shift on a date."""
    if asset.is_deleted or asset.status in {
        "retired",
        "disposed",
        "returned_to_customer",
        "maintenance",
    }:
        return {
            "status": SHIFT_AVAIL_UNAVAILABLE,
            "reason": f"Asset {asset.asset_number} status is {asset.status}",
            "assignee_name": None,
        }

    target = db.get(ResourceShift, shift_id)
    if target is None:
        raise ProTrackValidationError("Shift not found.")

    opens = open_asset_assignments_on_date(db, asset.id, on_date=on_date)
    if not opens:
        # Also blocked by package assignments covering this asset
        pkg_block = _package_blocks_asset(db, asset.id, shift_id=shift_id, on_date=on_date)
        if pkg_block:
            return pkg_block
        return {"status": SHIFT_AVAIL_AVAILABLE, "reason": None, "assignee_name": None}

    for row in opens:
        if row.shift_id == shift_id:
            user = db.get(User, row.assigned_to_user_id)
            return {
                "status": SHIFT_AVAIL_ASSIGNED,
                "reason": f"Assigned to {_full_name(user)} on this shift",
                "assignee_name": _full_name(user),
                "assignment_id": str(row.id),
            }
        if row.shift_id is None:
            user = db.get(User, row.assigned_to_user_id)
            return {
                "status": SHIFT_AVAIL_UNAVAILABLE,
                "reason": f"Legacy assignment to {_full_name(user)} without shift",
                "assignee_name": _full_name(user),
            }
        other = db.get(ResourceShift, row.shift_id)
        if other and provisioning.shift_windows_overlap(target, other):
            user = db.get(User, row.assigned_to_user_id)
            return {
                "status": SHIFT_AVAIL_CONFLICT,
                "reason": (
                    f"Overlaps {other.name} assignment to {_full_name(user)} "
                    f"({other.start_time}–{other.end_time})"
                ),
                "assignee_name": _full_name(user),
            }

    pkg_block = _package_blocks_asset(db, asset.id, shift_id=shift_id, on_date=on_date)
    if pkg_block:
        return pkg_block
    return {"status": SHIFT_AVAIL_AVAILABLE, "reason": None, "assignee_name": None}


def _package_blocks_asset(
    db: Session, asset_id: UUID, *, shift_id: UUID, on_date: date
) -> dict[str, Any] | None:
    """If asset is in a package assigned on overlapping shift, report that."""
    members = db.scalars(
        select(WorkstationPackageMember).where(
            WorkstationPackageMember.asset_id == asset_id,
            WorkstationPackageMember.effective_from <= on_date,
            or_(
                WorkstationPackageMember.effective_to.is_(None),
                WorkstationPackageMember.effective_to >= on_date,
            ),
            WorkstationPackageMember.follows_workstation.is_(True),
        )
    ).all()
    target = db.get(ResourceShift, shift_id)
    if target is None:
        return None
    for mem in members:
        for asg in open_package_assignments(db, mem.package_id, on_date=on_date):
            if asg.shift_id == shift_id:
                user = db.get(User, asg.user_id)
                return {
                    "status": SHIFT_AVAIL_ASSIGNED,
                    "reason": f"Package assigned to {_full_name(user)} on this shift",
                    "assignee_name": _full_name(user),
                }
            other = db.get(ResourceShift, asg.shift_id)
            if other and provisioning.shift_windows_overlap(target, other):
                user = db.get(User, asg.user_id)
                return {
                    "status": SHIFT_AVAIL_CONFLICT,
                    "reason": (
                        f"Package assigned to {_full_name(user)} on overlapping "
                        f"{other.name} ({other.start_time}–{other.end_time})"
                    ),
                    "assignee_name": _full_name(user),
                }
    return None


def package_shift_availability(
    db: Session,
    package: WorkstationPackage,
    *,
    shift_id: UUID,
    on_date: date,
) -> dict[str, Any]:
    if package.status in {PACKAGE_STATUS_RETIRED, PACKAGE_STATUS_MAINTENANCE}:
        return {
            "status": SHIFT_AVAIL_UNAVAILABLE,
            "reason": f"Package status is {package.status}",
            "member_issues": [],
            "assignees": [],
        }

    members = active_members(db, package.id, on_date=on_date)
    issues: list[dict[str, Any]] = []
    required_ok = True
    optional_missing = False

    # Package-level assignments first
    opens = open_package_assignments(db, package.id, on_date=on_date)
    target = db.get(ResourceShift, shift_id)
    assignees = []
    for asg in opens:
        user = db.get(User, asg.user_id)
        sh = db.get(ResourceShift, asg.shift_id)
        assignees.append(
            {
                "user_id": str(asg.user_id),
                "user_name": _full_name(user),
                "shift_id": str(asg.shift_id),
                "shift_display": shifts.format_shift_label(sh) if sh else None,
            }
        )
        if asg.shift_id == shift_id:
            return {
                "status": SHIFT_AVAIL_ASSIGNED,
                "reason": f"Assigned to {_full_name(user)}",
                "member_issues": [],
                "assignees": assignees,
            }
        if target and sh and provisioning.shift_windows_overlap(target, sh):
            return {
                "status": SHIFT_AVAIL_CONFLICT,
                "reason": (
                    f"Overlaps {_full_name(user)} on {sh.name} "
                    f"({sh.start_time}–{sh.end_time})"
                ),
                "member_issues": [],
                "assignees": assignees,
            }

    for mem in members:
        asset = db.get(Asset, mem.asset_id)
        if asset is None:
            issues.append({"asset_id": str(mem.asset_id), "role": mem.role, "reason": "Asset missing"})
            if mem.is_required:
                required_ok = False
            continue
        avail = asset_shift_availability(db, asset, shift_id=shift_id, on_date=on_date)
        if avail["status"] != SHIFT_AVAIL_AVAILABLE:
            issues.append(
                {
                    "asset_id": str(asset.id),
                    "asset_number": asset.asset_number,
                    "role": mem.role,
                    "is_required": mem.is_required,
                    "status": avail["status"],
                    "reason": avail.get("reason"),
                }
            )
            if mem.is_required:
                required_ok = False
            else:
                optional_missing = True

    if not required_ok:
        status = SHIFT_AVAIL_PARTIAL if optional_missing or issues else SHIFT_AVAIL_UNAVAILABLE
        # If any required member is conflict/assigned → unavailable/conflict
        if any(i.get("status") == SHIFT_AVAIL_CONFLICT for i in issues if i.get("is_required")):
            status = SHIFT_AVAIL_CONFLICT
        elif any(i.get("status") == SHIFT_AVAIL_ASSIGNED for i in issues if i.get("is_required")):
            status = SHIFT_AVAIL_ASSIGNED
        elif any(i.get("is_required") for i in issues):
            status = SHIFT_AVAIL_PARTIAL if any(not i.get("is_required") for i in issues) else SHIFT_AVAIL_UNAVAILABLE
        return {
            "status": status if status != SHIFT_AVAIL_PARTIAL or any(i.get("is_required") for i in issues) else SHIFT_AVAIL_UNAVAILABLE,
            "reason": issues[0]["reason"] if issues else "Required member unavailable",
            "member_issues": issues,
            "assignees": assignees,
        }

    if optional_missing:
        return {
            "status": SHIFT_AVAIL_PARTIAL,
            "reason": "Optional package member unavailable",
            "member_issues": issues,
            "assignees": assignees,
        }

    return {
        "status": SHIFT_AVAIL_AVAILABLE,
        "reason": None,
        "member_issues": [],
        "assignees": assignees,
    }


def all_shifts_availability(
    db: Session, package: WorkstationPackage, *, on_date: date | None = None
) -> list[dict[str, Any]]:
    when = on_date or date.today()
    shifts.ensure_company_standard_shifts(db)
    rows = []
    for shift in db.scalars(
        select(ResourceShift).where(ResourceShift.is_active.is_(True)).order_by(ResourceShift.start_time)
    ).all():
        avail = package_shift_availability(db, package, shift_id=shift.id, on_date=when)
        rows.append(
            {
                "shift_id": str(shift.id),
                "shift_code": shift.code,
                "shift_name": shift.name,
                "shift_display": shifts.format_shift_label(shift),
                **avail,
            }
        )
    return rows


def _monitor_count(members: list[WorkstationPackageMember]) -> int:
    return sum(
        1
        for m in members
        if m.role in {MEMBER_ROLE_PRIMARY_MONITOR, MEMBER_ROLE_SECONDARY_MONITOR}
    )


def _has_3d_mouse(members: list[WorkstationPackageMember]) -> bool:
    return any(m.role == MEMBER_ROLE_3D_MOUSE for m in members)


def create_package(
    db: Session,
    *,
    actor: User,
    code: str,
    name: str,
    primary_computer_asset_id: UUID,
    computer_type: str | None = None,
    members: list[dict[str, Any]] | None = None,
    notes: str | None = None,
    effective_from: date | None = None,
    commit: bool = True,
) -> WorkstationPackage:
    code = (code or "").strip().upper()
    if not code:
        raise ProTrackValidationError("Package code is required.")
    existing = db.scalar(select(WorkstationPackage).where(WorkstationPackage.code == code))
    if existing:
        raise ProTrackValidationError(f"Package code {code} already exists.")

    computer = db.get(Asset, primary_computer_asset_id)
    if computer is None or computer.is_deleted:
        raise ProTrackValidationError("Primary computer asset not found.")
    at = computer.asset_type or db.get(AssetType, computer.asset_type_id)
    if at is None or at.category != "computer":
        raise ProTrackValidationError("Primary asset must be a computer.")

    if computer_type and computer_type not in COMPUTER_TYPES:
        raise ProTrackValidationError(f"Invalid computer_type: {computer_type}")

    when = effective_from or date.today()
    package = WorkstationPackage(
        id=uuid4(),
        code=code,
        name=(name or code).strip(),
        primary_computer_asset_id=primary_computer_asset_id,
        computer_type=computer_type,
        status=PACKAGE_STATUS_ACTIVE,
        notes=(notes or "").strip() or None,
    )
    db.add(package)
    db.flush()

    # Primary computer member
    db.add(
        WorkstationPackageMember(
            id=uuid4(),
            package_id=package.id,
            asset_id=primary_computer_asset_id,
            role=MEMBER_ROLE_PRIMARY_COMPUTER,
            is_required=True,
            follows_workstation=True,
            effective_from=when,
        )
    )

    seen = {primary_computer_asset_id}
    monitor_index = 0
    for raw in members or []:
        asset_id = UUID(str(raw["asset_id"]))
        if asset_id in seen:
            continue
        seen.add(asset_id)
        asset = db.get(Asset, asset_id)
        if asset is None or asset.is_deleted:
            raise ProTrackValidationError(f"Member asset not found: {asset_id}")
        role = (raw.get("role") or infer_member_role(db, asset)).upper()
        if role not in MEMBER_ROLES:
            role = "OTHER"
        if role in {MEMBER_ROLE_PRIMARY_MONITOR, MEMBER_ROLE_SECONDARY_MONITOR}:
            monitor_index += 1
            if monitor_index == 1 and role == MEMBER_ROLE_SECONDARY_MONITOR:
                role = MEMBER_ROLE_PRIMARY_MONITOR
            elif monitor_index > 1:
                role = MEMBER_ROLE_SECONDARY_MONITOR
        db.add(
            WorkstationPackageMember(
                id=uuid4(),
                package_id=package.id,
                asset_id=asset_id,
                role=role,
                is_required=bool(raw.get("is_required", True)),
                follows_workstation=bool(raw.get("follows_workstation", True)),
                effective_from=when,
                notes=(raw.get("notes") or None),
            )
        )

    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_workstation_package,
        entity_id=package.id,
        action=ActivityAction.it_workstation_package_created,
        new_value={"code": package.code, "computer": computer.asset_number},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(package)
    return package


def replace_member(
    db: Session,
    package: WorkstationPackage,
    *,
    actor: User,
    old_asset_id: UUID,
    new_asset_id: UUID,
    reason: str,
    on_date: date | None = None,
    commit: bool = True,
) -> WorkstationPackage:
    when = on_date or date.today()
    current = [
        m
        for m in active_members(db, package.id, on_date=when)
        if m.asset_id == old_asset_id
    ]
    if not current:
        raise ProTrackValidationError("Current package member not found.")
    mem = current[0]
    mem.effective_to = when
    mem.removed_reason = (reason or "").strip() or "Replaced"
    db.add(mem)

    new_asset = db.get(Asset, new_asset_id)
    if new_asset is None or new_asset.is_deleted:
        raise ProTrackValidationError("Replacement asset not found.")

    # If replacing primary computer, update package pointer
    if mem.role == MEMBER_ROLE_PRIMARY_COMPUTER:
        package.primary_computer_asset_id = new_asset_id
        db.add(package)

    db.add(
        WorkstationPackageMember(
            id=uuid4(),
            package_id=package.id,
            asset_id=new_asset_id,
            role=mem.role,
            is_required=mem.is_required,
            follows_workstation=mem.follows_workstation,
            effective_from=when,
            notes=f"Replaced {old_asset_id}",
        )
    )
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_workstation_package,
        entity_id=package.id,
        action=ActivityAction.it_workstation_package_member_changed,
        old_value={"asset_id": str(old_asset_id), "role": mem.role},
        new_value={"asset_id": str(new_asset_id), "reason": reason},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(package)
    return package


def assign_package(
    db: Session,
    package: WorkstationPackage,
    *,
    actor: User,
    user_id: UUID,
    shift_id: UUID,
    effective_from: date | None = None,
    effective_to: date | None = None,
    notes: str | None = None,
    force_override: bool = False,
    override_reason: str | None = None,
    provisioning_request_id: UUID | None = None,
    commit: bool = True,
) -> WorkstationPackageAssignment:
    """Assign package to employee+shift; also create AssetAssignments for following members."""
    when = effective_from or date.today()
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("Assignee user not found.")
    shift = db.get(ResourceShift, shift_id)
    if shift is None or not shift.is_active:
        raise ProTrackValidationError("Shift not found or inactive.")

    # Revalidate
    avail = package_shift_availability(db, package, shift_id=shift_id, on_date=when)
    if avail["status"] not in {SHIFT_AVAIL_AVAILABLE, SHIFT_AVAIL_PARTIAL}:
        if not force_override:
            raise ProTrackValidationError(UNAVAILABLE_MSG, status_code=409)
        if not (override_reason or "").strip():
            raise ProTrackValidationError("override_reason required to force assignment.")
    if avail["status"] == SHIFT_AVAIL_PARTIAL and any(
        i.get("is_required") for i in avail.get("member_issues") or []
    ):
        if not force_override:
            raise ProTrackValidationError(
                avail.get("reason") or "Required package member unavailable.",
                status_code=409,
            )

    # Laptop packages: reject second occupant unless override
    computer = db.get(Asset, package.primary_computer_asset_id)
    if computer and provisioning.asset_is_laptop(db, computer):
        if open_package_assignments(db, package.id, on_date=when) and not force_override:
            raise ProTrackValidationError(
                "Laptops normally have one active user. Use force_override to share."
            )

    assignment = WorkstationPackageAssignment(
        id=uuid4(),
        package_id=package.id,
        user_id=user_id,
        shift_id=shift_id,
        assigned_by_user_id=actor.id,
        effective_from=when,
        effective_to=effective_to,
        status="ACTIVE",
        notes=(notes or "").strip() or None,
        override_reason=(override_reason or "").strip() or None,
        provisioning_request_id=provisioning_request_id,
    )
    db.add(assignment)
    db.flush()

    # Mirror to AssetAssignment for following members (shared history).
    # Create rows directly — assign_asset would see this package assignment as a blocker.
    from app.models.it_operations import AssetAssignment as AA
    from uuid import uuid4 as _uuid4

    for mem in active_members(db, package.id, on_date=when):
        if not mem.follows_workstation:
            continue
        asset = db.get(Asset, mem.asset_id)
        if asset is None:
            continue
        existing = [
            a
            for a in open_asset_assignments_on_date(db, asset.id, on_date=when)
            if a.assigned_to_user_id == user_id
            and a.shift_id == shift_id
            and a.returned_date is None
        ]
        if existing:
            continue
        # Soft conflict check against other occupants
        conflicts = provisioning.find_shift_time_conflicts(
            db, asset_id=asset.id, shift_id=shift_id
        )
        same_shift = [
            a
            for a in it_asset_service.list_open_assignments(db, asset.id)
            if a.shift_id == shift_id
        ]
        if same_shift and not force_override:
            raise ProTrackValidationError(UNAVAILABLE_MSG, status_code=409)
        if conflicts and not force_override:
            raise ProTrackValidationError(UNAVAILABLE_MSG, status_code=409)

        row = AA(
            id=_uuid4(),
            asset_id=asset.id,
            assigned_to_user_id=user_id,
            assigned_by_user_id=actor.id,
            shift_id=shift_id,
            assignment_type=ASSIGNMENT_TYPE_SHIFT_SHARED,
            override_reason=(override_reason or "").strip() or None,
            assigned_date=when,
            notes=f"Package {package.code}",
        )
        if asset.status == "available":
            asset.status = "assigned"
            db.add(asset)
        db.add(row)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_workstation_package,
        entity_id=package.id,
        action=ActivityAction.it_workstation_package_assigned,
        new_value={
            "user_id": str(user_id),
            "shift_id": str(shift_id),
            "effective_from": str(when),
            "code": package.code,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(assignment)
    return assignment


def return_package_assignment(
    db: Session,
    assignment: WorkstationPackageAssignment,
    *,
    actor: User,
    returned_date: date | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> WorkstationPackageAssignment:
    when = returned_date or date.today()
    if assignment.status != "ACTIVE" or (
        assignment.effective_to is not None and assignment.effective_to < when
    ):
        raise ProTrackValidationError("Assignment is already ended.")
    assignment.effective_to = when
    assignment.status = "ENDED"
    if notes:
        assignment.notes = ((assignment.notes or "") + f"\n{notes}").strip()
    db.add(assignment)

    package = db.get(WorkstationPackage, assignment.package_id)
    if package:
        for mem in active_members(db, package.id, on_date=when):
            if not mem.follows_workstation:
                continue
            asset = db.get(Asset, mem.asset_id)
            if asset is None:
                continue
            opens = [
                a
                for a in it_asset_service.list_open_assignments(db, asset.id)
                if a.assigned_to_user_id == assignment.user_id
                and a.shift_id == assignment.shift_id
            ]
            for row in opens:
                it_asset_service.return_asset(
                    db,
                    asset,
                    by_user=actor,
                    returned_date=when,
                    assignment_id=row.id,
                    notes=notes or f"Package {package.code} returned",
                    commit=False,
                )

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_workstation_package,
        entity_id=assignment.package_id,
        action=ActivityAction.it_workstation_package_returned,
        new_value={"assignment_id": str(assignment.id), "returned_date": str(when)},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(assignment)
    return assignment


def find_available_packages(
    db: Session,
    *,
    on_date: date,
    shift_id: UUID,
    computer_type: str | None = None,
    monitor_quantity: int | None = None,
    mouse_3d_required: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Search packages; group into exact / partial / unavailable matches."""
    packages = list(
        db.scalars(
            select(WorkstationPackage)
            .where(WorkstationPackage.status != PACKAGE_STATUS_RETIRED)
            .options(selectinload(WorkstationPackage.members))
        ).all()
    )
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    for package in packages:
        if computer_type and package.computer_type and package.computer_type != computer_type:
            continue
        # If package has no computer_type set, still include when filtering by type
        # only if primary computer looks like a match — keep inclusive.
        members = active_members(db, package.id, on_date=on_date)
        monitors = _monitor_count(members)
        has_3d = _has_3d_mouse(members)
        avail = package_shift_availability(db, package, shift_id=shift_id, on_date=on_date)

        req_monitors = monitor_quantity or 0
        monitors_ok = monitors >= req_monitors
        mouse_ok = (not mouse_3d_required) or has_3d
        type_ok = (not computer_type) or (package.computer_type == computer_type) or (
            package.computer_type is None
        )

        summary = _package_summary(db, package, members, avail, on_date=on_date)

        if avail["status"] == SHIFT_AVAIL_AVAILABLE and monitors_ok and mouse_ok and type_ok:
            exact.append(summary)
        elif avail["status"] in {SHIFT_AVAIL_AVAILABLE, SHIFT_AVAIL_PARTIAL} and type_ok:
            reasons = []
            if not monitors_ok:
                reasons.append(f"Only {monitors} monitor(s); need {req_monitors}")
            if not mouse_ok:
                reasons.append("3D mouse missing")
            if avail["status"] == SHIFT_AVAIL_PARTIAL:
                reasons.append(avail.get("reason") or "Partial package")
            summary["match_reasons"] = reasons
            partial.append(summary)
        elif type_ok and (
            (computer_type is None or package.computer_type == computer_type)
            and (req_monitors == 0 or monitors >= req_monitors or True)
        ):
            # Matching computer type (or all) but unavailable for shift
            if computer_type is None or package.computer_type == computer_type or package.computer_type is None:
                if monitors >= req_monitors or req_monitors == 0:
                    summary["match_reasons"] = [avail.get("reason") or avail["status"]]
                    unavailable.append(summary)

    return {"exact_matches": exact, "partial_matches": partial, "unavailable_matches": unavailable}


def _package_summary(
    db: Session,
    package: WorkstationPackage,
    members: list[WorkstationPackageMember],
    avail: dict[str, Any],
    *,
    on_date: date,
) -> dict[str, Any]:
    computer = db.get(Asset, package.primary_computer_asset_id)
    member_rows = []
    for mem in members:
        asset = db.get(Asset, mem.asset_id)
        at = asset.asset_type if asset else None
        if asset and at is None:
            at = db.get(AssetType, asset.asset_type_id)
        member_rows.append(
            {
                "member_id": str(mem.id),
                "asset_id": str(mem.asset_id),
                "asset_number": asset.asset_number if asset else None,
                "role": mem.role,
                "is_required": mem.is_required,
                "follows_workstation": mem.follows_workstation,
                "asset_type": at.name if at else None,
                "status": asset.status if asset else None,
            }
        )
    return {
        "id": str(package.id),
        "code": package.code,
        "name": package.name,
        "status": package.status,
        "computer_type": package.computer_type,
        "computer_type_label": COMPUTER_TYPE_LABELS.get(package.computer_type or "", package.computer_type),
        "primary_computer_asset_id": str(package.primary_computer_asset_id),
        "primary_computer_number": computer.asset_number if computer else None,
        "monitor_count": _monitor_count(members),
        "has_3d_mouse": _has_3d_mouse(members),
        "availability_status": avail.get("status"),
        "availability_reason": avail.get("reason"),
        "member_issues": avail.get("member_issues") or [],
        "assignees": avail.get("assignees") or [],
        "members": member_rows,
        "shift_availability": all_shifts_availability(db, package, on_date=on_date),
    }


def list_packages(
    db: Session,
    *,
    status: str | None = None,
    computer_type: str | None = None,
    shift_id: UUID | None = None,
    on_date: date | None = None,
    availability: str | None = None,
    min_monitors: int | None = None,
    mouse_3d: bool | None = None,
) -> list[dict[str, Any]]:
    when = on_date or date.today()
    packages = list(db.scalars(select(WorkstationPackage)).all())
    results = []
    for package in packages:
        if status and package.status != status.upper():
            continue
        if computer_type and package.computer_type != computer_type:
            continue
        members = active_members(db, package.id, on_date=when)
        if min_monitors is not None and _monitor_count(members) < min_monitors:
            continue
        if mouse_3d is True and not _has_3d_mouse(members):
            continue
        if mouse_3d is False and _has_3d_mouse(members):
            continue
        if shift_id:
            avail = package_shift_availability(db, package, shift_id=shift_id, on_date=when)
            if availability and avail["status"] != availability.upper():
                continue
            summary = _package_summary(db, package, members, avail, on_date=when)
        else:
            # Aggregate all shifts
            shift_rows = all_shifts_availability(db, package, on_date=when)
            fake_avail = {"status": "MULTI", "reason": None, "member_issues": [], "assignees": []}
            summary = _package_summary(db, package, members, fake_avail, on_date=when)
            summary["shift_availability"] = shift_rows
            if availability:
                # Keep packages that have at least one shift matching
                if not any(s["status"] == availability.upper() for s in shift_rows):
                    continue
        results.append(summary)
    return results


def capacity_by_computer_type(db: Session, *, on_date: date | None = None) -> list[dict[str, Any]]:
    when = on_date or date.today()
    shifts.ensure_company_standard_shifts(db)
    all_shifts = list(
        db.scalars(select(ResourceShift).where(ResourceShift.is_active.is_(True))).all()
    )
    packages = list(
        db.scalars(
            select(WorkstationPackage).where(WorkstationPackage.status != PACKAGE_STATUS_RETIRED)
        ).all()
    )
    out = []
    for code, label in COMPUTER_TYPE_LABELS.items():
        subset = [p for p in packages if p.computer_type == code]
        shift_stats = []
        for sh in all_shifts:
            available = 0
            assigned = 0
            for p in subset:
                avail = package_shift_availability(db, p, shift_id=sh.id, on_date=when)
                if avail["status"] == SHIFT_AVAIL_AVAILABLE:
                    available += 1
                elif avail["status"] in {SHIFT_AVAIL_ASSIGNED, SHIFT_AVAIL_CONFLICT}:
                    assigned += 1
            shift_stats.append(
                {
                    "shift_id": str(sh.id),
                    "shift_code": sh.code,
                    "shift_name": sh.name,
                    "available": available,
                    "assigned": assigned,
                }
            )
        out.append(
            {
                "computer_type": code,
                "label": label,
                "total": len(subset),
                "maintenance": sum(1 for p in subset if p.status == PACKAGE_STATUS_MAINTENANCE),
                "incomplete": sum(1 for p in subset if p.status == PACKAGE_STATUS_INCOMPLETE),
                "shifts": shift_stats,
            }
        )
    return out


def get_package(db: Session, package_id: UUID) -> WorkstationPackage | None:
    return db.get(WorkstationPackage, package_id)


def packages_for_user(
    db: Session, user_id: UUID, *, on_date: date | None = None
) -> list[dict[str, Any]]:
    when = on_date or date.today()
    asgs = db.scalars(
        select(WorkstationPackageAssignment).where(
            WorkstationPackageAssignment.user_id == user_id,
            WorkstationPackageAssignment.status == "ACTIVE",
            WorkstationPackageAssignment.effective_from <= when,
            or_(
                WorkstationPackageAssignment.effective_to.is_(None),
                WorkstationPackageAssignment.effective_to >= when,
            ),
        )
    ).all()
    rows = []
    for asg in asgs:
        package = db.get(WorkstationPackage, asg.package_id)
        if package is None:
            continue
        members = active_members(db, package.id, on_date=when)
        avail = package_shift_availability(db, package, shift_id=asg.shift_id, on_date=when)
        summary = _package_summary(db, package, members, avail, on_date=when)
        sh = db.get(ResourceShift, asg.shift_id)
        others = [
            a
            for a in open_package_assignments(db, package.id, on_date=when)
            if a.user_id != user_id
        ]
        summary["assignment"] = {
            "id": str(asg.id),
            "shift_id": str(asg.shift_id),
            "shift_display": shifts.format_shift_label(sh) if sh else None,
            "effective_from": str(asg.effective_from),
            "effective_to": str(asg.effective_to) if asg.effective_to else None,
            "shared": len(others) > 0,
            "other_users": [
                {
                    "user_id": str(o.user_id),
                    "user_name": _full_name(db.get(User, o.user_id)),
                    "shift_id": str(o.shift_id),
                }
                for o in others
            ],
        }
        rows.append(summary)
    return rows
