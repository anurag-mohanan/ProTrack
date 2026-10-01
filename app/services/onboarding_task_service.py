"""Onboarding task workflow — execution types, statuses, ticket linkage and audit.

An onboarding task (``OnboardingChecklistItem``) answers "what must happen for
this hire". A Help Desk ``Ticket`` answers "what work was requested from a
department". They are linked explicitly (``item.help_ticket_id`` and
``ticket.onboarding_item_id``) but never treated as the same record.

How a task is executed comes from the template (``execution_type``):

* ``CHECKLIST_ONLY``      — the owner completes it directly.
* ``TICKET_REQUIRED``     — one ticket per task is raised (idempotently); the
  task follows the ticket and completes when the ticket is resolved/closed
  (``completion_rule``). Completing it without that needs an override + reason.
* ``APPROVAL_REQUIRED``   — only the configured confirmer (``confirm_by``) may
  complete it.
* ``EXTERNAL_DEPENDENCY`` — waits on a third party; completion needs evidence.
* ``OPTIONAL``            — never blocks checklist completion.
* ``AUTOMATED``           — completed by the system when its check succeeds;
  manual completion needs an override + reason.

:func:`sync_from_ticket` is the only place a ticket status changes a task; task
changes never write back to the ticket, so there is no loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType, NotificationType
from app.models.models import (
    Activity,
    OnboardingChecklist,
    OnboardingChecklistItem,
    Ticket,
    User,
)
from app.services import ticketing_service as T
from app.services.activity_service import log_activity

MODULE = "human_resources"

NOT_STARTED = "not_started"
READY = "ready"
IN_PROGRESS = "in_progress"
WAITING = "waiting"
BLOCKED = "blocked"
COMPLETED = "completed"
NOT_REQUIRED = "not_required"
WAIVED = "waived"
CANCELLED = "cancelled"

TASK_STATUSES: tuple[str, ...] = (
    NOT_STARTED,
    READY,
    IN_PROGRESS,
    WAITING,
    BLOCKED,
    COMPLETED,
    NOT_REQUIRED,
    WAIVED,
    CANCELLED,
)
RESOLVED_STATUSES = frozenset({COMPLETED, NOT_REQUIRED, WAIVED, CANCELLED})
UNRESOLVED_STATUSES = frozenset({NOT_STARTED, READY, IN_PROGRESS, WAITING, BLOCKED})

LEGACY_STATUS_MAP = {"pending": NOT_STARTED, "not_applicable": NOT_REQUIRED}

STATUS_LABELS: dict[str, str] = {
    NOT_STARTED: "Not started",
    READY: "Ready",
    IN_PROGRESS: "In progress",
    WAITING: "Waiting",
    BLOCKED: "Blocked",
    COMPLETED: "Completed",
    NOT_REQUIRED: "Not required",
    WAIVED: "Waived",
    CANCELLED: "Cancelled",
}

CHECKLIST_ONLY = "CHECKLIST_ONLY"
TICKET_REQUIRED = "TICKET_REQUIRED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
OPTIONAL = "OPTIONAL"
AUTOMATED = "AUTOMATED"
EXECUTION_TYPE_LABELS: dict[str, str] = {
    CHECKLIST_ONLY: "Checklist only",
    TICKET_REQUIRED: "Ticket required",
    APPROVAL_REQUIRED: "Approval required",
    EXTERNAL_DEPENDENCY: "External dependency",
    OPTIONAL: "Optional",
    AUTOMATED: "Automated",
}
CONFIRM_BY_LABELS: dict[str, str] = {
    "owner": "Task owner",
    "hr": "HR / administrator",
    "manager": "Reporting manager",
    "it": "IT",
}
COMPLETION_RULES: dict[str, str] = {
    "resolved": "When the ticket is resolved",
    "closed": "When the ticket is closed",
}

COMPLETION_MANUAL = "manual"
COMPLETION_REQUEST = "request"
COMPLETION_OVERRIDE = "manual_override"
COMPLETION_EVIDENCE = "evidence"
COMPLETION_AUTOMATED = "automated"
COMPLETION_APPROVED = "approved"

TICKET_OPEN = T.OPEN_STATUSES
TICKET_DONE = T.DONE_STATUSES
TICKET_CANCELLED = T.CANCELLED

RESPONSIBILITY_TICKET_CATEGORY: dict[str, str | None] = {
    "hr": "hr",
    "admin": "admin",
    "it": "it",
    "accounts": "other",
    "manager": None,
}

VALIDATION_WORKSTATION = "workstation_assigned"
VALIDATION_EMPLOYEE_CODE = "employee_code_present"

ATTENTION_LABELS: dict[str, str] = {
    "request_missing": "Ticket required — not created",
    "request_resolved": "Linked ticket resolved — confirm completion",
    "request_cancelled": "Linked ticket was cancelled",
    "request_needs_owner": "Linked ticket has no owner",
    "request_waiting": "Linked ticket is waiting",
    "link_broken": "Ticket link is broken",
    "legacy_grouped": "Legacy shared ticket — needs review",
    "blocked": "Blocked",
    "overdue": "Overdue",
    "unassigned": "No named owner",
}

DUE_OFFSET_DAYS: dict[str, int] = {"hr": 0, "admin": 0, "it": 0, "manager": 7, "accounts": 14}


def normalize_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    value = LEGACY_STATUS_MAP.get(value, value)
    if value not in TASK_STATUSES:
        raise ProTrackValidationError(f"Invalid task status: {raw}")
    return value


def current_status(item: OnboardingChecklistItem) -> str:
    return LEGACY_STATUS_MAP.get(item.status, item.status)


def is_resolved(status: str | None) -> bool:
    return LEGACY_STATUS_MAP.get(status or "", status or "") in RESOLVED_STATUSES


def execution_type(item: OnboardingChecklistItem) -> str:
    value = (item.execution_type or "").strip().upper()
    if value in EXECUTION_TYPE_LABELS:
        return value
    return TICKET_REQUIRED if item.requires_request else CHECKLIST_ONLY


def is_mandatory(item: OnboardingChecklistItem) -> bool:
    if execution_type(item) == OPTIONAL:
        return False
    return bool(item.mandatory if item.mandatory is not None else True)


def blocks_completion(item: OnboardingChecklistItem) -> bool:
    if execution_type(item) == OPTIONAL:
        return False
    return bool(item.blocks_completion if item.blocks_completion is not None else True)


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
    if item.ticket_category and item.ticket_category in T.CATEGORY_LABELS:
        return item.ticket_category
    return RESPONSIBILITY_TICKET_CATEGORY.get(item.responsibility)


def has_active_request(item: OnboardingChecklistItem) -> bool:
    ticket = item.help_ticket
    return ticket is not None and ticket.status in TICKET_OPEN


def link_is_broken(item: OnboardingChecklistItem) -> bool:
    return item.help_ticket_id is not None and item.help_ticket is None


def is_legacy_grouped(item: OnboardingChecklistItem) -> bool:
    ticket = item.help_ticket
    return (
        ticket is not None
        and ticket.onboarding_item_id is None
        and bool(ticket.needs_review)
    )


def completion_rule(item: OnboardingChecklistItem) -> str:
    return item.completion_rule if item.completion_rule in COMPLETION_RULES else "resolved"


def ticket_satisfies(item: OnboardingChecklistItem, ticket: Ticket | None) -> bool:
    if ticket is None:
        return False
    if completion_rule(item) == "closed":
        return ticket.status == T.CLOSED
    return ticket.status in TICKET_DONE


def attention_codes(item: OnboardingChecklistItem, today: date | None = None) -> list[str]:
    if is_resolved(item.status):
        return []
    codes: list[str] = []
    ticket = item.help_ticket
    if link_is_broken(item):
        codes.append("link_broken")
    elif ticket is None:
        if execution_type(item) == TICKET_REQUIRED:
            codes.append("request_missing")
    elif ticket.status in TICKET_DONE:
        codes.append("request_resolved")
    elif ticket.status == TICKET_CANCELLED:
        codes.append("request_cancelled")
    else:
        if ticket.needs_owner or ticket.assignee_id is None:
            codes.append("request_needs_owner")
        if ticket.status in T.PENDING_STATUSES:
            codes.append("request_waiting")
    if ticket is not None and is_legacy_grouped(item):
        codes.append("legacy_grouped")
    if current_status(item) == BLOCKED:
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
        key = current_status(item)
        by_status[key] = by_status.get(key, 0) + 1
    resolved = sum(by_status[s] for s in RESOLVED_STATUSES)
    blocking_open = sum(
        1 for item in items if blocks_completion(item) and not is_resolved(item.status)
    )
    return {
        "total": total,
        "completed": by_status[COMPLETED],
        "resolved": resolved,
        "unresolved": total - resolved,
        "not_required": by_status[NOT_REQUIRED],
        "waived": by_status[WAIVED],
        "cancelled": by_status[CANCELLED],
        "blocked": by_status[BLOCKED],
        "waiting": by_status[WAITING],
        "ready": by_status[READY],
        "in_progress": by_status[IN_PROGRESS],
        "not_started": by_status[NOT_STARTED],
        "blocking_open": blocking_open,
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
    checklist = item.checklist
    if item.validation_rule == VALIDATION_EMPLOYEE_CODE:
        if checklist is not None and (checklist.employee_code or "").strip():
            return None
        return "No employee ID is recorded on this onboarding yet."
    if item.validation_rule != VALIDATION_WORKSTATION:
        return None
    user_id = checklist.employee_user_id if checklist else None
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


def _notify_task(db: Session, item: OnboardingChecklistItem, *, title: str, message: str) -> None:
    from app.services import notification_service

    checklist = item.checklist
    recipients = {item.owner_user_id, checklist.created_by_id if checklist else None}
    for user_id in {uid for uid in recipients if uid is not None}:
        try:
            with db.begin_nested():
                notification_service.create_notification(
                    db,
                    user_id=user_id,
                    notification_type=NotificationType.onboarding_task_update,
                    title=title[:200],
                    message=message,
                    entity_type=EntityType.onboarding_task,
                    entity_id=item.id,
                    send_email=False,
                    commit=False,
                )
        except Exception:  # noqa: BLE001 — never lose the task change over a notification
            pass


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
    old_status = current_status(item)
    now = datetime.utcnow()
    item.status = new_status
    item.status_changed_at = now
    item.status_changed_by_id = actor.id if actor is not None else None
    if note is not None and note.strip():
        item.notes = note.strip()
        if completion_type == COMPLETION_EVIDENCE:
            item.evidence_note = note.strip()
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
        item.status_reason = (
            ((reason or "").strip() or None) if new_status in {BLOCKED, WAITING} else None
        )
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
    can_approve: bool | None = None,
) -> TransitionResult:
    """Validated user-driven status change, honouring the task's execution type."""
    new_status = normalize_status(status)
    current = current_status(item)
    clean_reason = (reason or "").strip() or None
    clean_note = (note or "").strip() or None
    kind = execution_type(item)

    if new_status == current:
        raise ProTrackValidationError(f"Task is already {STATUS_LABELS[new_status].lower()}.")
    if current in RESOLVED_STATUSES and new_status in RESOLVED_STATUSES:
        raise ProTrackValidationError(
            "Reopen the task before changing it to another resolved state."
        )
    if current in RESOLVED_STATUSES and not item.reversible and not can_waive:
        raise PermissionError("This task is not reversible. Only HR or an administrator can reopen it.")
    if new_status == BLOCKED and not clean_reason:
        raise ProTrackValidationError("A blocked reason is required.")
    if new_status == WAITING and not clean_reason:
        raise ProTrackValidationError("Say what the task is waiting for.")
    if new_status == WAIVED:
        if not can_waive:
            raise PermissionError("Only HR or an administrator can waive a task.")
        if not clean_reason:
            raise ProTrackValidationError("A waiver reason is required.")
    if new_status == CANCELLED:
        if not clean_reason:
            raise ProTrackValidationError("A cancellation reason is required.")
        if is_mandatory(item) and not can_waive:
            raise PermissionError(
                "This task is mandatory. Only HR or an administrator can cancel it."
            )
    if new_status == NOT_REQUIRED and is_mandatory(item) and kind == TICKET_REQUIRED and not can_waive:
        raise PermissionError("Only HR or an administrator can mark a mandatory ticket task not required.")

    completion_type: str | None = None
    if new_status == COMPLETED:
        completion_type = COMPLETION_MANUAL
        problems: list[str] = []
        failure = validation_failure(db, item)
        if failure:
            problems.append(failure)
        if kind == TICKET_REQUIRED and not ticket_satisfies(item, item.help_ticket):
            ticket = item.help_ticket
            if ticket is None:
                problems.append("This task requires a ticket and none has been resolved.")
            else:
                problems.append(
                    f"Linked ticket {ticket.ticket_number} is "
                    f"{T.STATUS_LABELS.get(ticket.status, ticket.status).lower()}."
                )
        if kind == AUTOMATED:
            problems.append("This task is completed automatically by the system.")
        if kind == APPROVAL_REQUIRED and can_approve is False:
            raise PermissionError(
                f"Only the {CONFIRM_BY_LABELS.get(item.confirm_by or 'hr', 'confirmer').lower()} "
                "can approve this task."
            )
        if problems:
            if not override or not clean_reason:
                raise ProTrackValidationError(
                    " ".join(problems) + " Complete with an override and a reason to proceed."
                )
            completion_type = COMPLETION_OVERRIDE
        elif override and clean_reason:
            completion_type = COMPLETION_OVERRIDE
        elif kind == TICKET_REQUIRED:
            completion_type = COMPLETION_REQUEST
        elif kind == APPROVAL_REQUIRED:
            completion_type = COMPLETION_APPROVED
        if completion_type != COMPLETION_OVERRIDE and (
            item.evidence_required or kind == EXTERNAL_DEPENDENCY
        ):
            if not clean_note:
                raise ProTrackValidationError("Record the evidence for this task to complete it.")
            if completion_type == COMPLETION_MANUAL:
                completion_type = COMPLETION_EVIDENCE

    result = _apply(
        db,
        item=item,
        new_status=new_status,
        actor=actor,
        reason=clean_reason,
        note=note,
        completion_type=completion_type,
        completion_date=completion_date,
    )
    if new_status == BLOCKED:
        _notify_task(
            db,
            item,
            title=f"Onboarding task blocked: {item.item_text}"[:200],
            message=f"{item.checklist.employee_name if item.checklist else ''} · {clean_reason}",
        )
    return result


def complete_automated(
    db: Session, item: OnboardingChecklistItem, *, evidence: str
) -> TransitionResult | None:
    """System completion for AUTOMATED tasks whose check now passes."""
    if execution_type(item) != AUTOMATED or is_resolved(item.status):
        return None
    if validation_failure(db, item):
        return None
    return _apply(
        db,
        item=item,
        new_status=COMPLETED,
        actor=None,
        reason=None,
        note=evidence,
        completion_type=COMPLETION_AUTOMATED,
        source="automation",
    )


# --- Request linkage ------------------------------------------------------


def _ticket_description(item: OnboardingChecklistItem, details: str | None) -> str:
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
    return (
        f"Onboarding task: {item.item_text}\n\n"
        + "\n".join(employee_bits)
        + (f"\n\nDetails:\n{details.strip()}" if details and details.strip() else "")
        + f"\n\nOnboarding checklist id: {checklist.id}\nOnboarding task id: {item.id}"
    )


def primary_ticket_key(item: OnboardingChecklistItem) -> str:
    return f"onboarding_task:{item.id}:primary"


def _link(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    ticket: Ticket,
    actor: User | None,
    source: str,
) -> None:
    previous = item.help_ticket.ticket_number if item.help_ticket is not None else None
    if item.help_ticket_id == ticket.id:
        return
    item.help_ticket_id = ticket.id
    item.help_ticket = ticket
    if item.owner_user_id is None and ticket.assignee_id is not None:
        item.owner_user_id = ticket.assignee_id
    db.flush()
    _log(
        db,
        item=item,
        actor=actor,
        action=ActivityAction.onboarding_task_request_linked,
        old_value={"ticket_number": previous} if previous else None,
        new_value={
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "source": source,
        },
    )


def ensure_ticket_for_item(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    actor: User,
    priority: str | None = None,
    details: str | None = None,
    replace: bool = False,
) -> tuple[Ticket, bool]:
    """Idempotently raise this task's ticket. Returns ``(ticket, created)``.

    The idempotency key is the task id + purpose, so refreshes, retries and event
    replays return the same ticket. A replacement (after the previous ticket was
    cancelled) is keyed on the ticket it replaces, so it too is created once.
    """
    from app.services import ticket_workflow_service as workflow

    if is_resolved(item.status):
        raise ProTrackValidationError("Reopen the task before raising a new request.")
    category = request_category(item)
    if category is None:
        raise ProTrackValidationError(
            "Tasks owned by the reporting manager are completed directly, not via a request."
        )
    if has_active_request(item):
        if replace:
            raise ProTrackValidationError(
                f"Request {item.help_ticket.ticket_number} is already open for this task."
            )
        return item.help_ticket, False
    previous = item.help_ticket
    key = (
        primary_ticket_key(item)
        if previous is None or (previous.onboarding_item_id is None and previous.needs_review)
        else f"onboarding_task:{item.id}:replaces:{previous.id}"
    )
    checklist = item.checklist
    ticket: Ticket | None = None
    created = False
    for _hop in range(5):
        ticket, created = workflow.create_ticket(
            db,
            title=f"Onboarding · {checklist.employee_name} · {item.item_text}",
            description=_ticket_description(item, details),
            category=category,
            subcategory=item.ticket_subcategory,
            priority=priority or item.task_priority,
            requester=actor,
            actor=actor,
            source_module="onboarding",
            source_record_id=str(item.id),
            idempotency_key=key,
            affected_user_id=checklist.employee_user_id,
            onboarding_item_id=item.id,
            due_date=effective_due_date(item),
            location=checklist.department_name,
        )
        if created or ticket.status != T.CANCELLED:
            break
        key = f"onboarding_task:{item.id}:replaces:{ticket.id}"
    assert ticket is not None
    _link(db, item=item, ticket=ticket, actor=actor, source="request_created")
    _follow_ticket(db, item=item, ticket=ticket, actor=actor, source="request_created")
    return ticket, created


def create_request_for_item(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    actor: User,
    priority: str = "normal",
    details: str | None = None,
) -> Ticket:
    """Explicit user action: raise (or replace a cancelled) request for one task."""
    if has_active_request(item):
        raise ProTrackValidationError(
            f"Request {item.help_ticket.ticket_number} is already open for this task."
        )
    ticket, _created = ensure_ticket_for_item(
        db, item=item, actor=actor, priority=priority, details=details, replace=True
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
        _link(db, item=item, ticket=ticket, actor=actor, source="request_linked")
        _follow_ticket(db, item=item, ticket=ticket, actor=actor, source="request_linked")
        linked += 1
    return linked


def _follow_ticket(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    ticket: Ticket,
    actor: User | None,
    source: str,
) -> bool:
    """Move one task to the state implied by its linked ticket. Returns True if changed."""
    status = ticket.status
    current = current_status(item)
    number = ticket.ticket_number

    if status in T.DONE_STATUSES:
        if current in RESOLVED_STATUSES:
            return False
        if ticket_satisfies(item, ticket):
            _apply(
                db,
                item=item,
                new_status=COMPLETED,
                actor=actor,
                reason=None,
                note=f"Completed via linked request {number}.",
                completion_type=COMPLETION_REQUEST,
                source="request_completed",
            )
            _notify_task(
                db,
                item,
                title=f"Onboarding task completed: {item.item_text}"[:200],
                message=f"Completed via {number}.",
            )
            return True
        if current != IN_PROGRESS:
            _apply(
                db,
                item=item,
                new_status=IN_PROGRESS,
                actor=actor,
                reason=None,
                note=None,
                completion_type=None,
                source="request_resolved_awaiting_closure",
            )
            return True
        return False

    if status == T.CANCELLED:
        if current in RESOLVED_STATUSES:
            return False
        if is_mandatory(item):
            if current == BLOCKED and item.status_reason:
                return False
            _apply(
                db,
                item=item,
                new_status=BLOCKED,
                actor=actor,
                reason=f"Linked request {number} was cancelled.",
                note=None,
                completion_type=None,
                source="request_cancelled",
            )
            _notify_task(
                db,
                item,
                title=f"Onboarding task blocked: {item.item_text}"[:200],
                message=f"Linked request {number} was cancelled — raise a replacement or resolve the task.",
            )
        else:
            _apply(
                db,
                item=item,
                new_status=CANCELLED,
                actor=actor,
                reason=f"Linked request {number} was cancelled (optional task).",
                note=None,
                completion_type=None,
                source="request_cancelled",
            )
        return True

    if status in T.PENDING_STATUSES:
        if current in {NOT_STARTED, READY, IN_PROGRESS}:
            _apply(
                db,
                item=item,
                new_status=WAITING,
                actor=actor,
                reason=f"{number}: {T.STATUS_LABELS.get(status, status)}"
                + (f" — {ticket.pending_reason}" if ticket.pending_reason else ""),
                note=None,
                completion_type=None,
                source=source if source != "user" else "request_waiting",
            )
            return True
        return False

    if status in T.OPEN_STATUSES:
        reopened = current == COMPLETED and item.completion_type == COMPLETION_REQUEST
        blocked_by_ticket = current == BLOCKED and (item.status_reason or "").startswith(
            "Linked request"
        )
        if current in {NOT_STARTED, READY, WAITING} or reopened or blocked_by_ticket:
            _apply(
                db,
                item=item,
                new_status=IN_PROGRESS,
                actor=actor,
                reason=None,
                note=None,
                completion_type=None,
                source="request_reopened" if reopened else source,
            )
            return True
    return False


def sync_from_ticket(
    db: Session,
    ticket: Ticket,
    *,
    actor: User | None,
) -> list[OnboardingChecklistItem]:
    """Propagate a ticket status to every task currently linked to it.

    new / open / in_progress    -> task in progress (blocked tasks stay blocked)
    pending_*                   -> task waiting (with the ticket's reason)
    resolved / closed           -> task completed per its completion rule
    cancelled                   -> mandatory task blocked; optional task cancelled
    reopened (from resolved)    -> request-completed task back to in progress
    """
    items = list(
        db.scalars(
            select(OnboardingChecklistItem).where(OnboardingChecklistItem.help_ticket_id == ticket.id)
        ).all()
    )
    touched: list[OnboardingChecklistItem] = []
    checklists: dict[UUID, OnboardingChecklist] = {}
    for item in items:
        if _follow_ticket(db, item=item, ticket=ticket, actor=actor, source="request_open"):
            touched.append(item)
            if item.checklist is not None:
                checklists[item.checklist.id] = item.checklist
    if checklists:
        from app.services.onboarding_checklist_service import refresh_checklist_status

        for checklist in checklists.values():
            try:
                refresh_checklist_status(checklist, db)
            except ProTrackValidationError:
                pass
    return touched


PROVISIONING_TO_TICKET: dict[str, tuple[str, str | None]] = {
    "IN_PROGRESS": (T.IN_PROGRESS, None),
    "READY": (T.IN_PROGRESS, None),
    "WAITING_FOR_ASSET": (T.PENDING_INTERNAL, "Waiting for an asset to become available."),
    "WAITING_FOR_LICENSE": (T.PENDING_INTERNAL, "Waiting for a software license."),
    "COMPLETED": (T.RESOLVED, None),
    "CANCELLED": (T.CANCELLED, "IT provisioning request was cancelled."),
    "REJECTED": (T.CANCELLED, "IT provisioning request was rejected."),
}


def sync_from_provisioning(db: Session, request: Any, *, actor: User | None) -> None:
    """Structured IT provisioning drives its shared ticket (which drives the tasks)."""
    from app.services import ticket_workflow_service as workflow

    if request.ticket_id is None:
        return
    ticket = db.get(Ticket, request.ticket_id)
    if ticket is None:
        return
    target = PROVISIONING_TO_TICKET.get((request.status or "").upper())
    if target is None:
        return
    to_status, reason = target
    if ticket.status == to_status:
        return
    if to_status not in workflow.TRANSITIONS.get(ticket.status, frozenset()):
        sync_from_ticket(db, ticket, actor=actor)
        return
    kwargs: dict[str, Any] = {"reason": reason}
    if to_status == T.RESOLVED:
        kwargs["resolution"] = "IT provisioning request completed."
        kwargs["work_performed"] = (
            f"Provisioning request {request.id} marked COMPLETED"
            + (f" by {actor.first_name} {actor.last_name}".rstrip() if actor else "")
            + ". Assets and licenses are recorded on the employee's IT profile."
        )
        kwargs["resolution_category"] = "fulfilled"
    workflow.transition(
        db, ticket, to_status=to_status, actor=actor, source="it_provisioning", **kwargs
    )


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


# --- Repair ---------------------------------------------------------------


def repair_link(db: Session, *, item: OnboardingChecklistItem, actor: User) -> dict[str, Any]:
    """Fix a broken or legacy-shared link without deleting history.

    * dangling ``help_ticket_id`` -> cleared (logged), then a ticket is raised if
      the task requires one;
    * legacy grouped ticket       -> a dedicated ticket is raised for this task
      (the shared ticket is kept and stays linked to the other tasks);
    * ticket-required task with no ticket -> the ticket is raised.
    """
    actions: list[str] = []
    if link_is_broken(item):
        dangling = item.help_ticket_id
        item.help_ticket_id = None
        db.flush()
        _log(
            db,
            item=item,
            actor=actor,
            action=ActivityAction.onboarding_task_request_linked,
            old_value={"ticket_id": str(dangling)},
            new_value={"ticket_id": None, "source": "repair_dangling_link"},
        )
        actions.append("cleared_dangling_link")
    needs_ticket = execution_type(item) == TICKET_REQUIRED and not is_resolved(item.status)
    if is_legacy_grouped(item) and not is_resolved(item.status):
        item.help_ticket_id = None
        item.help_ticket = None
        db.flush()
        needs_ticket = request_category(item) is not None
        actions.append("detached_legacy_grouped")
    if needs_ticket and not has_active_request(item):
        ticket, created = ensure_ticket_for_item(db, item=item, actor=actor)
        actions.append("ticket_created" if created else "ticket_relinked")
        return {"actions": actions, "ticket_number": ticket.ticket_number}
    if item.help_ticket is not None:
        if _follow_ticket(db, item=item, ticket=item.help_ticket, actor=actor, source="repair"):
            actions.append("status_synced")
    return {
        "actions": actions,
        "ticket_number": item.help_ticket.ticket_number if item.help_ticket else None,
    }


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
                "status": current_status(item),
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
