"""Onboarding checklist API — PP-HRD-FO-14 New Hire Onboarding Checklist."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import MODULE_HUMAN_RESOURCES
from app.core.exceptions import ProTrackValidationError
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.models.models import OnboardingChecklist, OnboardingChecklistItem, User
from app.schemas.onboarding import (
    OnboardingAttentionSummary,
    OnboardingRepairResult,
    OnboardingTemplateConfigRead,
    OnboardingTemplateItemConfig,
    OnboardingTemplateItemRead,
    OnboardingChecklistCreate,
    OnboardingChecklistDetailRead,
    OnboardingChecklistItemRead,
    OnboardingChecklistRead,
    OnboardingChecklistUpdate,
    OnboardingItemHistoryEvent,
    OnboardingItemRequestCreate,
    OnboardingItemStatusUpdate,
    OnboardingItemUpdate,
    OnboardingTemplateRead,
    OnboardingTriggeredTicket,
)
from app.services import onboarding_checklist_service as onboard
from app.services import onboarding_task_service as tasks

router = APIRouter(prefix="/hr/onboarding", tags=["onboarding"])


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _require_hr_or_owner(db: Session, user: User) -> None:
    if onboard.can_manage_onboarding(db, user):
        return
    if user_has_module_action(
        user, get_role_name(db, user), MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW
    ):
        return
    # Managers / IT / Accounts can still list items they own via list endpoint filters.
    if onboard.responsibilities_for_user(db, user):
        return
    raise HTTPException(status_code=403, detail="Onboarding access required")


class _Viewer:
    """Per-request permission facts, computed once instead of per item."""

    def __init__(self, db: Session, user: User) -> None:
        self.user = user
        self.can_manage = onboard.can_manage_onboarding(db, user)
        self.owned = onboard.responsibilities_for_user(db, user)

    def can_edit(self, item: OnboardingChecklistItem) -> bool:
        return (
            self.can_manage
            or item.owner_user_id == self.user.id
            or item.responsibility in self.owned
        )

    def is_mine(self, item: OnboardingChecklistItem) -> bool:
        return item.owner_user_id == self.user.id or item.responsibility in self.owned

    def can_approve(self, item: OnboardingChecklistItem) -> bool:
        if self.can_manage:
            return True
        confirm_by = item.confirm_by or "owner"
        if confirm_by == "manager":
            return item.checklist is not None and item.checklist.reporting_manager_id == self.user.id
        if confirm_by == "it":
            return "it" in self.owned
        if confirm_by == "hr":
            return False
        return self.is_mine(item)


def _allowed_actions(item: OnboardingChecklistItem, viewer: _Viewer, can_edit: bool) -> list[str]:
    """Actions the UI may offer; the service re-validates every one of them."""
    if not can_edit:
        return []
    status_value = tasks.current_status(item)
    kind = tasks.execution_type(item)
    if tasks.is_resolved(status_value):
        return ["reopen"] if (item.reversible or viewer.can_manage) else []
    actions: list[str] = []
    if status_value in {tasks.NOT_STARTED, tasks.READY, tasks.WAITING, tasks.BLOCKED}:
        actions.append("start")
    if kind != tasks.AUTOMATED or viewer.can_manage:
        if kind != tasks.APPROVAL_REQUIRED or viewer.can_approve(item):
            actions.append("complete")
    if status_value != tasks.WAITING:
        actions.append("waiting")
    if status_value != tasks.BLOCKED:
        actions.append("block")
    if viewer.can_manage:
        actions.extend(["waive", "not_required"])
    if viewer.can_manage or not tasks.is_mandatory(item):
        actions.append("cancel")
    return actions


def _item_read(item: OnboardingChecklistItem, viewer: _Viewer) -> OnboardingChecklistItemRead:
    ticket = item.help_ticket
    status_value = tasks.LEGACY_STATUS_MAP.get(item.status, item.status)
    can_edit = viewer.can_edit(item)
    resolved = tasks.is_resolved(status_value)
    kind = tasks.execution_type(item)
    broken = tasks.link_is_broken(item)
    return OnboardingChecklistItemRead(
        id=item.id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        checklist_id=item.checklist_id,
        section=item.section,
        sort_order=item.sort_order,
        item_text=item.item_text,
        responsibility=item.responsibility,
        responsibility_label=onboard.RESPONSIBILITY_LABELS.get(
            item.responsibility, item.responsibility
        ),
        status=status_value,
        status_label=tasks.STATUS_LABELS.get(status_value, status_value),
        owner_user_id=item.owner_user_id,
        owner_name=_full_name(item.owner),
        help_ticket_id=item.help_ticket_id,
        help_ticket_number=ticket.ticket_number if ticket is not None else None,
        request_status=ticket.status if ticket is not None else None,
        request_category=tasks.request_category(item),
        requires_request=bool(item.requires_request),
        completed_by_id=item.completed_by_id,
        completed_by_name=_full_name(item.completed_by),
        completion_date=item.completion_date,
        completed_at=item.completed_at,
        completion_type=item.completion_type,
        notes=item.notes,
        due_date=tasks.effective_due_date(item),
        is_overdue=tasks.is_overdue(item),
        status_reason=item.status_reason,
        status_changed_at=item.status_changed_at,
        status_changed_by_name=_full_name(item.status_changed_by),
        validation_rule=item.validation_rule,
        attention=tasks.attention_codes(item),
        can_edit=can_edit,
        can_waive=viewer.can_manage,
        can_create_request=(
            can_edit
            and not resolved
            and kind == tasks.TICKET_REQUIRED
            and tasks.request_category(item) is not None
            and not tasks.has_active_request(item)
        ),
        is_mine=viewer.is_mine(item),
        execution_type=kind,
        execution_type_label=tasks.EXECUTION_TYPE_LABELS.get(kind, kind),
        mandatory=tasks.is_mandatory(item),
        blocks_completion=tasks.blocks_completion(item),
        evidence_required=bool(item.evidence_required) or kind == tasks.EXTERNAL_DEPENDENCY,
        reversible=item.reversible if item.reversible is not None else True,
        confirm_by=item.confirm_by,
        confirm_by_label=tasks.CONFIRM_BY_LABELS.get(item.confirm_by or "", None),
        can_approve=viewer.can_approve(item),
        evidence_note=item.evidence_note,
        request_status_label=(
            tasks.T.STATUS_LABELS.get(ticket.status, ticket.status) if ticket is not None else None
        ),
        request_assignee_name=_full_name(ticket.assignee) if ticket is not None else None,
        request_needs_owner=bool(
            ticket is not None and ticket.assignee_id is None and ticket.status in tasks.TICKET_OPEN
        ),
        link_broken=broken,
        allowed_actions=_allowed_actions(item, viewer, can_edit),
        can_repair_link=can_edit
        and not resolved
        and (
            broken
            or tasks.is_legacy_grouped(item)
            or (kind == tasks.TICKET_REQUIRED and item.help_ticket_id is None)
        ),
    )


def _to_read(
    db: Session, checklist: OnboardingChecklist, current_user: User, viewer: _Viewer | None = None
) -> OnboardingChecklistRead:
    viewer = viewer or _Viewer(db, current_user)
    stats = onboard.completion_stats(checklist)
    my_pending = sum(
        1
        for item in checklist.items
        if not tasks.is_resolved(item.status) and viewer.is_mine(item)
    )
    attention_items = sum(
        1
        for item in checklist.items
        if set(tasks.attention_codes(item)) - {"unassigned"}
    )
    overdue_items = sum(1 for item in checklist.items if tasks.is_overdue(item))
    return OnboardingChecklistRead(
        id=checklist.id,
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
        template_id=checklist.template_id,
        template_code=checklist.template.code if checklist.template else None,
        template_name=checklist.template.name if checklist.template else None,
        employee_user_id=checklist.employee_user_id,
        employee_name=checklist.employee_name,
        employee_code=checklist.employee_code,
        joining_date=checklist.joining_date,
        designation=checklist.designation,
        department_name=checklist.department_name,
        org_department_id=checklist.org_department_id,
        team_id=checklist.team_id,
        team_name=checklist.team_name,
        role_id=checklist.role_id,
        role_name=checklist.role_name,
        reporting_manager_id=checklist.reporting_manager_id,
        reporting_manager_name=checklist.reporting_manager_name
        or _full_name(checklist.reporting_manager),
        status=checklist.status,
        status_label=onboard.CHECKLIST_STATUS_LABELS.get(
            checklist.status, checklist.status
        ),
        notes=checklist.notes,
        created_by_id=checklist.created_by_id,
        created_by_name=_full_name(checklist.created_by),
        completed_at=checklist.completed_at,
        is_published=bool(getattr(checklist, "is_published", False)),
        published_at=getattr(checklist, "published_at", None),
        published_by_id=getattr(checklist, "published_by_id", None),
        total_items=stats["total"],
        completed_items=stats["completed"],
        resolved_items=stats["resolved"],
        pending_items=stats["unresolved"],
        blocked_items=stats["blocked"],
        attention_items=attention_items,
        overdue_items=overdue_items,
        completion_percent=stats["percent"],
        can_manage=viewer.can_manage,
        my_pending_items=my_pending,
    )


def _triggered_tickets(
    checklist: OnboardingChecklist,
    extra: list[dict] | None = None,
) -> list[OnboardingTriggeredTicket]:
    raw = extra if extra is not None else onboard.triggered_tickets_from_items(checklist)
    result: list[OnboardingTriggeredTicket] = []
    for row in raw:
        assignee_raw = row.get("assignee_id")
        result.append(
            OnboardingTriggeredTicket(
                responsibility=str(row["responsibility"]),
                responsibility_label=str(row["responsibility_label"]),
                ticket_id=UUID(str(row["ticket_id"])),
                ticket_number=str(row["ticket_number"]),
                category=str(row["category"]),
                assignee_id=UUID(str(assignee_raw)) if assignee_raw else None,
                item_count=int(row.get("item_count") or 0),
            )
        )
    return result


def _to_detail(
    db: Session,
    checklist: OnboardingChecklist,
    current_user: User,
    *,
    triggered: list[dict] | None = None,
    provisioned_temporary_password: str | None = None,
) -> OnboardingChecklistDetailRead:
    viewer = _Viewer(db, current_user)
    base = _to_read(db, checklist, current_user, viewer)
    items = [_item_read(item, viewer) for item in checklist.items]
    sections = []
    seen: set[str] = set()
    for item in checklist.items:
        if item.section not in seen:
            seen.add(item.section)
            sections.append(item.section)
    return OnboardingChecklistDetailRead(
        **base.model_dump(),
        items=items,
        sections=sections,
        triggered_tickets=_triggered_tickets(checklist, triggered),
        provisioned_temporary_password=provisioned_temporary_password,
    )


@router.get("/capabilities")
def onboarding_capabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    _require_hr_or_owner(db, current_user)
    return {"can_configure_templates": onboard.can_manage_onboarding(db, current_user)}


@router.get("/templates", response_model=list[OnboardingTemplateRead])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_or_owner(db, current_user)
    onboard.ensure_default_template(db)
    db.commit()
    from app.models.models import OnboardingChecklistTemplate

    templates = db.scalars(
        select(OnboardingChecklistTemplate)
        .where(OnboardingChecklistTemplate.is_active.is_(True))
        .order_by(OnboardingChecklistTemplate.code)
    ).all()
    return [
        OnboardingTemplateRead(
            id=row.id,
            code=row.code,
            name=row.name,
            version=row.version,
            is_active=row.is_active,
        )
        for row in templates
    ]


@router.get("", response_model=list[OnboardingChecklistRead])
def list_checklists(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_or_owner(db, current_user)
    onboard.ensure_default_template(db)
    viewer = _Viewer(db, current_user)
    result: list[OnboardingChecklistRead] = []
    for row in onboard.load_checklists(db, status=status_filter):
        if not _viewer_can_view(viewer, row):
            continue
        result.append(_to_read(db, row, current_user, viewer))
    return result


def _viewer_can_view(viewer: _Viewer, checklist: OnboardingChecklist) -> bool:
    user_id = viewer.user.id
    if viewer.can_manage or viewer.owned:
        return True
    if user_id in (
        checklist.employee_user_id,
        checklist.reporting_manager_id,
        checklist.created_by_id,
    ):
        return True
    return any(item.owner_user_id == user_id for item in checklist.items)


@router.get("/attention", response_model=OnboardingAttentionSummary)
def onboarding_attention(
    responsibility: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unresolved tasks that need action (missing/cancelled request, blocked, overdue)."""
    _require_hr_or_owner(db, current_user)
    viewer = _Viewer(db, current_user)
    items: list[OnboardingChecklistItem] = []
    for checklist in onboard.load_checklists(db, status="in_progress"):
        if not _viewer_can_view(viewer, checklist):
            continue
        for item in checklist.items:
            if responsibility and item.responsibility != responsibility:
                continue
            if not viewer.can_manage and not viewer.is_mine(item):
                continue
            items.append(item)
    return OnboardingAttentionSummary(**tasks.attention_summary(items))


@router.post("", response_model=OnboardingChecklistDetailRead, status_code=status.HTTP_201_CREATED)
def create_checklist(
    payload: OnboardingChecklistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can start onboarding.")
    template = onboard.ensure_default_template(db)
    if payload.template_id is not None:
        from app.models.models import OnboardingChecklistTemplate

        custom = db.get(OnboardingChecklistTemplate, payload.template_id)
        if custom is None:
            raise HTTPException(status_code=404, detail="Template not found.")
        template = custom

    from app.services import hr_onboarding_provisioning as provision

    employee_user_id = payload.employee_user_id
    role_id = payload.role_id
    provisioned_temporary_password: str | None = None

    if employee_user_id is not None:
        emp = db.get(User, employee_user_id)
        if emp is None or emp.is_deleted:
            raise HTTPException(status_code=404, detail="Employee user not found.")
    elif payload.employee_email:
        try:
            placement_preview = onboard.resolve_placement_fields(
                db,
                org_department_id=payload.org_department_id,
                team_id=payload.team_id,
                role_id=payload.role_id,
                reporting_manager_id=payload.reporting_manager_id,
                reporting_manager_name=payload.reporting_manager_name,
                department_name=payload.department_name,
                designation=payload.designation,
                fill_manager_from_team=payload.reporting_manager_id is None,
            )
            designation = payload.designation
            if not designation and isinstance(placement_preview.get("designation"), str):
                designation = placement_preview["designation"]  # type: ignore[assignment]
            new_user, temp_pw = provision.create_user_for_onboarding(
                db,
                employee_name=payload.employee_name,
                email=payload.employee_email,
                role_id=payload.role_id,
                team_id=payload.team_id,
                manager_id=placement_preview.get("reporting_manager_id"),  # type: ignore[arg-type]
                joining_date=payload.joining_date,
                designation=designation,
            )
            employee_user_id = new_user.id
            provisioned_temporary_password = temp_pw
            if role_id is None:
                role_id = new_user.role_id
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        checklist, triggered = onboard.create_checklist_from_template(
            db,
            template=template,
            employee_name=payload.employee_name,
            created_by=current_user,
            employee_user_id=employee_user_id,
            employee_code=payload.employee_code,
            joining_date=payload.joining_date,
            designation=payload.designation,
            department_name=payload.department_name,
            org_department_id=payload.org_department_id,
            team_id=payload.team_id,
            role_id=role_id,
            reporting_manager_id=payload.reporting_manager_id,
            reporting_manager_name=payload.reporting_manager_name,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    db.commit()

    # Notify after commit so onboarding is durable even if notify fails.
    if checklist.employee_user_id is not None:
        try:
            loaded_for_notify = onboard.load_checklist(db, checklist.id)
            if loaded_for_notify is not None:
                provision.notify_team_leader_of_new_hire(
                    db, loaded_for_notify, created_by=current_user
                )
        except Exception:
            pass

    loaded = onboard.load_checklist(db, checklist.id)
    assert loaded is not None
    return _to_detail(
        db,
        loaded,
        current_user,
        triggered=triggered,
        provisioned_temporary_password=provisioned_temporary_password,
    )


@router.get("/{checklist_id}", response_model=OnboardingChecklistDetailRead)
def get_checklist(
    checklist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_view_checklist(db, current_user, checklist):
        raise HTTPException(status_code=403, detail="Not permitted.")
    return _to_detail(db, checklist, current_user)


@router.patch("/{checklist_id}", response_model=OnboardingChecklistDetailRead)
def update_checklist(
    checklist_id: UUID,
    payload: OnboardingChecklistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can edit checklist header.")
    data = payload.model_dump(exclude_unset=True)
    prev_team = checklist.team_id
    prev_manager = checklist.reporting_manager_id
    try:
        from app.core.employee_immutable import reject_immutable_onboarding_mutations

        data = reject_immutable_onboarding_mutations(
            current_code=checklist.employee_code,
            current_joining=checklist.joining_date,
            fields=data,
        )
        onboard.apply_checklist_header(db, checklist, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None

    team_or_manager_changed = (
        loaded.team_id != prev_team or loaded.reporting_manager_id != prev_manager
    )
    if loaded.employee_user_id is not None and team_or_manager_changed:
        try:
            from app.services import hr_onboarding_provisioning as provision

            provision.notify_team_leader_of_new_hire(
                db, loaded, created_by=current_user
            )
        except Exception:
            pass

    return _to_detail(db, loaded, current_user)


@router.delete("/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist(
    checklist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can delete checklists.")
    try:
        from app.services.hr_form_publish import assert_can_delete

        assert_can_delete(checklist, document_label="onboarding checklist")
        onboard.delete_checklist(db, checklist)
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return None


@router.post("/{checklist_id}/publish", response_model=OnboardingChecklistDetailRead)
def publish_checklist(
    checklist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can publish checklists.")
    try:
        from app.services.hr_form_publish import publish_document

        publish_document(checklist, user=current_user)
        db.commit()
        loaded = onboard.load_checklist(db, checklist_id)
        assert loaded is not None
        return _to_detail(db, loaded, current_user)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{checklist_id}/items/{item_id}/status",
    response_model=OnboardingChecklistDetailRead,
)
def update_item_status(
    checklist_id: UUID,
    item_id: UUID,
    payload: OnboardingItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checklist, item = _load_item_for_edit(db, current_user, checklist_id, item_id)
    try:
        onboard.set_item_status(
            db,
            item=item,
            status=payload.status,
            actor=current_user,
            completion_date=payload.completion_date,
            notes=payload.notes,
            reason=payload.reason,
            override=payload.override,
        )
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, ProTrackValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
    return _to_detail(db, loaded, current_user)


def _load_item_for_edit(
    db: Session, current_user: User, checklist_id: UUID, item_id: UUID
) -> tuple[OnboardingChecklist, OnboardingChecklistItem]:
    checklist, item = _load_item_for_view(db, current_user, checklist_id, item_id)
    if not onboard.can_edit_item(db, current_user, item):
        raise HTTPException(
            status_code=403,
            detail="You cannot update items outside your responsibility.",
        )
    return checklist, item


def _load_item_for_view(
    db: Session, current_user: User, checklist_id: UUID, item_id: UUID
) -> tuple[OnboardingChecklist, OnboardingChecklistItem]:
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_view_checklist(db, current_user, checklist):
        raise HTTPException(status_code=403, detail="Not permitted.")
    item = next((row for row in checklist.items if row.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Checklist item not found.")
    return checklist, item


@router.post(
    "/{checklist_id}/items/{item_id}/request",
    response_model=OnboardingChecklistDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item_request(
    checklist_id: UUID,
    item_id: UUID,
    payload: OnboardingItemRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Raise a Help Desk request for one task and link it (task moves to in progress)."""
    _checklist, item = _load_item_for_edit(db, current_user, checklist_id, item_id)
    try:
        tasks.create_request_for_item(
            db,
            item=item,
            actor=current_user,
            priority=payload.priority,
            details=payload.details,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
    return _to_detail(db, loaded, current_user)


@router.patch(
    "/{checklist_id}/items/{item_id}",
    response_model=OnboardingChecklistDetailRead,
)
def update_item(
    checklist_id: UUID,
    item_id: UUID,
    payload: OnboardingItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit due date / named owner (HR) or notes (task owners)."""
    _checklist, item = _load_item_for_edit(db, current_user, checklist_id, item_id)
    data = payload.model_dump(exclude_unset=True)
    manage_only = {"due_date", "owner_user_id"} & set(data)
    if manage_only and not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can change due date or owner.")
    if data.get("owner_user_id") is not None:
        owner = db.get(User, data["owner_user_id"])
        if owner is None or owner.is_deleted or not owner.is_active:
            raise HTTPException(status_code=404, detail="Owner not found.")
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
    return _to_detail(db, loaded, current_user)


@router.get(
    "/{checklist_id}/items/{item_id}/history",
    response_model=list[OnboardingItemHistoryEvent],
)
def item_history(
    checklist_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _checklist, item = _load_item_for_view(db, current_user, checklist_id, item_id)
    return [OnboardingItemHistoryEvent(**row) for row in tasks.history_for_item(db, item)]


@router.post(
    "/{checklist_id}/items/{item_id}/repair-link",
    response_model=OnboardingRepairResult,
)
def repair_item_link(
    checklist_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fix a broken / legacy-shared / missing ticket link (history is kept)."""
    _checklist, item = _load_item_for_edit(db, current_user, checklist_id, item_id)
    try:
        result = tasks.repair_link(db, item=item, actor=current_user)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
    return OnboardingRepairResult(
        actions=list(result.get("actions") or []),
        checklist=_to_detail(db, loaded, current_user),
    )


def _template_config(row) -> OnboardingTemplateConfigRead:
    from app.services import ticketing_service as ticket_rules

    items: list[OnboardingTemplateItemRead] = []
    for s_index, section in enumerate(onboard.parse_structure(row.structure_json)):
        for i_index, item_row in enumerate(section.get("items") or []):
            config = onboard.item_config(item_row)
            responsibility = str(item_row.get("responsibility") or "hr")
            items.append(
                OnboardingTemplateItemRead(
                    section_index=s_index,
                    item_index=i_index,
                    section=str(section.get("section") or section.get("title") or ""),
                    text=str(item_row.get("text") or ""),
                    responsibility=responsibility,
                    responsibility_label=onboard.RESPONSIBILITY_LABELS.get(responsibility, responsibility),
                    execution_type=config["execution_type"],
                    execution_type_label=tasks.EXECUTION_TYPE_LABELS[config["execution_type"]],
                    owner_role=config.get("owner_role"),
                    priority=ticket_rules.normalize_priority(config["priority"]) if config.get("priority") else None,
                    due_offset_days=config.get("due_offset_days"),
                    evidence_required=bool(config.get("evidence_required")),
                    confirm_by=config.get("confirm_by") or "owner",
                    reversible=bool(config.get("reversible", True)),
                    mandatory=bool(config.get("mandatory", True)),
                    blocks_completion=bool(config.get("blocks_completion", True)),
                    ticket_category=config.get("ticket_category"),
                    ticket_subcategory=config.get("ticket_subcategory"),
                    completion_rule=config.get("completion_rule") or "resolved",
                    validation=item_row.get("validation"),
                )
            )
    return OnboardingTemplateConfigRead(
        id=row.id,
        code=row.code,
        name=row.name,
        version=row.version,
        items=items,
        execution_types=dict(tasks.EXECUTION_TYPE_LABELS),
        confirm_by=dict(tasks.CONFIRM_BY_LABELS),
        completion_rules=dict(tasks.COMPLETION_RULES),
        ticket_subcategories=ticket_rules.SUBCATEGORY_LABELS,
        responsibilities=dict(onboard.RESPONSIBILITY_LABELS),
    )


def _load_template_or_404(db: Session, template_id: UUID):
    from app.models.models import OnboardingChecklistTemplate

    row = db.get(OnboardingChecklistTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return row


@router.get("/templates/{template_id}/config", response_model=OnboardingTemplateConfigRead)
def get_template_config(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execution settings per template task (HR / Admin)."""
    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can configure templates.")
    return _template_config(_load_template_or_404(db, template_id))


@router.put(
    "/templates/{template_id}/items/{section_index}/{item_index}",
    response_model=OnboardingTemplateConfigRead,
)
def update_template_item(
    template_id: UUID,
    section_index: int,
    item_index: int,
    payload: OnboardingTemplateItemConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change one task's execution settings. Applies to checklists created
    afterwards; existing checklist tasks keep the settings they started with."""
    import json

    from app.models.enums import ActivityAction, EntityType
    from app.services import ticketing_service as ticket_rules
    from app.services.activity_service import log_activity

    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Only HR / Admin can configure templates.")
    row = _load_template_or_404(db, template_id)
    structure = onboard.parse_structure(row.structure_json)
    try:
        item_row = structure[section_index]["items"][item_index]
    except (IndexError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="Template task not found.") from exc
    data = payload.model_dump()
    kind = data["execution_type"]
    if kind == tasks.TICKET_REQUIRED:
        category = data["ticket_category"] or tasks.RESPONSIBILITY_TICKET_CATEGORY.get(data["responsibility"])
        if category is None:
            raise HTTPException(
                status_code=422,
                detail="A ticket-required task needs a ticket category (manager tasks have no queue).",
            )
        subcategory = data["ticket_subcategory"]
        if subcategory and subcategory not in ticket_rules.SUBCATEGORY_LABELS.get(category, {}):
            raise HTTPException(status_code=422, detail="Unknown ticket subcategory for that category.")
    if kind == tasks.AUTOMATED and not item_row.get("validation"):
        raise HTTPException(
            status_code=422,
            detail="Only tasks with a system check can be automated.",
        )
    if kind == tasks.OPTIONAL:
        data["mandatory"] = False
        data["blocks_completion"] = False
    if data["blocks_completion"] and not data["mandatory"]:
        raise HTTPException(status_code=422, detail="An optional task cannot block completion.")
    old = {key: item_row.get(key) for key in data}
    item_row.update(data)
    item_row["requires_request"] = kind == tasks.TICKET_REQUIRED
    row.structure_json = json.dumps(structure)
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.onboarding_template,
        entity_id=row.id,
        action=ActivityAction.onboarding_template_updated,
        old_value=old,
        new_value={"task": item_row.get("text"), **data},
        outcome="success",
        module="human_resources",
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return _template_config(row)
