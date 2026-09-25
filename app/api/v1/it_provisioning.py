"""IT provisioning / hire-with-IT APIs and Employee 360 aggregate."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_HUMAN_RESOURCES,
    MODULE_IT_OPERATIONS,
    SPECIAL_VIEW_IT_OPERATIONS,
)
from app.core.exceptions import ProTrackValidationError
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name, is_admin, user_has_module, user_has_special
from app.crud import user as user_crud
from app.crud.user import build_user_read
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    EmployeeSoftwareRequirement,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Project, Ticket, User
from app.models.resource_shifts import ResourceShift
from app.schemas.identity import UserCreate
from app.schemas.it_provisioning import (
    Employee360Read,
    HireWithItRequest,
    OnboardingReadinessRead,
    ProvisioningDashboardRead,
    ProvisioningForExistingUserRequest,
    ProvisioningHardwareRead,
    ProvisioningHardwareUpdate,
    ProvisioningRequestRead,
    ProvisioningSoftwareRead,
    ProvisioningStatusUpdate,
    SoftwareRequirementStatusUpdate,
)
from app.services import it_provisioning_service as provisioning
from app.services import onboarding_checklist_service as onboard
from app.services import resource_shift_service as shifts

router = APIRouter(prefix="/it/provisioning", tags=["it-provisioning"])


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _require_hr_or_admin(db: Session, user: User) -> None:
    if is_admin(db, user) or onboard.can_manage_onboarding(db, user):
        return
    role = get_role_name(db, user)
    if user_has_module_action(user, role, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW):
        return
    raise HTTPException(status_code=403, detail="HR or Admin access required")


def _require_it_access(db: Session, user: User) -> None:
    role = get_role_name(db, user)
    if (
        is_admin(db, user)
        or user_has_module(user, role, MODULE_IT_OPERATIONS)
        or user_has_special(user, role, SPECIAL_VIEW_IT_OPERATIONS)
    ):
        return
    raise HTTPException(status_code=403, detail="IT access required")


def _hardware_read(hw) -> ProvisioningHardwareRead:
    return ProvisioningHardwareRead(
        id=hw.id,
        created_at=hw.created_at,
        updated_at=hw.updated_at,
        provisioning_request_id=hw.provisioning_request_id,
        computer_required=hw.computer_required,
        computer_type=hw.computer_type,
        computer_type_label=provisioning.computer_type_label(hw.computer_type),
        computer_is_required=hw.computer_is_required,
        monitor_quantity=hw.monitor_quantity,
        monitor_is_required=hw.monitor_is_required,
        mouse_3d_required=hw.mouse_3d_required,
        mouse_3d_is_required=hw.mouse_3d_is_required,
        mouse_3d_model_hint=hw.mouse_3d_model_hint,
        mouse_3d_asset_type_id=hw.mouse_3d_asset_type_id,
        wireless_mouse_required=hw.wireless_mouse_required,
        laptop_dock_required=hw.laptop_dock_required,
        laptop_bag_required=hw.laptop_bag_required,
        headset_required=hw.headset_required,
        wireless_keyboard_required=hw.wireless_keyboard_required,
    )


def _software_read(db: Session, row: EmployeeSoftwareRequirement) -> ProvisioningSoftwareRead:
    catalog = db.get(SoftwareCatalog, row.software_id)
    return ProvisioningSoftwareRead(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        user_id=row.user_id,
        software_id=row.software_id,
        software_name=catalog.name if catalog else None,
        requirement_level=row.requirement_level,
        license_required=bool(getattr(row, "license_required", True)),
        priority=getattr(row, "priority", None) or "medium",
        purpose=getattr(row, "purpose", None),
        version=row.version,
        status=getattr(row, "status", None) or "REQUESTED",
        requested_by_id=getattr(row, "requested_by_id", None),
        provisioning_request_id=getattr(row, "provisioning_request_id", None),
    )


def _request_read(db: Session, request) -> ProvisioningRequestRead:
    user = db.get(User, request.user_id)
    ticket = db.get(Ticket, request.ticket_id) if request.ticket_id else None
    it_user = db.get(User, request.assigned_it_user_id) if request.assigned_it_user_id else None
    shift_display = None
    if request.shift_id:
        shift = db.get(ResourceShift, request.shift_id)
        if shift:
            shift_display = shifts.format_shift_label(shift)
    today = date.today()
    is_overdue = bool(
        request.required_by
        and request.required_by < today
        and request.status not in {"COMPLETED", "REJECTED", "CANCELLED"}
    )
    sw = provisioning.software_requirements_for_request(db, request.id)
    return ProvisioningRequestRead(
        id=request.id,
        created_at=request.created_at,
        updated_at=request.updated_at,
        user_id=request.user_id,
        employee_name=_full_name(user),
        employee_code=getattr(user, "employee_code", None) if user else None,
        department=None,
        designation=user.designation if user else None,
        joining_date=user.joining_date if user else None,
        checklist_id=request.checklist_id,
        ticket_id=request.ticket_id,
        ticket_number=ticket.ticket_number if ticket else None,
        shift_id=request.shift_id,
        shift_display=shift_display,
        required_by=request.required_by,
        priority=request.priority,
        status=request.status,
        assigned_it_user_id=request.assigned_it_user_id,
        assigned_it_user_name=_full_name(it_user),
        processing_started_at=request.processing_started_at,
        completed_at=request.completed_at,
        notes=request.notes,
        is_overdue=bool(is_overdue),
        hardware=_hardware_read(request.hardware) if request.hardware else None,
        software=[_software_read(db, row) for row in sw],
    )


@router.get("/computer-types")
def list_computer_types(
    current_user: User = Depends(get_current_user),
):
    from app.models.it_operations import COMPUTER_TYPE_LABELS

    _ = current_user
    return [
        {"code": code, "label": label}
        for code, label in COMPUTER_TYPE_LABELS.items()
    ]


@router.get("/dashboard", response_model=ProvisioningDashboardRead)
def provisioning_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return ProvisioningDashboardRead(**provisioning.dashboard_metrics(db))


@router.get("/workstation-demand-by-shift")
def workstation_demand_by_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return provisioning.workstation_demand_by_shift(db)


@router.get("/requests", response_model=list[ProvisioningRequestRead])
def list_provisioning_requests(
    status_filter: str | None = Query(None, alias="status"),
    overdue_only: bool = Query(False),
    computer_type: str | None = Query(None),
    user_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    rows = provisioning.list_requests(
        db,
        status=status_filter,
        overdue_only=overdue_only,
        computer_type=computer_type,
        user_id=user_id,
    )
    return [_request_read(db, row) for row in rows]


@router.get("/requests/{request_id}", response_model=ProvisioningRequestRead)
def get_provisioning_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    row = provisioning.get_request(db, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    return _request_read(db, row)


@router.patch("/requests/{request_id}/status", response_model=ProvisioningRequestRead)
def update_provisioning_status(
    request_id: UUID,
    payload: ProvisioningStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    row = provisioning.get_request(db, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    try:
        updated = provisioning.update_request_status(
            db,
            row,
            status=payload.status,
            actor=current_user,
            assigned_it_user_id=payload.assigned_it_user_id,
            notes=payload.notes,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return _request_read(db, updated)


@router.patch("/requests/{request_id}/hardware", response_model=ProvisioningRequestRead)
def update_provisioning_hardware(
    request_id: UUID,
    payload: ProvisioningHardwareUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_or_admin(db, current_user)
    row = provisioning.get_request(db, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    try:
        provisioning.update_hardware_requirements(
            db,
            row,
            actor=current_user,
            hardware=payload.hardware.model_dump(exclude_unset=True),
            reason=payload.reason,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    refreshed = provisioning.get_request(db, request_id)
    return _request_read(db, refreshed)


@router.patch(
    "/software-requirements/{requirement_id}/status",
    response_model=ProvisioningSoftwareRead,
)
def update_software_requirement_status(
    requirement_id: UUID,
    payload: SoftwareRequirementStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    row = db.get(EmployeeSoftwareRequirement, requirement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Software requirement not found")
    try:
        updated = provisioning.update_software_requirement_status(
            db, row, status=payload.status, actor=current_user
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return _software_read(db, updated)


@router.post(
    "/for-user",
    response_model=ProvisioningRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_provisioning_for_existing_user(
    payload: ProvisioningForExistingUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_or_admin(db, current_user)
    user = db.get(User, payload.user_id)
    if user is None or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        request = provisioning.create_provisioning_for_user(
            db,
            user=user,
            created_by=current_user,
            shift_id=payload.shift_id,
            hardware=payload.hardware.model_dump(),
            software_lines=[line.model_dump() for line in payload.software],
            checklist_id=payload.checklist_id,
            required_by=payload.required_by,
            priority=payload.priority,
            notes=payload.notes,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return _request_read(db, request)


@router.post(
    "/hire",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def hire_with_it(
    payload: HireWithItRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create employee + IT provisioning request (+ optional onboarding checklist)."""
    _require_hr_or_admin(db, current_user)
    try:
        user_in = UserCreate.model_validate(payload.user)
        created = user_crud.create(db, obj_in=user_in)
        checklist_id = None
        if payload.create_checklist:
            template = onboard.ensure_default_template(db)
            checklist, _tickets = onboard.create_checklist_from_template(
                db,
                template=template,
                employee_name=f"{created.first_name} {created.last_name}".strip(),
                created_by=current_user,
                employee_user_id=created.id,
                joining_date=created.joining_date,
                designation=created.designation,
                raise_tickets=False,
            )
            checklist_id = checklist.id
        request = provisioning.create_provisioning_for_user(
            db,
            user=created,
            created_by=current_user,
            shift_id=payload.shift_id,
            hardware=payload.hardware.model_dump(),
            software_lines=[line.model_dump() for line in payload.software],
            checklist_id=checklist_id,
            required_by=payload.required_by,
            priority=payload.priority,
            notes=payload.notes,
            commit=True,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _handle_validation(exc) from exc
    except Exception:
        db.rollback()
        raise
    return {
        "user": build_user_read(db, created),
        "provisioning": _request_read(db, request),
        "checklist_id": str(checklist_id) if checklist_id else None,
    }


@router.get("/readiness/{user_id}", response_model=OnboardingReadinessRead)
def get_onboarding_readiness(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        try:
            _require_hr_or_admin(db, current_user)
        except HTTPException:
            _require_it_access(db, current_user)
    return OnboardingReadinessRead(**provisioning.onboarding_readiness(db, user_id))


# --- Employee 360 (mounted under /users via separate router too) ---

users_360_router = APIRouter(prefix="/users", tags=["employee-360"])


def build_employee_360(db: Session, user_id: UUID) -> Employee360Read:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    shift_info = None
    try:
        from app.models.resource_shifts import ResourceShiftAssignment

        assignment = db.scalar(
            select(ResourceShiftAssignment)
            .where(
                ResourceShiftAssignment.user_id == user_id,
                ResourceShiftAssignment.is_active.is_(True),
                ResourceShiftAssignment.effective_to.is_(None),
            )
            .order_by(ResourceShiftAssignment.effective_from.desc())
        )
        if assignment is not None:
            sh = db.get(ResourceShift, assignment.shift_id)
            if sh is not None:
                shift_info = {
                    "shift_id": str(sh.id),
                    "shift_code": sh.code,
                    "shift_name": sh.name,
                    "shift_display": shifts.format_shift_label(sh),
                    "assignment_type": assignment.assignment_type,
                    "effective_from": str(assignment.effective_from),
                }
    except Exception:
        shift_info = None

    assignments = list(
        db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.assigned_to_user_id == user_id,
                AssetAssignment.returned_date.is_(None),
            )
        ).all()
    )
    it_assets = []
    for row in assignments:
        asset = db.get(Asset, row.asset_id)
        if asset is None:
            continue
        at = asset.asset_type or db.get(AssetType, asset.asset_type_id)
        shift_display = None
        if row.shift_id:
            sh = db.get(ResourceShift, row.shift_id)
            if sh:
                shift_display = shifts.format_shift_label(sh)
        it_assets.append(
            {
                "assignment_id": str(row.id),
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "asset_type": at.name if at else None,
                "category": at.category if at else None,
                "make": asset.make,
                "model": asset.model,
                "assignment_type": getattr(row, "assignment_type", None),
                "assigned_date": str(row.assigned_date),
                "shift_display": shift_display,
                "status": "Active",
            }
        )

    software_licenses = []
    for asg in db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
        )
    ).all():
        pool = db.get(SoftwareLicensePool, asg.license_pool_id)
        catalog = db.get(SoftwareCatalog, pool.software_id) if pool else None
        software_licenses.append(
            {
                "assignment_id": str(asg.id),
                "software": catalog.name if catalog else None,
                "license_type": pool.license_type if pool else None,
                "license_id": pool.entitlement_code if pool else None,
                "assigned_date": str(asg.assigned_date) if asg.assigned_date else None,
                "expiry_date": str(pool.expiry_date) if pool and pool.expiry_date else None,
                "status": "Assigned",
            }
        )

    performance_reviews = []
    try:
        from app.models.models import PerformanceReviewSheet

        sheets = db.scalars(
            select(PerformanceReviewSheet)
            .where(PerformanceReviewSheet.employee_id == user_id)
            .order_by(PerformanceReviewSheet.created_at.desc())
        ).all()
        for sheet in sheets:
            reviewer = db.get(User, sheet.reviewer_id)
            performance_reviews.append(
                {
                    "id": str(sheet.id),
                    "review_period": sheet.period_label,
                    "review_date": str(sheet.review_date) if sheet.review_date else None,
                    "reviewer": _full_name(reviewer),
                    "status": sheet.status,
                    "overall_result": (
                        float(sheet.overall_score) if sheet.overall_score is not None else None
                    ),
                    "next_review_date": str(sheet.due_date) if sheet.due_date else None,
                }
            )
    except Exception:
        performance_reviews = []

    projects = []
    try:
        from sqlalchemy import or_

        proj_rows = db.scalars(
            select(Project)
            .where(
                Project.is_deleted.is_(False),
                or_(
                    Project.design_leader_id == user_id,
                    Project.designer_id == user_id,
                    Project.surfacer_id == user_id,
                ),
            )
            .limit(50)
        ).all()
        for p in proj_rows:
            role = None
            if p.design_leader_id == user_id:
                role = "Design Leader"
            elif p.designer_id == user_id:
                role = "Designer"
            elif p.surfacer_id == user_id:
                role = "Surfacer"
            projects.append(
                {
                    "id": str(p.id),
                    "project_number": getattr(p, "project_number", None)
                    or getattr(p, "code", None),
                    "name": getattr(p, "name", None),
                    "status": getattr(p, "status", None),
                    "role": role,
                }
            )
    except Exception:
        projects = []

    timesheets = {"current_month_hours": None, "billable_hours": None, "projects_worked": len(projects)}
    try:
        from app.models.models import TimesheetEntry
        from calendar import monthrange

        today = date.today()
        start = today.replace(day=1)
        end = today.replace(day=monthrange(today.year, today.month)[1])
        total = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                TimesheetEntry.user_id == user_id,
                TimesheetEntry.work_date >= start,
                TimesheetEntry.work_date <= end,
            )
        )
        timesheets["current_month_hours"] = float(total or 0)
    except Exception:
        pass

    readiness = provisioning.onboarding_readiness(db, user_id)
    manager = db.get(User, user.manager_id) if user.manager_id else None

    workstation_packages: list[dict] = []
    try:
        from app.services import workstation_package_service as ws_packages

        workstation_packages = ws_packages.packages_for_user(db, user_id)
    except Exception:
        workstation_packages = []

    from app.services import it_stock_service, virtual_seat_service

    virtual_seats = virtual_seat_service.seats_for_user(db, user_id)
    consumables = it_stock_service.employee_consumables(db, user_id)

    return Employee360Read(
        overview={
            "name": _full_name(user),
            "employee_id": getattr(user, "employee_code", None),
            "email": user.email,
            "department": None,
            "designation": user.designation,
            "manager": _full_name(manager),
            "joining_date": str(user.joining_date) if user.joining_date else None,
            "shift": (shift_info or {}).get("shift_display") if isinstance(shift_info, dict) else None,
            "status": "Active" if user.is_active else "Inactive",
            "onboarding_overall": readiness.get("overall"),
            "it_summary": {
                "computers": sum(1 for a in it_assets if (a.get("category") or "") == "computer"),
                "other_assets": sum(1 for a in it_assets if (a.get("category") or "") != "computer"),
                "software_licenses": len(software_licenses),
                "workstation_packages": len(workstation_packages),
                "virtual_seats": sum(1 for s in virtual_seats if s.get("primary")),
            },
            "work_summary": {
                "active_projects": len(projects),
                "timesheet_hours": timesheets.get("current_month_hours"),
            },
            "performance_summary": {
                "last_review": performance_reviews[0] if performance_reviews else None,
            },
        },
        employment={
            "email": user.email,
            "phone": user.phone,
            "employment_type": (
                user.employment_type.value
                if hasattr(user.employment_type, "value")
                else user.employment_type
            ),
            "joining_date": str(user.joining_date) if user.joining_date else None,
            "leaving_date": str(user.leaving_date) if user.leaving_date else None,
            "designation": user.designation,
            "skill_level": (
                user.skill_level.value
                if hasattr(user.skill_level, "value")
                else user.skill_level
            ),
        },
        shift=shift_info if isinstance(shift_info, dict) else None,
        it_assets=it_assets,
        workstation_packages=workstation_packages,
        virtual_seats=virtual_seats,
        consumables=consumables,
        software_licenses=software_licenses,
        performance_reviews=performance_reviews,
        projects=projects,
        timesheets=timesheets,
        onboarding=OnboardingReadinessRead(**readiness),
    )


@users_360_router.get("/{user_id}/360", response_model=Employee360Read)
def employee_360(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and not is_admin(db, current_user):
        role = get_role_name(db, current_user)
        allowed = (
            user_has_module(current_user, role, MODULE_IT_OPERATIONS)
            or user_has_module_action(
                current_user, role, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW
            )
            or user_has_special(current_user, role, SPECIAL_VIEW_IT_OPERATIONS)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return build_employee_360(db, user_id)
