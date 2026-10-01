"""Ticket lifecycle — the single write path for every ticket in ProTrack.

* :func:`create_ticket` is idempotent on ``idempotency_key`` (unique per tenant)
  and allocates a race-safe ticket number.
* :func:`resolve_routing` picks the owner from admin configuration only
  (subcategory rule, then category route; primary, then backup). With no valid
  owner the ticket stays in the queue flagged ``needs_owner`` and the escalation
  owner (or administrators) are told.
* :func:`transition` enforces the status graph and required fields, records the
  audit trail, notifies, and propagates to linked onboarding tasks.
* :func:`assign` / :func:`transfer` keep a full assignment history.
* :func:`run_sla_sweep` sends due-soon / overdue alerts and escalations once.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType, NotificationType
from app.models.models import (
    Role,
    Ticket,
    TicketAssignmentHistory,
    TicketCategoryRoute,
    TicketComment,
    TicketNotificationLog,
    TicketRoutingRule,
    TicketSlaPolicy,
    User,
)
from app.services import ticketing_service as tickets
from app.services.activity_service import log_activity

logger = logging.getLogger(__name__)

MODULE = "tickets"

T = tickets
_PENDING = (T.PENDING_REQUESTER, T.PENDING_INTERNAL, T.PENDING_VENDOR)
_WORKING = frozenset({T.OPEN, T.IN_PROGRESS, *_PENDING})

TRANSITIONS: dict[str, frozenset[str]] = {
    T.NEW: frozenset({T.OPEN, T.IN_PROGRESS, *_PENDING, T.RESOLVED, T.CANCELLED}),
    T.OPEN: frozenset({T.IN_PROGRESS, *_PENDING, T.RESOLVED, T.CANCELLED}),
    T.IN_PROGRESS: frozenset({T.OPEN, *_PENDING, T.RESOLVED, T.CANCELLED}),
    T.RESOLVED: frozenset({T.CLOSED, T.OPEN, T.IN_PROGRESS}),
    T.CLOSED: frozenset({T.OPEN}),
    T.CANCELLED: frozenset({T.OPEN}),
}
for _pending in (*_PENDING, T.LEGACY_ON_HOLD):
    TRANSITIONS[_pending] = frozenset(
        {T.OPEN, T.IN_PROGRESS, *_PENDING, T.RESOLVED, T.CANCELLED} - {_pending}
    )

CLOSURE_REASONS: dict[str, str] = {
    "resolved": "Resolved",
    "confirmed_by_requester": "Confirmed by requester",
    "no_response": "No response from requester",
    "duplicate": "Duplicate",
    "superseded": "Superseded by another request",
}
RESOLUTION_CATEGORIES: dict[str, str] = {
    "fulfilled": "Request fulfilled",
    "fixed": "Fault fixed",
    "workaround": "Workaround provided",
    "no_fault": "No fault found",
    "not_required": "No longer required",
}

DEFAULT_SLA: tuple[tuple[str, int, int, int, int], ...] = (
    # priority, response_h, resolution_h, due_soon_h, escalate_after_h
    ("urgent", 1, 8, 2, 4),
    ("high", 4, 24, 8, 8),
    ("normal", 8, 72, 24, 24),
    ("low", 24, 120, 24, 48),
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uid() -> str:
    return uuid4().hex[:12]


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _name(user: User | None) -> str:
    if user is None:
        return "Unassigned"
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _active_user(db: Session, user_id: UUID | None) -> User | None:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or user.is_deleted or not user.is_active:
        return None
    return user


# --- SLA ------------------------------------------------------------------
def ensure_default_sla_policies(db: Session) -> None:
    if db.scalar(select(TicketSlaPolicy.id).limit(1)) is not None:
        return
    for priority, response_h, resolution_h, due_soon_h, escalate_h in DEFAULT_SLA:
        db.add(
            TicketSlaPolicy(
                category="*",
                priority=priority,
                response_hours=response_h,
                resolution_hours=resolution_h,
                due_soon_hours=due_soon_h,
                escalate_after_hours=escalate_h,
                is_active=True,
            )
        )
    db.flush()


def sla_policy_for(db: Session, category: str, priority: str) -> TicketSlaPolicy | None:
    priority = T.normalize_priority(priority)
    rows = db.scalars(
        select(TicketSlaPolicy).where(
            TicketSlaPolicy.priority == priority,
            TicketSlaPolicy.category.in_([category, "*"]),
            TicketSlaPolicy.is_active.is_(True),
        )
    ).all()
    specific = [row for row in rows if row.category == category]
    return (specific or list(rows) or [None])[0]


def _apply_sla(db: Session, ticket: Ticket) -> None:
    policy = sla_policy_for(db, ticket.category, ticket.priority)
    if policy is None or not policy.resolution_hours:
        ticket.sla_due_at = None
        return
    start = ticket.created_at or _now()
    ticket.sla_due_at = start + timedelta(hours=policy.resolution_hours)


# --- Routing --------------------------------------------------------------
@dataclass
class RoutingDecision:
    assignee_id: UUID | None
    group: str
    escalation_user_id: UUID | None
    source: str
    needs_owner: bool
    default_priority: str | None = None


def _matching_rules(
    db: Session, category: str, subcategory: str | None, source_module: str | None, today: date
) -> list[TicketRoutingRule]:
    rows = db.scalars(
        select(TicketRoutingRule).where(
            TicketRoutingRule.category == category, TicketRoutingRule.is_active.is_(True)
        )
    ).all()
    matches: list[tuple[int, TicketRoutingRule]] = []
    for rule in rows:
        if rule.effective_from is not None and rule.effective_from > today:
            continue
        if rule.subcategory and rule.subcategory != subcategory:
            continue
        if rule.source_module and rule.source_module != source_module:
            continue
        score = (2 if rule.subcategory else 0) + (1 if rule.source_module else 0)
        matches.append((score, rule))
    matches.sort(key=lambda pair: pair[0], reverse=True)
    return [rule for _score, rule in matches]


def resolve_routing(
    db: Session,
    *,
    category: str,
    subcategory: str | None = None,
    source_module: str | None = None,
) -> RoutingDecision:
    today = date.today()
    candidates: list[tuple[UUID | None, str]] = []
    escalation: UUID | None = None
    default_priority: str | None = None
    for rule in _matching_rules(db, category, subcategory, source_module, today):
        candidates.append((rule.primary_user_id, "rule_primary"))
        candidates.append((rule.backup_user_id, "rule_backup"))
        escalation = escalation or rule.escalation_user_id
        default_priority = default_priority or rule.default_priority
    route = db.scalar(select(TicketCategoryRoute).where(TicketCategoryRoute.category == category))
    if route is not None and route.is_active and (
        route.effective_from is None or route.effective_from <= today
    ):
        candidates.append((route.assignee_user_id, "category_primary"))
        candidates.append((route.backup_user_id, "category_backup"))
        escalation = escalation or route.escalation_user_id
    for user_id, source in candidates:
        if _active_user(db, user_id) is not None:
            return RoutingDecision(
                assignee_id=user_id,
                group=category,
                escalation_user_id=escalation if _active_user(db, escalation) else None,
                source=source,
                needs_owner=False,
                default_priority=default_priority,
            )
    return RoutingDecision(
        assignee_id=None,
        group=category,
        escalation_user_id=escalation if _active_user(db, escalation) else None,
        source="queue",
        needs_owner=True,
        default_priority=default_priority,
    )


def admin_user_ids(db: Session) -> set[UUID]:
    rows = db.scalars(
        select(User.id)
        .join(Role, Role.id == User.role_id)
        .where(Role.name == "Admin", User.is_active.is_(True), User.is_deleted.is_(False))
    ).all()
    return set(rows)


# --- Notifications --------------------------------------------------------
def notify(
    db: Session,
    ticket: Ticket,
    *,
    event_key: str,
    user_ids: Iterable[UUID | None],
    notification_type: NotificationType,
    title: str,
    message: str,
    exclude: UUID | None = None,
) -> int:
    """Create one in-app notification per recipient per event (deduplicated)."""
    from app.services import notification_service

    sent = 0
    for user_id in {uid for uid in user_ids if uid is not None and uid != exclude}:
        existing = db.scalar(
            select(TicketNotificationLog).where(
                TicketNotificationLog.ticket_id == ticket.id,
                TicketNotificationLog.event_key == event_key,
                TicketNotificationLog.user_id == user_id,
            )
        )
        if existing is not None and existing.status == "sent":
            continue
        log = existing or TicketNotificationLog(
            ticket_id=ticket.id, event_key=event_key, user_id=user_id, attempts=0
        )
        log.attempts = int(log.attempts or 0) + 1
        try:
            with db.begin_nested():
                notification_service.create_notification(
                    db,
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title[:200],
                    message=message,
                    entity_type=EntityType.ticket,
                    entity_id=ticket.id,
                    send_email=False,
                    commit=False,
                )
            log.status = "sent"
            log.error = None
            sent += 1
        except Exception as exc:  # noqa: BLE001 — the ticket change must not be lost
            logger.exception("Ticket notification failed for %s", ticket.ticket_number)
            log.status = "failed"
            log.error = str(exc)[:500]
        db.add(log)
    db.flush()
    return sent


def retry_failed_notifications(db: Session, ticket: Ticket) -> int:
    failed = db.scalars(
        select(TicketNotificationLog).where(
            TicketNotificationLog.ticket_id == ticket.id,
            TicketNotificationLog.status == "failed",
        )
    ).all()
    count = 0
    for row in failed:
        count += notify(
            db,
            ticket,
            event_key=row.event_key,
            user_ids=[row.user_id],
            notification_type=NotificationType.ticket_status_changed,
            title=f"{ticket.ticket_number} · {ticket.title}",
            message=f"Update on {ticket.ticket_number}: {T.STATUS_LABELS.get(ticket.status, ticket.status)}.",
        )
    return count


# --- Audit ----------------------------------------------------------------
def _log(
    db: Session,
    ticket: Ticket,
    *,
    actor: User | None,
    action: ActivityAction,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> None:
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.ticket,
        entity_id=ticket.id,
        action=action,
        old_value=old,
        new_value={"ticket": ticket.ticket_number, **(new or {})},
        outcome="success",
        module=MODULE,
        commit=False,
    )


def _record_assignment(
    db: Session,
    ticket: Ticket,
    *,
    previous_assignee_id: UUID | None,
    previous_group: str | None,
    actor: User | None,
    change_type: str,
    reason: str | None,
) -> None:
    db.add(
        TicketAssignmentHistory(
            ticket_id=ticket.id,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=ticket.assignee_id,
            previous_group=previous_group,
            new_group=ticket.assignment_group,
            changed_by_id=actor.id if actor is not None else None,
            change_type=change_type,
            reason=_clean(reason),
        )
    )
    db.flush()


# --- Creation -------------------------------------------------------------
def find_by_key(db: Session, idempotency_key: str) -> Ticket | None:
    return db.scalar(select(Ticket).where(Ticket.idempotency_key == idempotency_key))


def create_ticket(
    db: Session,
    *,
    title: str,
    category: str,
    requester: User,
    actor: User | None = None,
    description: str | None = None,
    subcategory: str | None = None,
    priority: str | None = None,
    source_module: str = "help_desk",
    source_record_id: str | None = None,
    idempotency_key: str | None = None,
    affected_user_id: UUID | None = None,
    onboarding_item_id: UUID | None = None,
    related_asset_id: UUID | None = None,
    related_license_pool_id: UUID | None = None,
    related_stock_item_id: UUID | None = None,
    due_date: date | None = None,
    location: str | None = None,
    org_department_id: UUID | None = None,
    assignee_id: UUID | None = None,
) -> tuple[Ticket, bool]:
    """Create (or return the existing) ticket. Returns ``(ticket, created)``."""
    if category not in T.CATEGORY_LABELS:
        raise ProTrackValidationError(f"Unknown ticket category: {category}")
    if idempotency_key:
        existing = find_by_key(db, idempotency_key)
        if existing is not None:
            return existing, False

    actor = actor or requester
    decision = resolve_routing(
        db, category=category, subcategory=subcategory, source_module=source_module
    )
    explicit = _active_user(db, assignee_id)
    owner_id = explicit.id if explicit is not None else decision.assignee_id
    priority_value = T.normalize_priority(priority or decision.default_priority)
    now = _now()

    ticket: Ticket | None = None
    for _attempt in range(8):
        candidate = Ticket(
            ticket_number=T.next_ticket_number(db),
            title=title.strip()[:200],
            description=description,
            category=category,
            subcategory=subcategory,
            priority=priority_value,
            status=T.OPEN if owner_id else T.NEW,
            requester_id=requester.id,
            assignee_id=owner_id,
            org_department_id=org_department_id or T.default_department_id_for_category(db, category),
            location=location,
            due_date=due_date,
            source_module=source_module,
            source_record_id=source_record_id,
            idempotency_key=idempotency_key,
            affected_user_id=affected_user_id,
            onboarding_item_id=onboarding_item_id,
            related_asset_id=related_asset_id,
            related_license_pool_id=related_license_pool_id,
            related_stock_item_id=related_stock_item_id,
            assignment_group=decision.group,
            needs_owner=owner_id is None,
            created_by_id=actor.id,
            updated_by_id=actor.id,
            assigned_at=now if owner_id else None,
            last_activity_at=now,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            ticket = candidate
            break
        except IntegrityError:
            if idempotency_key:
                existing = find_by_key(db, idempotency_key)
                if existing is not None:
                    return existing, False
            continue
    if ticket is None:
        raise ProTrackValidationError("Could not allocate a ticket number. Please retry.", status_code=409)

    ensure_default_sla_policies(db)
    _apply_sla(db, ticket)
    db.flush()
    _log(
        db,
        ticket,
        actor=actor,
        action=ActivityAction.ticket_created,
        new={
            "category": category,
            "subcategory": subcategory,
            "priority": priority_value,
            "status": ticket.status,
            "source_module": source_module,
            "source_record_id": source_record_id,
            "assignee_id": str(owner_id) if owner_id else None,
            "routing": "explicit" if explicit is not None else decision.source,
        },
    )
    _record_assignment(
        db,
        ticket,
        previous_assignee_id=None,
        previous_group=None,
        actor=actor,
        change_type="explicit" if explicit is not None else f"auto:{decision.source}",
        reason=None if owner_id else "No active owner configured for this queue.",
    )
    if owner_id:
        notify(
            db,
            ticket,
            event_key=f"assigned:{owner_id}",
            user_ids=[owner_id],
            notification_type=NotificationType.ticket_assigned,
            title=f"New ticket {ticket.ticket_number} assigned to you",
            message=f"{ticket.title} · Priority {T.PRIORITY_LABELS.get(ticket.priority, ticket.priority)}",
            exclude=actor.id,
        )
    else:
        recipients = (
            {decision.escalation_user_id} if decision.escalation_user_id else admin_user_ids(db)
        )
        notify(
            db,
            ticket,
            event_key="needs_owner",
            user_ids=recipients,
            notification_type=NotificationType.ticket_needs_owner,
            title=f"{ticket.ticket_number} needs an owner",
            message=(
                f"{ticket.title} is in the {T.CATEGORY_LABELS.get(category, category)} queue with no "
                "active owner configured. Assign it or update ticket routing."
            ),
        )
    return ticket, True


# --- Assignment -----------------------------------------------------------
def assign(
    db: Session,
    ticket: Ticket,
    *,
    assignee_id: UUID | None,
    actor: User,
    reason: str | None = None,
    change_type: str = "assign",
) -> Ticket:
    if ticket.status in T.TERMINAL_STATUSES:
        raise ProTrackValidationError("Reopen the ticket before changing its owner.")
    if assignee_id is not None and _active_user(db, assignee_id) is None:
        raise ProTrackValidationError("Assignee not found or inactive.", status_code=404)
    previous = ticket.assignee_id
    if previous == assignee_id:
        return ticket
    if previous is not None and change_type == "assign":
        change_type = "reassign"
    ticket.assignee_id = assignee_id
    ticket.needs_owner = assignee_id is None
    ticket.assigned_at = _now() if assignee_id else None
    ticket.updated_by_id = actor.id
    ticket.last_activity_at = _now()
    old_status = ticket.status
    if assignee_id is not None and ticket.status == T.NEW:
        T.apply_status_timestamps(ticket, T.OPEN)
    db.flush()
    _record_assignment(
        db,
        ticket,
        previous_assignee_id=previous,
        previous_group=ticket.assignment_group,
        actor=actor,
        change_type=change_type,
        reason=reason,
    )
    _log(
        db,
        ticket,
        actor=actor,
        action=ActivityAction.ticket_assigned,
        old={"assignee_id": str(previous) if previous else None, "status": old_status},
        new={
            "assignee_id": str(assignee_id) if assignee_id else None,
            "status": ticket.status,
            "change_type": change_type,
            "reason": _clean(reason),
        },
    )
    if assignee_id is not None:
        notify(
            db,
            ticket,
            event_key=f"assigned:{assignee_id}:{_uid()}",
            user_ids=[assignee_id],
            notification_type=NotificationType.ticket_assigned,
            title=f"{ticket.ticket_number} assigned to you",
            message=f"{ticket.title}" + (f" · {reason.strip()}" if _clean(reason) else ""),
            exclude=actor.id,
        )
    if previous is not None and previous != actor.id:
        notify(
            db,
            ticket,
            event_key=f"unassigned:{previous}:{_uid()}",
            user_ids=[previous],
            notification_type=NotificationType.ticket_assigned,
            title=f"{ticket.ticket_number} was reassigned",
            message=f"Now owned by {_name(db.get(User, assignee_id)) if assignee_id else 'the queue'}.",
        )
    if old_status != ticket.status:
        _sync_side_effects(db, ticket, actor)
    return ticket


def transfer(
    db: Session,
    ticket: Ticket,
    *,
    category: str,
    subcategory: str | None,
    actor: User,
    reason: str | None,
    assignee_id: UUID | None = None,
) -> Ticket:
    if category not in T.CATEGORY_LABELS:
        raise ProTrackValidationError(f"Unknown ticket category: {category}")
    if not _clean(reason):
        raise ProTrackValidationError("A transfer reason is required.")
    if ticket.status in T.TERMINAL_STATUSES:
        raise ProTrackValidationError("Reopen the ticket before transferring it.")
    previous_group = ticket.assignment_group
    previous_assignee = ticket.assignee_id
    old = {"category": ticket.category, "subcategory": ticket.subcategory}
    ticket.category = category
    ticket.subcategory = subcategory
    decision = resolve_routing(
        db, category=category, subcategory=subcategory, source_module=ticket.source_module
    )
    explicit = _active_user(db, assignee_id)
    ticket.assignee_id = explicit.id if explicit else decision.assignee_id
    ticket.assignment_group = decision.group
    ticket.needs_owner = ticket.assignee_id is None
    ticket.assigned_at = _now() if ticket.assignee_id else None
    ticket.org_department_id = T.default_department_id_for_category(db, category)
    ticket.updated_by_id = actor.id
    ticket.last_activity_at = _now()
    if ticket.assignee_id is None and ticket.status == T.OPEN:
        T.apply_status_timestamps(ticket, T.NEW)
    elif ticket.assignee_id is not None and ticket.status == T.NEW:
        T.apply_status_timestamps(ticket, T.OPEN)
    db.flush()
    _record_assignment(
        db,
        ticket,
        previous_assignee_id=previous_assignee,
        previous_group=previous_group,
        actor=actor,
        change_type="transfer",
        reason=reason,
    )
    _log(
        db,
        ticket,
        actor=actor,
        action=ActivityAction.ticket_transferred,
        old=old,
        new={
            "category": category,
            "subcategory": subcategory,
            "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None,
            "reason": _clean(reason),
        },
    )
    if ticket.assignee_id:
        notify(
            db,
            ticket,
            event_key=f"assigned:{ticket.assignee_id}:{_uid()}",
            user_ids=[ticket.assignee_id],
            notification_type=NotificationType.ticket_assigned,
            title=f"{ticket.ticket_number} transferred to you",
            message=f"{ticket.title} · {reason.strip()}",
            exclude=actor.id,
        )
    else:
        notify(
            db,
            ticket,
            event_key=f"needs_owner:{category}",
            user_ids={decision.escalation_user_id} if decision.escalation_user_id else admin_user_ids(db),
            notification_type=NotificationType.ticket_needs_owner,
            title=f"{ticket.ticket_number} needs an owner",
            message=f"Transferred to {T.CATEGORY_LABELS.get(category, category)} with no active owner.",
        )
    return ticket


# --- Transitions ----------------------------------------------------------
def allowed_transitions(ticket: Ticket) -> list[str]:
    return [s for s in T.STATUS_ORDER if s in TRANSITIONS.get(ticket.status, frozenset())]


def requester_transitions(ticket: Ticket) -> list[str]:
    """What a requester (who is not an agent) may do on their own ticket."""
    allowed: list[str] = []
    if ticket.status in T.OPEN_STATUSES:
        allowed.append(T.CANCELLED)
    if ticket.status == T.RESOLVED:
        allowed.extend([T.OPEN, T.CLOSED])
    return allowed


def transition(
    db: Session,
    ticket: Ticket,
    *,
    to_status: str,
    actor: User | None,
    resolution: str | None = None,
    work_performed: str | None = None,
    resolution_category: str | None = None,
    closure_reason: str | None = None,
    reason: str | None = None,
    source: str = "user",
) -> Ticket:
    """Validated status change. ``actor=None`` means a system-driven change."""
    to_status = (to_status or "").strip().lower()
    if to_status not in T.STATUS_ORDER:
        raise ProTrackValidationError(f"Invalid ticket status: {to_status}")
    current = ticket.status
    if to_status == current:
        raise ProTrackValidationError(
            f"Ticket is already {T.STATUS_LABELS.get(current, current).lower()}."
        )
    if to_status not in TRANSITIONS.get(current, frozenset()):
        raise ProTrackValidationError(
            f"Cannot move a ticket from {T.STATUS_LABELS.get(current, current)} "
            f"to {T.STATUS_LABELS.get(to_status, to_status)}."
        )
    clean_reason = _clean(reason)
    now = _now()
    old = {
        "status": current,
        "resolution": ticket.resolution,
        "work_performed": ticket.work_performed,
        "closure_reason": ticket.closure_reason,
        "cancellation_reason": ticket.cancellation_reason,
    }
    reopening = current in T.TERMINAL_STATUSES and to_status in _WORKING

    if to_status == T.RESOLVED:
        summary = _clean(resolution) or _clean(ticket.resolution)
        work = _clean(work_performed) or _clean(ticket.work_performed)
        if not summary:
            raise ProTrackValidationError("A resolution summary is required to resolve a ticket.")
        if not work:
            raise ProTrackValidationError("Describe the work performed to resolve the ticket.")
        if resolution_category and resolution_category not in RESOLUTION_CATEGORIES:
            raise ProTrackValidationError("Unknown resolution category.")
        ticket.resolution = summary
        ticket.work_performed = work
        ticket.resolution_category = resolution_category or ticket.resolution_category
    elif to_status == T.CLOSED:
        reason_key = closure_reason or "resolved"
        if reason_key not in CLOSURE_REASONS:
            raise ProTrackValidationError("Unknown closure reason.")
        ticket.closure_reason = reason_key
    elif to_status == T.CANCELLED:
        if not clean_reason:
            raise ProTrackValidationError("A cancellation reason is required.")
        ticket.cancellation_reason = clean_reason
    elif to_status in _PENDING:
        if not clean_reason:
            raise ProTrackValidationError("Say what the ticket is waiting for.")
        ticket.pending_reason = clean_reason
    if reopening:
        if not clean_reason:
            raise ProTrackValidationError("A reason is required to reopen a ticket.")
        ticket.resolution = None
        ticket.work_performed = None
        ticket.resolution_category = None
        ticket.closure_reason = None
        ticket.cancellation_reason = None
    if to_status in {T.OPEN, T.IN_PROGRESS}:
        ticket.pending_reason = None

    T.apply_status_timestamps(ticket, to_status)
    if to_status == T.IN_PROGRESS and ticket.first_response_at is None:
        ticket.first_response_at = now
    if reopening:
        ticket.escalation_level = 0
        ticket.escalated_at = None
        _apply_sla_from(ticket, db, now)
    ticket.updated_by_id = actor.id if actor is not None else ticket.updated_by_id
    db.flush()

    action = ActivityAction.ticket_status_changed
    if to_status == T.RESOLVED:
        action = ActivityAction.ticket_resolved
    elif to_status == T.CLOSED:
        action = ActivityAction.ticket_closed
    elif to_status == T.CANCELLED:
        action = ActivityAction.ticket_cancelled
    elif reopening:
        action = ActivityAction.ticket_reopened
    _log(
        db,
        ticket,
        actor=actor,
        action=action,
        old=old,
        new={
            "status": to_status,
            "resolution": ticket.resolution,
            "work_performed": ticket.work_performed,
            "resolution_category": ticket.resolution_category,
            "closure_reason": ticket.closure_reason,
            "reason": clean_reason,
            "source": source,
        },
    )
    _notify_status(db, ticket, previous=current, actor=actor, reason=clean_reason)
    _sync_side_effects(db, ticket, actor)
    return ticket


def _apply_sla_from(ticket: Ticket, db: Session, start: datetime) -> None:
    policy = sla_policy_for(db, ticket.category, ticket.priority)
    ticket.sla_due_at = (
        start + timedelta(hours=policy.resolution_hours)
        if policy is not None and policy.resolution_hours
        else None
    )


def _notify_status(
    db: Session, ticket: Ticket, *, previous: str, actor: User | None, reason: str | None
) -> None:
    label = T.STATUS_LABELS.get(ticket.status, ticket.status)
    stamp = _uid()
    people = {ticket.requester_id, ticket.affected_user_id}
    if ticket.status == T.PENDING_REQUESTER:
        notify(
            db,
            ticket,
            event_key=f"info_requested:{stamp}",
            user_ids=[ticket.requester_id],
            notification_type=NotificationType.ticket_status_changed,
            title=f"{ticket.ticket_number}: more information needed",
            message=reason or "The team needs more information to continue.",
            exclude=actor.id if actor else None,
        )
        return
    if ticket.status in {T.RESOLVED, T.CLOSED, T.CANCELLED} or (
        previous in T.TERMINAL_STATUSES and ticket.status in _WORKING
    ):
        recipients = set(people)
        if ticket.status not in {T.RESOLVED, T.CLOSED} and ticket.assignee_id:
            recipients.add(ticket.assignee_id)
        if previous in T.TERMINAL_STATUSES and ticket.assignee_id:
            recipients.add(ticket.assignee_id)
        detail = ticket.resolution if ticket.status == T.RESOLVED else reason
        notify(
            db,
            ticket,
            event_key=f"status:{ticket.status}:{stamp}",
            user_ids=recipients,
            notification_type=NotificationType.ticket_status_changed,
            title=f"{ticket.ticket_number} {label.lower()}",
            message=f"{ticket.title}" + (f" · {detail}" if detail else ""),
            exclude=actor.id if actor else None,
        )


def _sync_side_effects(db: Session, ticket: Ticket, actor: User | None) -> None:
    from app.services import onboarding_task_service as onboarding_tasks

    onboarding_tasks.sync_from_ticket(db, ticket, actor=actor)
    if ticket.status == T.CANCELLED:
        from app.services import it_stock_service

        it_stock_service.release_for_ticket(
            db, ticket.id, actor=actor, reason=f"Request {ticket.ticket_number} was cancelled"
        )


# --- Comments -------------------------------------------------------------
def add_comment(
    db: Session,
    ticket: Ticket,
    *,
    actor: User,
    body: str,
    is_internal: bool,
    is_agent: bool,
) -> TicketComment:
    text = (body or "").strip()
    if not text:
        raise ProTrackValidationError("Comment cannot be empty.")
    internal = bool(is_internal) and is_agent
    comment = TicketComment(
        ticket_id=ticket.id, author_id=actor.id, body=text, is_internal=internal
    )
    db.add(comment)
    now = _now()
    ticket.last_activity_at = now
    if is_agent and not internal and actor.id != ticket.requester_id and ticket.first_response_at is None:
        ticket.first_response_at = now
    db.flush()
    _log(
        db,
        ticket,
        actor=actor,
        action=ActivityAction.ticket_commented,
        new={"internal": internal},
    )
    stamp = _uid()
    if actor.id == ticket.requester_id and ticket.status == T.PENDING_REQUESTER:
        transition(
            db,
            ticket,
            to_status=T.IN_PROGRESS if ticket.assignee_id else T.OPEN,
            actor=actor,
            source="info_received",
        )
        notify(
            db,
            ticket,
            event_key=f"info_received:{stamp}",
            user_ids=[ticket.assignee_id],
            notification_type=NotificationType.ticket_comment,
            title=f"{ticket.ticket_number}: requester replied",
            message=text[:300],
            exclude=actor.id,
        )
    elif not internal:
        recipients = {ticket.requester_id, ticket.assignee_id}
        notify(
            db,
            ticket,
            event_key=f"comment:{comment.id}",
            user_ids=recipients,
            notification_type=NotificationType.ticket_comment,
            title=f"New comment on {ticket.ticket_number}",
            message=text[:300],
            exclude=actor.id,
        )
    elif ticket.assignee_id:
        notify(
            db,
            ticket,
            event_key=f"comment:{comment.id}",
            user_ids=[ticket.assignee_id],
            notification_type=NotificationType.ticket_comment,
            title=f"Internal note on {ticket.ticket_number}",
            message=text[:300],
            exclude=actor.id,
        )
    return comment


# --- Field updates --------------------------------------------------------
def update_fields(db: Session, ticket: Ticket, *, actor: User, data: dict[str, Any]) -> Ticket:
    changed: dict[str, Any] = {}
    old: dict[str, Any] = {}
    for field in ("title", "description", "location", "due_date", "subcategory", "org_department_id"):
        if field in data and getattr(ticket, field) != data[field]:
            old[field] = str(getattr(ticket, field)) if getattr(ticket, field) is not None else None
            setattr(ticket, field, data[field])
            changed[field] = str(data[field]) if data[field] is not None else None
    if "priority" in data and data["priority"] is not None:
        priority = T.normalize_priority(data["priority"])
        if priority != T.normalize_priority(ticket.priority):
            old["priority"] = ticket.priority
            ticket.priority = priority
            changed["priority"] = priority
            if ticket.created_at is not None:
                _apply_sla_from(ticket, db, ticket.created_at)
    if "category" in data and data["category"] and data["category"] != ticket.category:
        raise ProTrackValidationError("Use Transfer to move a ticket to another queue.")
    if not changed:
        return ticket
    ticket.updated_by_id = actor.id
    ticket.last_activity_at = _now()
    db.flush()
    _log(db, ticket, actor=actor, action=ActivityAction.ticket_updated, old=old, new=changed)
    return ticket


# --- SLA sweep ------------------------------------------------------------
def _due_moment(ticket: Ticket) -> datetime | None:
    moments: list[datetime] = []
    if ticket.due_date is not None:
        moments.append(datetime.combine(ticket.due_date, datetime.max.time()).replace(microsecond=0))
    if ticket.sla_due_at is not None:
        moments.append(ticket.sla_due_at)
    return min(moments) if moments else None


def run_sla_sweep(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Due-soon, overdue and escalation alerts — each sent once per due moment."""
    moment = now or _now()
    ensure_default_sla_policies(db)
    counts = {"due_soon": 0, "overdue": 0, "escalated": 0}
    rows = db.scalars(select(Ticket).where(Ticket.status.in_(T.OPEN_STATUSES))).all()
    for ticket in rows:
        due = _due_moment(ticket)
        if due is None:
            continue
        policy = sla_policy_for(db, ticket.category, ticket.priority)
        due_soon_hours = policy.due_soon_hours if policy is not None else 24
        stamp = due.strftime("%Y%m%d%H%M")
        owners = [ticket.assignee_id] if ticket.assignee_id else list(admin_user_ids(db))
        if moment < due <= moment + timedelta(hours=due_soon_hours):
            counts["due_soon"] += notify(
                db,
                ticket,
                event_key=f"due_soon:{stamp}",
                user_ids=owners,
                notification_type=NotificationType.ticket_due_soon,
                title=f"{ticket.ticket_number} is due soon",
                message=f"{ticket.title} is due {due:%d %b %H:%M}.",
            )
        elif due < moment:
            counts["overdue"] += notify(
                db,
                ticket,
                event_key=f"overdue:{stamp}",
                user_ids=owners,
                notification_type=NotificationType.ticket_overdue,
                title=f"{ticket.ticket_number} is overdue",
                message=f"{ticket.title} was due {due:%d %b %H:%M}.",
            )
            escalate_after = policy.escalate_after_hours if policy is not None else None
            if escalate_after is not None and due + timedelta(hours=escalate_after) < moment:
                if ticket.escalation_level == 0:
                    decision = resolve_routing(
                        db,
                        category=ticket.category,
                        subcategory=ticket.subcategory,
                        source_module=ticket.source_module,
                    )
                    targets = (
                        {decision.escalation_user_id}
                        if decision.escalation_user_id
                        else admin_user_ids(db)
                    )
                    ticket.escalation_level = 1
                    ticket.escalated_at = moment
                    db.flush()
                    _log(
                        db,
                        ticket,
                        actor=None,
                        action=ActivityAction.ticket_escalated,
                        new={"level": 1, "due": due.isoformat(), "to": sorted(str(t) for t in targets)},
                    )
                    notify(
                        db,
                        ticket,
                        event_key=f"escalated:{stamp}",
                        user_ids=targets,
                        notification_type=NotificationType.ticket_escalated,
                        title=f"Escalation: {ticket.ticket_number} is overdue",
                        message=(
                            f"{ticket.title} — owner {_name(ticket.assignee)} — was due {due:%d %b %H:%M}."
                        ),
                    )
                    counts["escalated"] += 1
    db.flush()
    return counts
