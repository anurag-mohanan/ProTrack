"""IT employee provisioning — hire requirements, readiness, demand aggregates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    COMPUTER_TYPE_ENG_WS,
    COMPUTER_TYPE_LABELS,
    COMPUTER_TYPES,
    DEFAULT_MONITOR_MAX,
    LAPTOP_COMPUTER_TYPES,
    ONBOARDING_SOFTWARE_MAX,
    PROVISIONING_STATUSES,
    PROVISIONING_TERMINAL,
    SOFTWARE_REQUIREMENT_STATUSES,
    Asset,
    AssetAssignment,
    AssetType,
    EmployeeSoftwareRequirement,
    ItProvisioningHardware,
    ItProvisioningRequest,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Ticket, User
from app.models.resource_shifts import ResourceShift, ResourceShiftAssignment
from app.services import it_software_service
from app.services import resource_shift_service as shifts
from app.services.activity_service import log_activity

MODULE = "it_operations"

CONFLICT_MSG = (
    "Workstation is already assigned during part of this employee's scheduled shift."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def license_rights_free(db: Session, pools: list[SoftwareLicensePool], shift_id: UUID | None) -> int:
    """Free rights for a joiner: within the shift window when known (engine-based)."""
    from app.services import resource_allocation_engine as allocation

    if shift_id is None:
        return sum(it_software_service.available_seats(db, pool) for pool in pools)
    shift = db.get(ResourceShift, shift_id)
    window = allocation.window_for_shift(shift) if shift else allocation.ALL_HOURS
    total = 0
    for pool in pools:
        free = allocation.license_free_in_window(db, pool, window)
        total += it_software_service.available_seats(db, pool) if free is None else free
    return total


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def default_monitor_quantity(computer_type: str | None) -> int:
    if computer_type == COMPUTER_TYPE_ENG_WS:
        return 2
    if computer_type in LAPTOP_COMPUTER_TYPES:
        return 0
    return 1


def computer_type_label(code: str | None) -> str | None:
    if not code:
        return None
    return COMPUTER_TYPE_LABELS.get(code, code)


def shift_windows_overlap(a: ResourceShift, b: ResourceShift) -> bool:
    """True when two shift wall-clock windows overlap (handles overnight)."""
    from app.services import resource_allocation_engine as allocation

    if a.id == b.id:
        return True
    return allocation.windows_overlap(allocation.window_for_shift(a), allocation.window_for_shift(b))


def asset_is_laptop(db: Session, asset: Asset) -> bool:
    at = asset.asset_type or db.get(AssetType, asset.asset_type_id)
    if at is None:
        return False
    blob = f"{at.code or ''} {at.name or ''}".upper()
    return "LAPTOP" in blob or "NOTEBOOK" in blob


def find_shift_time_conflicts(
    db: Session,
    *,
    asset_id: UUID,
    shift_id: UUID,
) -> list[AssetAssignment]:
    """Open assignments whose shifts overlap the requested shift window."""
    from app.services import it_asset_service

    new_shift = db.get(ResourceShift, shift_id)
    if new_shift is None:
        return []
    conflicts: list[AssetAssignment] = []
    for row in it_asset_service.list_open_assignments(db, asset_id):
        if row.shift_id is None or row.shift_id == shift_id:
            continue
        other = db.get(ResourceShift, row.shift_id)
        if other is not None and shift_windows_overlap(new_shift, other):
            conflicts.append(row)
    return conflicts


def derive_computer_utilization(
    db: Session,
    asset: Asset,
    *,
    open_assignments: list[AssetAssignment] | None = None,
) -> dict[str, Any]:
    """Derive utilization label for shared workstations."""
    from app.services import it_asset_service

    if asset.status in {"retired", "disposed", "returned_to_customer"}:
        return {
            "utilization": "RETIRED",
            "active_users": 0,
            "active_shifts": 0,
            "configured_shifts": 0,
        }
    if asset.status == "maintenance":
        return {
            "utilization": "UNDER_MAINTENANCE",
            "active_users": 0,
            "active_shifts": 0,
            "configured_shifts": 0,
        }

    opens = open_assignments
    if opens is None:
        opens = it_asset_service.list_open_assignments(db, asset.id)
    active_users = len({row.assigned_to_user_id for row in opens})
    active_shifts = len({row.shift_id for row in opens if row.shift_id})
    configured = db.scalar(
        select(func.count()).select_from(ResourceShift).where(ResourceShift.is_active.is_(True))
    ) or 0

    if not opens:
        util = "AVAILABLE"
    elif asset_is_laptop(db, asset) and active_users >= 1 and active_shifts <= 1:
        util = "FULLY_UTILIZED" if active_users >= 1 else "AVAILABLE"
    elif configured and active_shifts >= configured:
        util = "FULLY_UTILIZED"
    elif active_shifts >= 1 and configured and active_shifts < configured:
        util = "PARTIALLY_UTILIZED"
    else:
        util = "ASSIGNED"

    return {
        "utilization": util,
        "active_users": active_users,
        "active_shifts": active_shifts,
        "configured_shifts": int(configured),
    }


def create_provisioning_for_user(
    db: Session,
    *,
    user: User,
    created_by: User,
    shift_id: UUID | None = None,
    hardware: dict[str, Any] | None = None,
    software_lines: list[dict[str, Any]] | None = None,
    checklist_id: UUID | None = None,
    required_by: date | None = None,
    priority: str = "medium",
    notes: str | None = None,
    commit: bool = True,
) -> ItProvisioningRequest:
    """Create structured IT provisioning request + Help Desk ticket for a new hire."""
    hw = hardware or {}
    software_lines = software_lines or []
    if len(software_lines) > ONBOARDING_SOFTWARE_MAX:
        raise ProTrackValidationError(
            f"Onboarding allows at most {ONBOARDING_SOFTWARE_MAX} software requirements."
        )

    computer_type = hw.get("computer_type")
    if computer_type and computer_type not in COMPUTER_TYPES:
        raise ProTrackValidationError(f"Invalid computer_type: {computer_type}")

    computer_required = bool(hw.get("computer_required", True))
    if computer_required and not computer_type:
        raise ProTrackValidationError("computer_type is required when computer_required is Yes.")

    monitor_qty = hw.get("monitor_quantity")
    if monitor_qty is None:
        monitor_qty = default_monitor_quantity(computer_type) if computer_required else 0
    monitor_qty = int(monitor_qty)
    if monitor_qty < 0 or monitor_qty > DEFAULT_MONITOR_MAX:
        raise ProTrackValidationError(
            f"monitor_quantity must be between 0 and {DEFAULT_MONITOR_MAX}."
        )

    is_laptop = computer_type in LAPTOP_COMPUTER_TYPES if computer_type else False
    wireless_mouse = hw.get("wireless_mouse_required")
    if wireless_mouse is None:
        wireless_mouse = True if is_laptop else False

    if shift_id is not None:
        shift = db.get(ResourceShift, shift_id)
        if shift is None or not shift.is_active:
            raise ProTrackValidationError("Shift not found or inactive.")
        # Ensure employee has an active shift assignment
        existing = db.scalar(
            select(ResourceShiftAssignment).where(
                ResourceShiftAssignment.user_id == user.id,
                ResourceShiftAssignment.is_active.is_(True),
                ResourceShiftAssignment.effective_to.is_(None),
            )
        )
        if existing is None or existing.shift_id != shift_id:
            shifts.assign_shift(
                db,
                {
                    "user_id": user.id,
                    "shift_id": shift_id,
                    "assignment_type": "permanent",
                    "effective_from": user.joining_date or date.today(),
                    "end_date_existing": True,
                },
                commit=False,
            )

    req_by = required_by or user.joining_date
    request = ItProvisioningRequest(
        id=uuid4(),
        user_id=user.id,
        checklist_id=checklist_id,
        shift_id=shift_id,
        required_by=req_by,
        priority=(priority or "medium").lower(),
        status="OPEN",
        notes=(notes or "").strip() or None,
    )
    db.add(request)
    db.flush()

    hardware_row = ItProvisioningHardware(
        id=uuid4(),
        provisioning_request_id=request.id,
        computer_required=computer_required,
        computer_type=computer_type if computer_required else None,
        computer_is_required=bool(hw.get("computer_is_required", True)),
        monitor_quantity=monitor_qty,
        monitor_is_required=bool(hw.get("monitor_is_required", monitor_qty > 0)),
        mouse_3d_required=bool(hw.get("mouse_3d_required", False)),
        mouse_3d_is_required=bool(hw.get("mouse_3d_is_required", hw.get("mouse_3d_required", False))),
        mouse_3d_model_hint=(hw.get("mouse_3d_model_hint") or None),
        mouse_3d_asset_type_id=hw.get("mouse_3d_asset_type_id"),
        wireless_mouse_required=bool(wireless_mouse),
        laptop_dock_required=bool(hw.get("laptop_dock_required", False)),
        laptop_bag_required=bool(hw.get("laptop_bag_required", False)),
        headset_required=bool(hw.get("headset_required", False)),
        wireless_keyboard_required=bool(hw.get("wireless_keyboard_required", False)),
    )
    db.add(hardware_row)

    seen_software: set[UUID] = set()
    for line in software_lines:
        software_id = line.get("software_id")
        if software_id is None:
            raise ProTrackValidationError("Each software line requires software_id.")
        software_id = UUID(str(software_id))
        if software_id in seen_software:
            raise ProTrackValidationError("Duplicate software selected in onboarding requirements.")
        seen_software.add(software_id)
        catalog = db.get(SoftwareCatalog, software_id)
        if catalog is None or not getattr(catalog, "is_active", True):
            raise ProTrackValidationError("Software catalog item not found or inactive.")
        level = (line.get("requirement_level") or "required").lower()
        license_required = bool(line.get("license_required", True))
        status = "REQUESTED"
        if license_required:
            pools = db.scalars(
                select(SoftwareLicensePool).where(
                    SoftwareLicensePool.software_id == software_id,
                    SoftwareLicensePool.status == "active",
                )
            ).all()
            if license_rights_free(db, list(pools), shift_id) < 1:
                status = "LICENSE_NOT_AVAILABLE"

        row = EmployeeSoftwareRequirement(
            id=uuid4(),
            user_id=user.id,
            software_id=software_id,
            requirement_level=level,
            version=(line.get("version") or None),
            reason=(line.get("reason") or None),
            notes=(line.get("notes") or None),
            provisioning_request_id=request.id,
            license_required=license_required,
            priority=(line.get("priority") or priority or "medium").lower(),
            purpose=(line.get("purpose") or None),
            requested_by_id=created_by.id,
            status=status,
        )
        db.add(row)

    waiting_license = any(
        line.get("license_required", True)
        for line in software_lines
    ) and any(
        True
        for _ in db.scalars(
            select(EmployeeSoftwareRequirement.id).where(
                EmployeeSoftwareRequirement.provisioning_request_id == request.id,
                EmployeeSoftwareRequirement.status == "LICENSE_NOT_AVAILABLE",
            )
        ).all()
    )
    if waiting_license:
        request.status = "WAITING_FOR_LICENSE"

    request_items = []
    if checklist_id is not None:
        from app.models.models import OnboardingChecklistItem

        request_items = list(
            db.scalars(
                select(OnboardingChecklistItem).where(
                    OnboardingChecklistItem.checklist_id == checklist_id,
                    OnboardingChecklistItem.responsibility == "it",
                    OnboardingChecklistItem.requires_request.is_(True),
                )
            ).all()
        )
    ticket = _create_it_ticket(
        db,
        request=request,
        user=user,
        created_by=created_by,
        hardware=hardware_row,
        task_items=request_items,
    )
    request.ticket_id = ticket.id
    db.add(request)
    db.flush()
    if request_items:
        from app.services import onboarding_task_service as onboarding_tasks

        onboarding_tasks.link_items_to_ticket(
            db, items=request_items, ticket=ticket, actor=created_by
        )

    log_activity(
        db,
        user=created_by,
        entity_type=EntityType.it_provisioning_request,
        entity_id=request.id,
        action=ActivityAction.it_provisioning_created,
        new_value={
            "user_id": str(user.id),
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "computer_type": hardware_row.computer_type,
            "monitor_quantity": hardware_row.monitor_quantity,
            "software_count": len(software_lines),
            "required_by": str(req_by) if req_by else None,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )

    if commit:
        db.commit()
        db.refresh(request)
    return request


def _create_it_ticket(
    db: Session,
    *,
    request: ItProvisioningRequest,
    user: User,
    created_by: User,
    hardware: ItProvisioningHardware,
    task_items: list | None = None,
) -> Ticket:
    """The provisioning request's ticket — shared with the workstation onboarding task.

    If the workstation task already has an active ticket it is reused (the
    provisioning detail is added as a comment); otherwise the ticket is created
    under the task's primary idempotency key so the onboarding auto-raise never
    creates a second one.
    """
    from app.services import onboarding_task_service as onboarding_tasks
    from app.services import ticket_workflow_service as workflow

    name = _full_name(user) or user.email
    emp_code = getattr(user, "employee_code", None) or getattr(user, "employee_id", None)
    hw_lines = []
    if hardware.computer_required:
        hw_lines.append(
            f"- Computer: {computer_type_label(hardware.computer_type)} "
            f"({'required' if hardware.computer_is_required else 'optional'})"
        )
        hw_lines.append(f"- Monitors: {hardware.monitor_quantity}")
        if hardware.mouse_3d_required:
            hint = hardware.mouse_3d_model_hint or "Yes"
            hw_lines.append(f"- 3D Mouse: {hint}")
        if hardware.wireless_mouse_required:
            hw_lines.append("- Wireless Mouse: Yes")
    else:
        hw_lines.append("- Computer: Not required")

    sw_rows = list(
        db.scalars(
            select(EmployeeSoftwareRequirement).where(
                EmployeeSoftwareRequirement.provisioning_request_id == request.id
            )
        ).all()
    )
    sw_lines: list[str] = []
    for row in sw_rows:
        catalog = db.get(SoftwareCatalog, row.software_id)
        sw_lines.append(
            f"- {catalog.name if catalog else row.software_id} · "
            f"License Required: {'Yes' if row.license_required else 'No'} · "
            f"Status: {row.status}"
        )

    shift_label = "—"
    if request.shift_id:
        shift = db.get(ResourceShift, request.shift_id)
        if shift:
            shift_label = shifts.format_shift_label(shift)

    description = (
        f"New employee onboarding request created for {name}. "
        f"Required by {request.required_by or 'TBD'}.\n\n"
        f"Employee: {name}"
        f"{f' ({emp_code})' if emp_code else ''}\n"
        f"Joining: {user.joining_date or 'TBD'}\n"
        f"Shift: {shift_label}\n"
        f"Department: {getattr(user, 'department_name', None) or '—'}\n"
        f"Designation: {user.designation or '—'}\n\n"
        f"HARDWARE\n" + ("\n".join(hw_lines) or "- None") + "\n\n"
        f"SOFTWARE\n" + ("\n".join(sw_lines) or "- None") + "\n\n"
        f"Provisioning request id: {request.id}"
    )
    task = next(iter(task_items or []), None)
    if task is not None and onboarding_tasks.has_active_request(task):
        existing = task.help_ticket
        workflow.add_comment(
            db,
            existing,
            actor=created_by,
            body=f"IT provisioning requirements recorded.\n\n{description}",
            is_internal=False,
            is_agent=True,
        )
        if existing.source_record_id is None:
            existing.source_record_id = str(request.id)
        db.flush()
        return existing
    key = (
        onboarding_tasks.primary_ticket_key(task)
        if task is not None and task.help_ticket_id is None
        else f"it_provisioning:{request.id}"
    )
    ticket, _created = workflow.create_ticket(
        db,
        title=f"Onboarding · {name} · IT Provisioning",
        description=description,
        category="it",
        subcategory="onboarding.provisioning",
        priority=request.priority,
        requester=created_by,
        actor=created_by,
        source_module="it_provisioning",
        source_record_id=str(request.id),
        idempotency_key=key,
        affected_user_id=user.id,
        onboarding_item_id=task.id if task is not None else None,
        due_date=request.required_by,
        location=user.designation,
    )
    return ticket


def get_request(db: Session, request_id: UUID) -> ItProvisioningRequest | None:
    return db.scalar(
        select(ItProvisioningRequest)
        .where(ItProvisioningRequest.id == request_id)
        .options(selectinload(ItProvisioningRequest.hardware))
    )


def list_requests(
    db: Session,
    *,
    status: str | None = None,
    overdue_only: bool = False,
    computer_type: str | None = None,
    user_id: UUID | None = None,
) -> list[ItProvisioningRequest]:
    stmt = select(ItProvisioningRequest).options(selectinload(ItProvisioningRequest.hardware))
    if status:
        stmt = stmt.where(ItProvisioningRequest.status == status.upper())
    if user_id:
        stmt = stmt.where(ItProvisioningRequest.user_id == user_id)
    if overdue_only:
        today = date.today()
        stmt = stmt.where(
            ItProvisioningRequest.required_by.is_not(None),
            ItProvisioningRequest.required_by < today,
            ItProvisioningRequest.status.notin_(list(PROVISIONING_TERMINAL)),
        )
    rows = list(db.scalars(stmt.order_by(ItProvisioningRequest.created_at.desc())).all())
    if computer_type:
        rows = [
            r
            for r in rows
            if r.hardware and r.hardware.computer_type == computer_type
        ]
    return rows


def update_request_status(
    db: Session,
    request: ItProvisioningRequest,
    *,
    status: str,
    actor: User,
    assigned_it_user_id: UUID | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> ItProvisioningRequest:
    status = status.upper()
    if status not in PROVISIONING_STATUSES:
        raise ProTrackValidationError(f"Invalid status: {status}")
    old = request.status
    if old in PROVISIONING_TERMINAL and status != old:
        raise ProTrackValidationError(f"Cannot change status from {old}.")

    request.status = status
    if status == "IN_PROGRESS" and request.processing_started_at is None:
        request.processing_started_at = _utcnow()
    if status == "COMPLETED":
        request.completed_at = _utcnow()
    if assigned_it_user_id is not None:
        request.assigned_it_user_id = assigned_it_user_id
    if notes is not None:
        request.notes = notes.strip() or None
    db.add(request)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_provisioning_request,
        entity_id=request.id,
        action=ActivityAction.it_provisioning_status_changed,
        old_value={"status": old},
        new_value={"status": status},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if status != old:
        from app.services import onboarding_task_service as onboarding_tasks

        onboarding_tasks.sync_from_provisioning(db, request, actor=actor)
        if status in {"CANCELLED", "REJECTED"}:
            from app.services import it_stock_service

            it_stock_service.release_for_provisioning(
                db, request.id, actor=actor, reason=f"Provisioning request {status.lower()}"
            )
    if commit:
        db.commit()
        db.refresh(request)
    return request


def update_hardware_requirements(
    db: Session,
    request: ItProvisioningRequest,
    *,
    actor: User,
    hardware: dict[str, Any],
    reason: str | None = None,
    commit: bool = True,
) -> ItProvisioningHardware:
    if request.hardware is None:
        raise ProTrackValidationError("Hardware requirements missing.")
    if request.processing_started_at is not None or request.status not in {
        "OPEN",
        "WAITING_FOR_LICENSE",
        "WAITING_FOR_ASSET",
    }:
        if not reason:
            raise ProTrackValidationError(
                "IT processing has started. Provide a reason to change hardware requirements."
            )

    hw = request.hardware
    old = {
        "computer_type": hw.computer_type,
        "monitor_quantity": hw.monitor_quantity,
        "mouse_3d_required": hw.mouse_3d_required,
    }
    for key in (
        "computer_required",
        "computer_type",
        "computer_is_required",
        "monitor_quantity",
        "monitor_is_required",
        "mouse_3d_required",
        "mouse_3d_is_required",
        "mouse_3d_model_hint",
        "mouse_3d_asset_type_id",
        "wireless_mouse_required",
        "laptop_dock_required",
        "laptop_bag_required",
        "headset_required",
        "wireless_keyboard_required",
    ):
        if key in hardware:
            setattr(hw, key, hardware[key])
    if hw.computer_type and hw.computer_type not in COMPUTER_TYPES:
        raise ProTrackValidationError(f"Invalid computer_type: {hw.computer_type}")
    db.add(hw)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_provisioning_request,
        entity_id=request.id,
        action=ActivityAction.it_provisioning_requirement_changed,
        old_value=old,
        new_value={
            "computer_type": hw.computer_type,
            "monitor_quantity": hw.monitor_quantity,
            "mouse_3d_required": hw.mouse_3d_required,
            "reason": reason,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(hw)
    return hw


def software_requirements_for_request(
    db: Session, request_id: UUID
) -> list[EmployeeSoftwareRequirement]:
    return list(
        db.scalars(
            select(EmployeeSoftwareRequirement).where(
                EmployeeSoftwareRequirement.provisioning_request_id == request_id
            )
        ).all()
    )


def update_software_requirement_status(
    db: Session,
    row: EmployeeSoftwareRequirement,
    *,
    status: str,
    actor: User,
    commit: bool = True,
) -> EmployeeSoftwareRequirement:
    status = status.upper()
    if status not in SOFTWARE_REQUIREMENT_STATUSES:
        raise ProTrackValidationError(f"Invalid software requirement status: {status}")
    old = row.status
    row.status = status
    db.add(row)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_provisioning_request,
        entity_id=row.provisioning_request_id or row.id,
        action=ActivityAction.it_provisioning_requirement_changed,
        old_value={"software_requirement_id": str(row.id), "status": old},
        new_value={"status": status},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def onboarding_readiness(db: Session, user_id: UUID) -> dict[str, Any]:
    """Compute onboarding readiness from requirements vs assignments."""
    user = db.get(User, user_id)
    items: list[dict[str, Any]] = []

    items.append(
        {
            "key": "employee_record",
            "label": "Employee Record",
            "required": True,
            "done": user is not None and not getattr(user, "is_deleted", False),
        }
    )

    request = db.scalar(
        select(ItProvisioningRequest)
        .where(ItProvisioningRequest.user_id == user_id)
        .options(selectinload(ItProvisioningRequest.hardware))
        .order_by(ItProvisioningRequest.created_at.desc())
    )
    items.append(
        {
            "key": "it_request",
            "label": "IT Request",
            "required": True,
            "done": request is not None,
            "status": request.status if request else None,
            "request_id": str(request.id) if request else None,
        }
    )

    open_assigns = []
    if user is not None:
        open_assigns = list(
            db.scalars(
                select(AssetAssignment).where(
                    AssetAssignment.assigned_to_user_id == user_id,
                    AssetAssignment.returned_date.is_(None),
                )
            ).all()
        )

    def _asset_blob(asset: Asset | None) -> str:
        if asset is None:
            return ""
        at = asset.asset_type or db.get(AssetType, asset.asset_type_id)
        return (
            f"{(at.code if at else '')} {(at.name if at else '')} "
            f"{(at.category if at else '')}"
        ).upper()

    def _has_asset_category(needle: str) -> bool:
        for row in open_assigns:
            blob = _asset_blob(db.get(Asset, row.asset_id))
            if needle in blob:
                return True
            if needle == "COMPUTER":
                asset = db.get(Asset, row.asset_id)
                at = asset.asset_type if asset else None
                if at is None and asset is not None:
                    at = db.get(AssetType, asset.asset_type_id)
                if at and at.category == "computer":
                    return True
        return False

    hw = request.hardware if request else None
    if hw and hw.computer_required and hw.computer_is_required:
        items.append(
            {
                "key": "workstation",
                "label": "Workstation Assigned",
                "required": True,
                "done": _has_asset_category("COMPUTER"),
            }
        )
    if hw and hw.monitor_quantity > 0 and hw.monitor_is_required:
        monitor_count = sum(
            1
            for row in open_assigns
            if "MONITOR" in _asset_blob(db.get(Asset, row.asset_id))
        )
        items.append(
            {
                "key": "monitors",
                "label": "Monitors Assigned",
                "required": True,
                "done": monitor_count >= hw.monitor_quantity,
                "needed": hw.monitor_quantity,
                "assigned": monitor_count,
            }
        )
    if hw and hw.mouse_3d_required and hw.mouse_3d_is_required:
        items.append(
            {
                "key": "mouse_3d",
                "label": "3D Mouse Assigned",
                "required": True,
                "done": _has_asset_category("3D") or _has_asset_category("SPACEMOUSE"),
            }
        )

    sw_reqs = list(
        db.scalars(
            select(EmployeeSoftwareRequirement).where(
                EmployeeSoftwareRequirement.user_id == user_id,
                EmployeeSoftwareRequirement.requirement_level == "required",
            )
        ).all()
    )
    active_sw: set[UUID] = set()
    for asg in db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
        )
    ).all():
        pool = db.get(SoftwareLicensePool, asg.license_pool_id)
        if pool:
            active_sw.add(pool.software_id)

    for req in sw_reqs:
        catalog = db.get(SoftwareCatalog, req.software_id)
        label = catalog.name if catalog else str(req.software_id)
        done = req.software_id in active_sw or req.status in {
            "LICENSE_ASSIGNED",
            "INSTALLED",
            "AVAILABLE",
        }
        if not req.license_required and req.status in {"APPROVED", "INSTALLED", "AVAILABLE"}:
            done = True
        items.append(
            {
                "key": f"software_{req.id}",
                "label": f"{label} License",
                "required": req.requirement_level == "required",
                "done": done,
                "status": req.status,
            }
        )

    required = [i for i in items if i.get("required")]
    done_required = [i for i in required if i.get("done")]
    if not required:
        overall = "NOT_STARTED"
    elif len(done_required) == 0:
        overall = "NOT_STARTED" if request is None else "PARTIALLY_READY"
    elif len(done_required) < len(required):
        overall = "PARTIALLY_READY"
    elif request and request.status == "COMPLETED":
        overall = "COMPLETE"
    else:
        overall = "READY"

    return {
        "user_id": str(user_id),
        "overall": overall,
        "items": items,
        "required_count": len(required),
        "done_required_count": len(done_required),
        "provisioning_request_id": str(request.id) if request else None,
    }


def dashboard_metrics(db: Session) -> dict[str, Any]:
    today = date.today()
    rows = list(
        db.scalars(
            select(ItProvisioningRequest).options(selectinload(ItProvisioningRequest.hardware))
        ).all()
    )
    open_rows = [r for r in rows if r.status not in PROVISIONING_TERMINAL]
    due_today = [r for r in open_rows if r.required_by == today]
    overdue = [r for r in open_rows if r.required_by and r.required_by < today]

    hardware_demand: dict[str, int] = {code: 0 for code in COMPUTER_TYPES}
    monitors = mice_3d = wireless = 0
    for r in open_rows:
        hw = r.hardware
        if not hw:
            continue
        if hw.computer_required and hw.computer_type:
            hardware_demand[hw.computer_type] = hardware_demand.get(hw.computer_type, 0) + 1
        monitors += hw.monitor_quantity or 0
        if hw.mouse_3d_required:
            mice_3d += 1
        if hw.wireless_mouse_required:
            wireless += 1

    sw_reqs = list(
        db.scalars(
            select(EmployeeSoftwareRequirement).where(
                EmployeeSoftwareRequirement.status.in_(
                    ["REQUESTED", "UNDER_REVIEW", "APPROVED", "LICENSE_NOT_AVAILABLE", "AVAILABLE"]
                )
            )
        ).all()
    )
    software_demand: list[dict[str, Any]] = []
    by_sw: dict[UUID, dict[str, Any]] = {}
    shift_by_request = {
        r.id: r.shift_id for r in db.scalars(
            select(ItProvisioningRequest).where(
                ItProvisioningRequest.id.in_({q.provisioning_request_id for q in sw_reqs if q.provisioning_request_id})
            )
        ).all()
    } if sw_reqs else {}
    for req in sw_reqs:
        entry = by_sw.setdefault(
            req.software_id,
            {"software_id": str(req.software_id), "requested": 0, "available": 0, "assigned": 0,
             "shortage": 0, "_by_shift": {}},
        )
        entry["requested"] += 1
        shift_key = shift_by_request.get(req.provisioning_request_id)
        entry["_by_shift"][shift_key] = entry["_by_shift"].get(shift_key, 0) + 1
        catalog = db.get(SoftwareCatalog, req.software_id)
        entry["software_name"] = catalog.name if catalog else None

    for software_id, entry in by_sw.items():
        pools = list(db.scalars(
            select(SoftwareLicensePool).where(
                SoftwareLicensePool.software_id == software_id,
                SoftwareLicensePool.status == "active",
            )
        ).all())
        assigned = sum(
            it_software_service.count_active_assignments(db, pool.id) for pool in pools
        )
        by_shift = entry.pop("_by_shift")
        free_by_shift = {key: license_rights_free(db, pools, key) for key in by_shift}
        entry["available"] = max(free_by_shift.values()) if free_by_shift else 0
        entry["assigned"] = assigned
        entry["shortage"] = sum(max(0, n - free_by_shift[key]) for key, n in by_shift.items())
        software_demand.append(entry)

    return {
        "new_employee_requests": len(rows),
        "open_it_requests": len(open_rows),
        "due_today": len(due_today),
        "overdue_requests": len(overdue),
        "waiting_for_hardware": sum(1 for r in open_rows if r.status == "WAITING_FOR_ASSET"),
        "waiting_for_software_license": sum(
            1 for r in open_rows if r.status == "WAITING_FOR_LICENSE"
        ),
        "ready_for_joining": sum(1 for r in open_rows if r.status == "READY"),
        "completed": sum(1 for r in rows if r.status == "COMPLETED"),
        "hardware_demand": {
            "by_computer_type": [
                {"code": code, "label": COMPUTER_TYPE_LABELS[code], "required": count}
                for code, count in hardware_demand.items()
            ],
            "monitors_required": monitors,
            "mice_3d_required": mice_3d,
            "wireless_mice_required": wireless,
        },
        "software_demand": software_demand,
    }


def workstation_demand_by_shift(db: Session) -> list[dict[str, Any]]:
    """Open computer requirements grouped by employee shift for Resource Planning."""
    shifts.ensure_company_standard_shifts(db)
    all_shifts = list(
        db.scalars(select(ResourceShift).where(ResourceShift.is_active.is_(True))).all()
    )
    open_rows = list_requests(db)
    open_rows = [r for r in open_rows if r.status not in PROVISIONING_TERMINAL]
    result = []
    for shift in all_shifts:
        count = sum(
            1
            for r in open_rows
            if r.shift_id == shift.id
            and r.hardware
            and r.hardware.computer_required
        )
        result.append(
            {
                "shift_id": str(shift.id),
                "shift_code": shift.code,
                "shift_name": shift.name,
                "shift_display": shifts.format_shift_label(shift),
                "workstations_required": count,
            }
        )
    return result


def end_assignments_for_offboard(
    db: Session,
    *,
    user_id: UUID,
    actor: User,
    end_date: date | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """End-date open asset and software assignments without deleting history."""
    from app.services import it_asset_service

    when = end_date or date.today()
    asset_count = 0
    opens = list(
        db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.assigned_to_user_id == user_id,
                AssetAssignment.returned_date.is_(None),
            )
        ).all()
    )
    for row in opens:
        asset = db.get(Asset, row.asset_id)
        if asset is None:
            continue
        it_asset_service.return_asset(
            db,
            asset,
            by_user=actor,
            returned_date=when,
            assignment_id=row.id,
            notes="Ended on employee offboarding",
            commit=False,
        )
        asset_count += 1

    sw_count = 0
    for asg in db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
        )
    ).all():
        asg.released_date = when
        asg.notes = ((asg.notes or "") + "\nEnded on employee offboarding").strip()
        db.add(asg)
        sw_count += 1

    if commit:
        db.commit()
    return {"assets_returned": asset_count, "licenses_released": sw_count}
