"""Onboarding checklist API — PP-HRD-FO-14 New Hire Onboarding Checklist."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import MODULE_HUMAN_RESOURCES
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.models.models import OnboardingChecklist, OnboardingChecklistItem, User
from app.schemas.onboarding import (
    OnboardingChecklistCreate,
    OnboardingChecklistDetailRead,
    OnboardingChecklistItemRead,
    OnboardingChecklistRead,
    OnboardingChecklistUpdate,
    OnboardingItemStatusUpdate,
    OnboardingTemplateRead,
    OnboardingTriggeredTicket,
)
from app.services import onboarding_checklist_service as onboard

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


def _item_read(
    db: Session, item: OnboardingChecklistItem, current_user: User
) -> OnboardingChecklistItemRead:
    is_mine = (
        item.owner_user_id == current_user.id
        or item.responsibility in onboard.responsibilities_for_user(db, current_user)
    )
    ticket = item.help_ticket
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
        status=item.status,
        status_label=onboard.STATUS_LABELS.get(item.status, item.status),
        owner_user_id=item.owner_user_id,
        owner_name=_full_name(item.owner),
        help_ticket_id=item.help_ticket_id,
        help_ticket_number=ticket.ticket_number if ticket is not None else None,
        completed_by_id=item.completed_by_id,
        completed_by_name=_full_name(item.completed_by),
        completion_date=item.completion_date,
        notes=item.notes,
        can_edit=onboard.can_edit_item(db, current_user, item),
        is_mine=is_mine,
    )


def _to_read(
    db: Session, checklist: OnboardingChecklist, current_user: User
) -> OnboardingChecklistRead:
    stats = onboard.completion_stats(checklist)
    my_pending = sum(
        1
        for item in checklist.items
        if item.status == "pending"
        and (
            item.owner_user_id == current_user.id
            or item.responsibility
            in onboard.responsibilities_for_user(db, current_user)
        )
    )
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
        total_items=stats["total"],
        completed_items=stats["completed"],
        pending_items=stats["pending"],
        completion_percent=stats["percent"],
        can_manage=onboard.can_manage_onboarding(db, current_user),
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
) -> OnboardingChecklistDetailRead:
    base = _to_read(db, checklist, current_user)
    items = [_item_read(db, item, current_user) for item in checklist.items]
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
    )


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
    stmt = (
        select(OnboardingChecklist)
        .options(
            # lightweight: items needed for stats
        )
        .order_by(OnboardingChecklist.created_at.desc())
    )
    if status_filter and status_filter != "all":
        stmt = stmt.where(OnboardingChecklist.status == status_filter)

    rows = db.scalars(stmt).all()
    # Load items for stats
    result: list[OnboardingChecklistRead] = []
    for row in rows:
        full = onboard.load_checklist(db, row.id)
        if full is None:
            continue
        if not onboard.can_view_checklist(db, current_user, full):
            continue
        result.append(_to_read(db, full, current_user))
    return result


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

    if payload.employee_user_id is not None:
        emp = db.get(User, payload.employee_user_id)
        if emp is None or emp.is_deleted:
            raise HTTPException(status_code=404, detail="Employee user not found.")

    try:
        checklist, triggered = onboard.create_checklist_from_template(
            db,
            template=template,
            employee_name=payload.employee_name,
            created_by=current_user,
            employee_user_id=payload.employee_user_id,
            employee_code=payload.employee_code,
            joining_date=payload.joining_date,
            designation=payload.designation,
            department_name=payload.department_name,
            org_department_id=payload.org_department_id,
            team_id=payload.team_id,
            role_id=payload.role_id,
            reporting_manager_id=payload.reporting_manager_id,
            reporting_manager_name=payload.reporting_manager_name,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist.id)
    assert loaded is not None
    return _to_detail(db, loaded, current_user, triggered=triggered)


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
    try:
        onboard.apply_checklist_header(db, checklist, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
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
    onboard.delete_checklist(db, checklist)
    db.commit()
    return None


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
    checklist = onboard.load_checklist(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found.")
    if not onboard.can_view_checklist(db, current_user, checklist):
        raise HTTPException(status_code=403, detail="Not permitted.")
    item = next((row for row in checklist.items if row.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Checklist item not found.")
    if not onboard.can_edit_item(db, current_user, item):
        raise HTTPException(
            status_code=403,
            detail="You cannot update items outside your responsibility.",
        )
    try:
        onboard.set_item_status(
            db,
            item=item,
            status=payload.status,
            actor=current_user,
            completion_date=payload.completion_date,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    loaded = onboard.load_checklist(db, checklist_id)
    assert loaded is not None
    return _to_detail(db, loaded, current_user)
