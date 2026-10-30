"""Workflow automation engine (phase 110).

Rules are defined in code (``rules.py``). The ``automation_rules`` table only
stores the on/off switch and last-run state, and every rule is **off until an
administrator enables it**. Each evaluation of a rule for one target is one
``AutomationExecution`` row:

* ``dedupe_key`` is unique, so a repeated event, a re-run sweep or two workers
  racing never act twice on the same condition.
* The execution row is written before the action runs (claiming the key), and the
  action runs in a savepoint, so a failing action leaves no partial changes and is
  recorded as ``failed`` with its error. Failed executions are retried only on an
  explicit request; a retry reuses the same row and increments ``attempts``.
* Actions are limited to in-app notifications and recommendations. Rules never
  change workflow status, approve, pay, assign or complete anything;
  consequential outcomes are recorded as ``pending_review`` for a person.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType, NotificationType
from app.models.models import User
from app.models.workflow import (
    EXEC_DISMISSED,
    EXEC_FAILED,
    EXEC_PENDING_REVIEW,
    EXEC_SKIPPED,
    EXEC_SUCCEEDED,
    AutomationExecution,
    AutomationRule,
)
from app.services.activity_service import log_activity

logger = logging.getLogger("protrack.automation")

KIND_EVENT = "event"
KIND_SWEEP = "sweep"
KIND_EXTERNAL = "external"


@dataclass
class ActionResult:
    status: str  # succeeded | skipped | pending_review
    summary: str
    data: dict = field(default_factory=dict)


@dataclass
class Candidate:
    dedupe_key: str
    target_type: str
    target_id: UUID | None
    project_id: UUID | None
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RuleDefinition:
    key: str
    name: str
    module: str
    kind: str
    trigger: str
    description: str
    conditions: str
    action: str
    recipients: str
    authorization: str
    consequential: bool = False
    runs_where: str | None = None
    perform: Callable[[Session, dict], ActionResult] | None = None
    candidates: Callable[[Session, date], Iterable[Candidate]] | None = None

    @property
    def executable(self) -> bool:
        return self.kind != KIND_EXTERNAL and self.perform is not None


REGISTRY: dict[str, RuleDefinition] = {}


def register(definition: RuleDefinition) -> RuleDefinition:
    REGISTRY[definition.key] = definition
    return definition


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_rule(key: str) -> RuleDefinition:
    from app.services.automation import rules  # noqa: F401 - populates the registry

    definition = REGISTRY.get(key)
    if definition is None:
        raise KeyError(key)
    return definition


def all_rules() -> list[RuleDefinition]:
    from app.services.automation import rules  # noqa: F401 - populates the registry

    return list(REGISTRY.values())


def rule_row(db: Session, key: str) -> AutomationRule | None:
    return db.scalar(select(AutomationRule).where(AutomationRule.rule_key == key))


def is_enabled(db: Session, key: str) -> bool:
    row = rule_row(db, key)
    return bool(row and row.is_enabled)


def set_enabled(db: Session, key: str, enabled: bool, *, actor: User, reason: str | None = None) -> AutomationRule:
    definition = get_rule(key)
    if not definition.executable:
        raise ValueError(f"'{definition.name}' is managed by {definition.runs_where} and cannot be switched here.")
    row = rule_row(db, key)
    previous = bool(row and row.is_enabled)
    if row is None:
        row = AutomationRule(rule_key=key, is_enabled=enabled)
        db.add(row)
    row.is_enabled = enabled
    row.updated_by_id = actor.id
    db.flush()
    if previous != enabled:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.settings,
            entity_id=row.id,
            action=ActivityAction.automation_rule_changed,
            old_value=f"{key}: {'enabled' if previous else 'disabled'}",
            new_value=f"{key}: {'enabled' if enabled else 'disabled'}" + (f" — {reason}" if reason else ""),
            module="automation",
            commit=False,
        )
    db.commit()
    db.refresh(row)
    return row


def _touch_rule(db: Session, key: str, status: str, error: str | None) -> None:
    row = rule_row(db, key)
    if row is None:
        row = AutomationRule(rule_key=key, is_enabled=False)
        db.add(row)
    row.last_run_at = _now()
    row.last_status = status
    row.last_error = error


def _run_action(db: Session, definition: RuleDefinition, row: AutomationExecution, context: dict) -> None:
    try:
        with db.begin_nested():
            result = definition.perform(db, context)  # type: ignore[misc]
        row.status = result.status
        row.summary = result.summary
        row.result_json = json.dumps({"context": context, "result": result.data}, default=str)
        row.error_message = None
    except Exception as exc:  # noqa: BLE001 - recorded on the execution row
        logger.warning("Automation rule %s failed for %s: %s", definition.key, row.dedupe_key, exc)
        row.status = EXEC_FAILED
        row.summary = f"{definition.name} failed"
        row.result_json = json.dumps({"context": context}, default=str)
        row.error_message = f"{type(exc).__name__}: {exc}"[:2000]
    row.finished_at = _now()
    _touch_rule(db, definition.key, row.status, row.error_message)


def execute(
    db: Session,
    definition: RuleDefinition,
    candidate: Candidate,
    *,
    trigger_event: str,
    actor: User | None = None,
) -> AutomationExecution | None:
    """Run one rule for one target once. Returns the execution (new or existing)."""
    if not definition.executable or not is_enabled(db, definition.key):
        return None
    existing = db.scalar(select(AutomationExecution).where(AutomationExecution.dedupe_key == candidate.dedupe_key))
    if existing is not None:
        return existing
    row = AutomationExecution(
        rule_key=definition.key,
        dedupe_key=candidate.dedupe_key,
        trigger_event=trigger_event,
        actor_type="user" if actor is not None else "system",
        actor_id=actor.id if actor is not None else None,
        target_type=candidate.target_type,
        target_id=candidate.target_id,
        project_id=candidate.project_id,
        status=EXEC_FAILED,
        attempts=1,
        started_at=_now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return db.scalar(select(AutomationExecution).where(AutomationExecution.dedupe_key == candidate.dedupe_key))
    _run_action(db, definition, row, candidate.context)
    db.commit()
    return row


def retry(db: Session, execution: AutomationExecution, *, actor: User) -> AutomationExecution:
    if execution.status != EXEC_FAILED:
        raise ValueError("Only failed executions can be retried.")
    definition = get_rule(execution.rule_key)
    try:
        context = json.loads(execution.result_json or "{}").get("context") or {}
    except ValueError:
        context = {}
    execution.attempts = int(execution.attempts or 0) + 1
    execution.started_at = _now()
    execution.review_note = f"Retried by {actor.email}"
    _run_action(db, definition, execution, context)
    db.commit()
    db.refresh(execution)
    return execution


def review(db: Session, execution: AutomationExecution, *, actor: User, decision: str, note: str | None) -> AutomationExecution:
    """Close a recommendation. Acknowledging records the decision; it does not act."""
    if execution.status != EXEC_PENDING_REVIEW:
        raise ValueError("Only recommendations awaiting review can be reviewed.")
    if decision not in {"acknowledge", "dismiss"}:
        raise ValueError("Decision must be acknowledge or dismiss.")
    execution.status = EXEC_SUCCEEDED if decision == "acknowledge" else EXEC_DISMISSED
    execution.reviewed_by_id = actor.id
    execution.reviewed_at = _now()
    execution.review_note = (note or "").strip() or None
    db.commit()
    db.refresh(execution)
    return execution


def emit(db: Session, event: str, candidates_by_rule: dict[str, list[Candidate]], *, actor: User | None = None) -> list[AutomationExecution]:
    """Dispatch an application event to the enabled rules listening for it."""
    done: list[AutomationExecution] = []
    for key, candidates in candidates_by_rule.items():
        definition = get_rule(key)
        if definition.trigger != event:
            continue
        for candidate in candidates:
            row = execute(db, definition, candidate, trigger_event=event, actor=actor)
            if row is not None:
                done.append(row)
    return done


def run_sweeps(db: Session, *, today: date | None = None, rule_keys: list[str] | None = None) -> dict[str, dict[str, int]]:
    """Evaluate every enabled sweep rule. Safe to run repeatedly."""
    today = today or date.today()
    summary: dict[str, dict[str, int]] = {}
    for definition in all_rules():
        if definition.kind != KIND_SWEEP or definition.candidates is None:
            continue
        if rule_keys is not None and definition.key not in rule_keys:
            continue
        if not is_enabled(db, definition.key):
            continue
        counts = {"evaluated": 0, "new": 0, "deduplicated": 0, "failed": 0}
        try:
            candidates = list(definition.candidates(db, today))
        except Exception as exc:  # noqa: BLE001 - recorded as the rule's last error
            db.rollback()
            _touch_rule(db, definition.key, EXEC_FAILED, f"{type(exc).__name__}: {exc}"[:2000])
            db.commit()
            counts["failed"] += 1
            summary[definition.key] = counts
            continue
        for candidate in candidates:
            counts["evaluated"] += 1
            before = db.scalar(
                select(AutomationExecution.id).where(AutomationExecution.dedupe_key == candidate.dedupe_key)
            )
            row = execute(db, definition, candidate, trigger_event="sweep")
            if before is not None:
                counts["deduplicated"] += 1
            elif row is not None:
                counts["new"] += 1
                if row.status == EXEC_FAILED:
                    counts["failed"] += 1
        if not candidates:
            _touch_rule(db, definition.key, EXEC_SKIPPED, None)
            db.commit()
        summary[definition.key] = counts
    return summary


def notify(db: Session, user_ids: Iterable[UUID | None], *, title: str, message: str,
           entity_type: EntityType, entity_id: UUID) -> list[str]:
    """In-app notification through the existing service; never sends email."""
    from app.services.notification_service import create_notification

    sent: list[str] = []
    for user_id in dict.fromkeys(u for u in user_ids if u):
        user = db.get(User, user_id)
        if user is None or not user.is_active or user.is_deleted:
            continue
        note = create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.workflow_automation,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            send_email=False,
            commit=False,
        )
        if note is not None:
            sent.append(str(user_id))
    return sent
