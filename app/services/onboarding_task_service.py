"""Onboarding task workflow — explicit statuses, request linkage and audit trail.

An onboarding task (``OnboardingChecklistItem``) answers "what must happen for
this hire". A Help Desk ``Ticket`` answers "what work was requested from a
department". They are linked through ``help_ticket_id`` but never treated as
the same record: a task can be completed directly, and a cancelled request
never completes a task.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.models import (
    Activity,
    OnboardingChecklist,
    OnboardingChecklistItem,
    Ticket,
    User,
)
from app.services.activity_service import log_activity

MODULE = "human_resources"

NOT_STARTED = "not_started"
IN_PROGRESS = "in_progress"
BLOCKED = "blocked"
COMPLETED = "completed"
NOT_REQUIRED = "not_required"
WAIVED = "waived"

TASK_STATUSES: tuple[str, ...] = (
    NOT_STARTED,
    IN_PROGRESS,
    BLOCKED,
    COMPLETED,
    NOT_REQUIRED,
    WAIVED,
)
RESOLVED_STATUSES = frozenset({COMPLETED, NOT_REQUIRED, WAIVED})
UNRESOLVED_STATUSES = frozenset({NOT_STARTED, IN_PROGRESS, BLOCKED})

LEGACY_STATUS_MAP = {"pending": NOT_STARTED, "not_applicable": NOT_REQUIRED}

STATUS_LABELS: dict[str, str] = {
    NOT_STARTED: "Not started",
    IN_PROGRESS: "In progress",
    BLOCKED: "Blocked",
    COMPLETED: "Completed",
    NOT_REQUIRED: "Not required",
    WAIVED: "Waived",
}

COMPLETION_MANUAL = "manual"
COMPLETION_REQUEST = "request"
COMPLETION_OVERRIDE = "manual_override"

TICKET_OPEN = frozenset({"open", "in_progress", "on_hold"})
TICKET_DONE = frozenset({"resolved", "closed"})
TICKET_CANCELLED = "cancelled"

RESPONSIBILITY_TICKET_CATEGORY: dict[str, str | None] = {
    "hr": "hr",
    "admin": "admin",
    "it": "it",
    "accounts": "other",
    "manager": None,
}

VALIDATION_WORKSTATION = "workstation_assigned"

ATTENTION_LABELS: dict[str, str] = {
    "request_missing": "IT request not created",
    "request_resolved": "Linked request resolved — confirm completion",
    "request_cancelled": "Linked request was cancelled",
    "blocked": "Blocked",
    "overdue": "Overdue",
    "unassigned": "No named owner",
}

# Days after joining by which each owner bucket should finish.
DUE_OFFSET_DAYS: dict[str, int] = {"hr": 0, "admin": 0, "it": 0, "manager": 7, "accounts": 14}


def normalize_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    value = LEGACY_STATUS_MAP.get(value, value)
    if value not in TASK_STATUSES:
        raise ProTrackValidationError(f"Invalid task status: {raw}")
    return value


def is_resolved(status: str | None) -> bool:
    return LEGACY_STATUS_MAP.get(status or "", status or "") in RESOLVED_STATUSES


def default_due_date(responsibility: str, joining_date: date | None) -> date | None:
    if joining_date is None:
        return None
    return joining_date + timedelta(days=DUE_OFFSET_DAYS.get(responsibility, 0))


def effective_due_date(item: OnboardingChecklistItem) -> date | None:
    if item.due_date is not None:
        return item.due_date
    checklist = item.checklist
    return default_due_date(item.responsibility, checklist.joining_date if checklist else None)


def is_overdue(item: OnboardingChecklistItem, today: date | None = None) -> bool:
    if is_resolved(item.status):
        return False
    due = effective_due_date(item)
    return due is not None and due < (today or date.today())


def request_category(item: OnboardingChecklistItem) -> str | None:
    return RESPONSIBILITY_TICKET_CATEGORY.get(item.responsibility)


def has_active_request(item: OnboardingChecklistItem) -> bool:
    ticket = item.help_ticket
    return ticket is not None and ticket.status in TICKET_OPEN


def attention_codes(item: OnboardingChecklistItem, today: date | None = None) -> list[str]:
    if is_resolved(item.status):
        return []
    codes: list[str] = []
    ticket = item.help_ticket
    if ticket is None:
        if item.requires_request:
            codes.append("request_missing")
    elif ticket.status in TICKET_DONE:
        codes.append("request_resolved")
    elif ticket.status == TICKET_CANCELLED:
        codes.append("request_cancelled")
    if item.status == BLOCKED:
        codes.append("blocked")
    if is_overdue(item, today):
        codes.append("overdue")
    if item.owner_user_id is None:
        codes.append("unassigned")
    return codes


def completion_stats(checklist: OnboardingChecklist) -> dict[str, int]:
    items = list(checklist.items)
    total = len(items)
    by_status: dict[str, int] = {status: 0 for status in TASK_STATUSES}
    for item in items:
        key = LEGACY_STATUS_MAP.get(item.status, item.status)
        by_status[key] = by_status.get(key, 0) + 1
    resolved = sum(by_status[s] for s in RESOLVED_STATUSES)
    return {
        "total": total,
        "completed": by_status[COMPLETED],
        "resolved": resolved,
        "unresolved": total - resolved,
        "not_required": by_status[NOT_REQUIRED],
        "waived": by_status[WAIVED],
        "blocked": by_status[BLOCKED],
        "in_progress": by_status[IN_PROGRESS],
        "not_started": by_status[NOT_STARTED],
        "percent": int(round(resolved * 100 / total)) if total else 100,
    }


# --- Validation -----------------------------------------------------------


def _workstation_assigned(db: Session, user_id: UUID) -> bool:
    from app.models.it_operations import AssetAssignment, WorkstationPackageAssignment

    has_asset = db.scalar(
        select(AssetAssignment.id)
        .where(
            AssetAssignment.assigned_to_user_id == user_id,
            AssetAssignment.returned_date.is_(None),
        )
        .limit(1)
    )
    if has_asset is not None:
        return True
    has_seat = db.scalar(
        select(WorkstationPackageAssignment.id)
        .where(
            WorkstationPackageAssignment.user_id == user_id,
            WorkstationPackageAssignment.status == "ACTIVE",
        )
        .limit(1)
    )
    return has_seat is not None


def validation_failure(db: Session, item: OnboardingChecklistItem) -> str | None:
    """Return a human message when completion evidence is missing, else None."""
    if item.validation_rule != VALIDATION_WORKSTATION:
        return None
    user_id = item.checklist.employee_user_id if item.checklist else None
    if user_id is None:
        return None
    if _workstation_assigned(db, user_id):
        return None
    return "No computer, asset or virtual seat is assigned to this employee yet."


# --- Transitions ----------------------------------------------------------


@dataclass
class TransitionResult:
    item: OnboardingChecklistItem
    old_status: str
    new_status: str


def _log(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    actor: User | None,
    action: ActivityAction,
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any],
) -> None:
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.onboarding_task,
        entity_id=item.id,
        action=action,
        old_value=old_value,
        new_value={"checklist_id": str(item.checklist_id), **new_value},
        outcome="success",
        module=MODULE,
        commit=False,
    )


def _apply(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    new_status: str,
    actor: User | None,
    reason: str | None,
    note: str | None,
    completion_type: str | None,
    completion_date: date | None = None,
    source: str = "user",
) -> TransitionResult:
    old_status = LEGACY_STATUS_MAP.get(item.status, item.status)
    now = datetime.utcnow()
    item.status = new_status
    item.status_changed_at = now
    item.status_changed_by_id = actor.id if actor is not None else None
    if note is not None and note.strip():
        item.notes = note.strip()
    if new_status in RESOLVED_STATUSES:
        item.completed_by_id = actor.id if actor is not None else None
        item.completion_date = completion_date or date.today()
        item.completed_at = now
        item.completion_type = completion_type if new_status == COMPLETED else None
        item.status_reason = (reason or "").strip() or None
    else:
        item.completed_by_id = None
        item.completion_date = None
        item.completed_at = None
        item.completion_type = None
        item.status_reason = ((reason or "").strip() or None) if new_status == BLOCKED else None
    db.flush()
    ticket = item.help_ticket
    _log(
        db,
        item=item,
        actor=actor,
        action=ActivityAction.onboarding_task_status_changed,
        old_value={"status": old_status},
        new_value={
            "status": new_status,
            "reason": item.status_reason,
            "note": (note or "").strip() or None,
            "completion_type": item.completion_type,
            "ticket_number": ticket.ticket_number if ticket is not None else None,
            "source": source,
        },
    )
    return TransitionResult(item=item, old_status=old_status, new_status=new_status)


def transition(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    status: str,
    actor: User,
    can_waive: bool,
    reason: str | None = None,
    note: str | None = None,
    override: bool = False,
    completion_date: date | None = None,
) -> TransitionResult:
    """Validated user-driven status change."""
    new_status = normalize_status(status)
    current = LEGACY_STATUS_MAP.get(item.status, item.status)
    clean_reason = (reason or "").strip() or None

    if new_status == current:
        raise ProTrackValidationError(f"Task is already {STATUS_LABELS[new_status].lower()}.")
    if current in RESOLVED_STATUSES and new_status in RESOLVED_STATUSES:
        raise ProTrackValidationError(
            "Reopen the task before changing it to another resolved state."
        )
    if new_status == BLOCKED and not clean_reason:
        raise ProTrackValidationError("A blocked reason is required.")
    if new_status == WAIVED:
        if not can_waive:
            raise PermissionError("Only HR or an administrator can waive a task.")
        if not clean_reason:
            raise ProTrackValidationError("A waiver reason is required.")

    completion_type: str | None = None
    if new_status == COMPLETED:
        completion_type = COMPLETION_MANUAL
        failure = validation_failure(db, item)
        if failure:
            if not override or not clean_reason:
                raise ProTrackValidationError(
                    f"{failure} Complete with an override and a reason to proceed."
                )
            completion_type = COMPLETION_OVERRIDE
        elif override and clean_reason:
            completion_type = COMPLETION_OVERRIDE

    return _apply(
        db,
        item=item,
        new_status=new_status,
        actor=actor,
        reason=clean_reason,
        note=note,
        completion_type=completion_type,
        completion_date=completion_date,
    )


# --- Request linkage ------------------------------------------------------


def create_request_for_item(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    actor: User,
    priority: str = "medium",
    details: str | None = None,
) -> Ticket:
    from app.services import ticketing_service as tickets

    if is_resolved(item.status):
        raise ProTrackValidationError("Reopen the task before raising a new request.")
    category = request_category(item)
    if category is None:
        raise ProTrackValidationError(
            "Tasks owned by the reporting manager are completed directly, not via a request."
        )
    if has_active_request(item):
        raise ProTrackValidationError(
            f"Request {item.help_ticket.ticket_number} is already open for this task."
        )
    checklist = item.checklist
    due = effective_due_date(item)
    employee_bits = [
        f"Employee: {checklist.employee_name}"
        + (f" ({checklist.employee_code})" if checklist.employee_code else ""),
        f"Department: {checklist.department_name or '—'}",
        f"Team: {checklist.team_name or '—'}",
        f"Role: {checklist.role_name or checklist.designation or '—'}",
        f"Joining date: {checklist.joining_date or 'TBD'}",
        f"Required by: {due or 'TBD'}",
        f"Manager: {checklist.reporting_manager_name or '—'}",
    ]
    description = (
        f"Onboarding task: {item.item_text}\n\n"
        + "\n".join(employee_bits)
        + (f"\n\nDetails:\n{details.strip()}" if details and details.strip() else "")
        + f"\n\nOnboarding checklist id: {checklist.id}\nOnboarding task id: {item.id}"
    )
    assignee_id = tickets.category_contact_id(db, category) or item.owner_user_id
    ticket = Ticket(
        ticket_number=tickets.next_ticket_number(db),
        title=f"Onboarding · {checklist.employee_name} · {item.item_text}"[:200],
        description=description,
        category=category,
        priority=priority if priority in {"low", "medium", "high", "urgent"} else "medium",
        status="open",
        requester_id=actor.id,
        assignee_id=assignee_id,
        org_department_id=tickets.default_department_id_for_category(db, category),
        location=checklist.department_name,
        due_date=due,
    )
    db.add(ticket)
    db.flush()
    previous = item.help_ticket.ticket_number if item.help_ticket is not None else None
    item.help_ticket_id = ticket.id
    item.help_ticket = ticket
    if item.owner_user_id is None and assignee_id is not None:
        item.owner_user_id = assignee_id
    db.flush()
    _log(
        db,
        item=item,
        actor=actor,
        action=ActivityAction.onboarding_task_request_linked,
        old_value={"ticket_number": previous} if previous else None,
        new_value={"ticket_id": str(ticket.id), "ticket_number": ticket.ticket_number},
    )
    if LEGACY_STATUS_MAP.get(item.status, item.status) in {NOT_STARTED, BLOCKED}:
        _apply(
            db,
            item=item,
            new_status=IN_PROGRESS,
            actor=actor,
            reason=None,
            note=None,
            completion_type=None,
            source="request_created",
        )
    return ticket


def link_items_to_ticket(
    db: Session,
    *,
    items: Iterable[OnboardingChecklistItem],
    ticket: Ticket,
    actor: User | None,
) -> int:
    """Attach an existing request to unresolved tasks lacking an active request."""
    linked = 0
    for item in items:
        if is_resolved(item.status) or has_active_request(item):
            continue
        item.help_ticket_id = ticket.id
        item.help_ticket = ticket
        db.flush()
        _log(
            db,
            item=item,
            actor=actor,
            action=ActivityAction.onboarding_task_request_linked,
            old_value=None,
            new_value={"ticket_id": str(ticket.id), "ticket_number": ticket.ticket_number},
        )
        if LEGACY_STATUS_MAP.get(item.status, item.status) == NOT_STARTED:
            _apply(
                db,
                item=item,
                new_status=IN_PROGRESS,
                actor=actor,
                reason=None,
                note=None,
                completion_type=None,
                source="request_linked",
            )
        linked += 1
    return linked


def sync_from_ticket(
    db: Session,
    ticket: Ticket,
    *,
    actor: User | None,
    status: str | None = None,
) -> list[OnboardingChecklistItem]:
    """Propagate a request status change to every task linked to it.

    open / in_progress / on_hold -> task in progress (blocked tasks stay blocked)
    resolved / closed            -> task completed (completion_type=request)
    cancelled                    -> task blocked with reason; never completed
    """
    ticket_status = (status or ticket.status or "").lower()
    items = list(
        db.scalars(
            select(OnboardingChecklistItem).where(OnboardingChecklistItem.help_ticket_id == ticket.id)
        ).all()
    )
    touched: list[OnboardingChecklistItem] = []
    checklists: dict[UUID, OnboardingChecklist] = {}
    for item in items:
        current = LEGACY_STATUS_MAP.get(item.status, item.status)
        if current in RESOLVED_STATUSES:
            continue
        if ticket_status in TICKET_DONE:
            _apply(
                db,
                item=item,
                new_status=COMPLETED,
                actor=actor,
                reason=None,
                note=f"Completed via linked request {ticket.ticket_number}.",
                completion_type=COMPLETION_REQUEST,
                source="request_completed",
            )
        elif ticket_status == TICKET_CANCELLED:
            if current == BLOCKED and item.status_reason:
                continue
            _apply(
                db,
                item=item,
                new_status=BLOCKED,
                actor=actor,
                reason=f"Linked request {ticket.ticket_number} was cancelled.",
                note=None,
                completion_type=None,
                source="request_cancelled",
            )
        elif ticket_status in TICKET_OPEN:
            if current != NOT_STARTED:
                continue
            _apply(
                db,
                item=item,
                new_status=IN_PROGRESS,
                actor=actor,
                reason=None,
                note=None,
                completion_type=None,
                source="request_open",
            )
        else:
            continue
        touched.append(item)
        if item.checklist is not None:
            checklists[item.checklist.id] = item.checklist
    if checklists:
        from app.services.onboarding_checklist_service import refresh_checklist_status

        for checklist in checklists.values():
            try:
                refresh_checklist_status(checklist, db)
            except ProTrackValidationError:
                # Required trainings still open — the checklist stays in progress.
                pass
    return touched


PROVISIONING_TO_TICKET_STATUS = {
    "COMPLETED": "resolved",
    "CANCELLED": "cancelled",
    "REJECTED": "cancelled",
}


def sync_from_provisioning(db: Session, request: Any, *, actor: User | None) -> None:
    """Structured IT provisioning shares its Help Desk ticket with the task."""
    if request.ticket_id is None:
        return
    ticket = db.get(Ticket, request.ticket_id)
    if ticket is None:
        return
    mapped = PROVISIONING_TO_TICKET_STATUS.get((request.status or "").upper(), "in_progress")
    sync_from_ticket(db, ticket, actor=actor, status=mapped)


# --- History --------------------------------------------------------------


def history_for_item(db: Session, item: OnboardingChecklistItem) -> list[dict[str, Any]]:
    import json

    rows = db.execute(
        select(Activity, User.first_name, User.last_name)
        .outerjoin(User, User.id == Activity.user_id)
        .where(
            Activity.entity_type == EntityType.onboarding_task,
            Activity.entity_id == item.id,
        )
        .order_by(Activity.created_at.desc())
    ).all()

    def _parse(raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    events: list[dict[str, Any]] = []
    for activity, first, last in rows:
        old = _parse(activity.old_value)
        new = _parse(activity.new_value)
        actor_name = f"{first or ''} {last or ''}".strip() or None
        if activity.action == ActivityAction.onboarding_task_request_linked:
            event = "request_linked"
        else:
            event = "status_changed"
        events.append(
            {
                "at": activity.created_at,
                "actor_name": actor_name or ("System" if activity.user_id is None else None),
                "event": event,
                "old_status": old.get("status"),
                "new_status": new.get("status"),
                "reason": new.get("reason"),
                "note": new.get("note"),
                "completion_type": new.get("completion_type"),
                "ticket_number": new.get("ticket_number"),
                "source": new.get("source"),
            }
        )
    events.append(
        {
            "at": item.created_at,
            "actor_name": None,
            "event": "created",
            "old_status": None,
            "new_status": None,
            "reason": None,
            "note": None,
            "completion_type": None,
            "ticket_number": None,
            "source": None,
        }
    )
    return events


# --- Attention across checklists -----------------------------------------


def attention_summary(
    items: Iterable[OnboardingChecklistItem], *, today: date | None = None
) -> dict[str, Any]:
    counts: dict[str, int] = {code: 0 for code in ATTENTION_LABELS}
    rows: list[dict[str, Any]] = []
    for item in items:
        codes = attention_codes(item, today)
        if not codes:
            continue
        for code in codes:
            counts[code] += 1
        checklist = item.checklist
        rows.append(
            {
                "checklist_id": str(item.checklist_id),
                "item_id": str(item.id),
                "employee_name": checklist.employee_name if checklist else None,
                "item_text": item.item_text,
                "responsibility": item.responsibility,
                "status": LEGACY_STATUS_MAP.get(item.status, item.status),
                "due_date": effective_due_date(item),
                "attention": codes,
                "ticket_number": item.help_ticket.ticket_number if item.help_ticket else None,
            }
        )
    actionable = {k: v for k, v in counts.items() if k != "unassigned"}
    return {
        "total_tasks": len(rows),
        "counts": counts,
        "actionable_total": sum(1 for r in rows if set(r["attention"]) - {"unassigned"}),
        "labels": ATTENTION_LABELS,
        "items": rows,
        "breakdown": actionable,
    }
