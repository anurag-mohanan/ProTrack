"""Append-only management history (comments, decisions, changes, approvals) plus the system audit log."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.management import EVENT_ENTITY_TYPES, ManagementEvent
from app.models.models import User
from app.services.activity_service import log_activity

_AUDIT = {
    "objective": (EntityType.strategic_objective, ActivityAction.strategy_objective_changed),
    "initiative": (EntityType.strategic_initiative, ActivityAction.strategy_initiative_changed),
    "review": (EntityType.management_review, ActivityAction.management_review_changed),
    "action": (EntityType.management_action, ActivityAction.management_action_changed),
}
_TARGET_EVENTS = {"target_changed", "baseline_changed", "target_approved"}


def _dump(value) -> str | None:
    return None if value is None else json.dumps(value, default=str)


def record_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    event_type: str,
    summary: str,
    actor: User | None,
    old=None,
    new=None,
    reason: str | None = None,
    body: str | None = None,
    approved_by: User | None = None,
) -> ManagementEvent:
    if entity_type not in EVENT_ENTITY_TYPES:
        raise ValueError(f"Unknown entity type {entity_type}")
    event = ManagementEvent(
        entity_type=entity_type, entity_id=entity_id, event_type=event_type, summary=summary[:500], body=body,
        old_value_json=_dump(old), new_value_json=_dump(new), reason=reason,
        actor_id=actor.id if actor else None, approved_by_id=approved_by.id if approved_by else None,
    )
    db.add(event)
    db.flush()
    if event_type not in {"comment"}:
        audit_entity, action = _AUDIT[entity_type]
        if entity_type == "objective" and event_type in _TARGET_EVENTS:
            action = ActivityAction.strategy_target_changed
        log_activity(db, user=actor, entity_type=audit_entity, entity_id=entity_id, action=action,
                     old_value=old, new_value={"event": event_type, "summary": summary, "value": new},
                     outcome="success", module="management", commit=False)
    return event


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def serialize_event(event: ManagementEvent, users: dict[UUID, User]) -> dict:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "summary": event.summary,
        "body": event.body,
        "old_value": json.loads(event.old_value_json) if event.old_value_json else None,
        "new_value": json.loads(event.new_value_json) if event.new_value_json else None,
        "reason": event.reason,
        "actor": _name(users.get(event.actor_id)),
        "approved_by": _name(users.get(event.approved_by_id)),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def list_events(db: Session, entity_type: str, entity_id: UUID, *, event_types: set[str] | None = None) -> list[dict]:
    stmt = select(ManagementEvent).where(ManagementEvent.entity_type == entity_type,
                                         ManagementEvent.entity_id == entity_id)
    if event_types:
        stmt = stmt.where(ManagementEvent.event_type.in_(event_types))
    events = list(db.scalars(stmt.order_by(ManagementEvent.created_at.desc())).all())
    ids = {e.actor_id for e in events} | {e.approved_by_id for e in events}
    ids.discard(None)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [serialize_event(e, users) for e in events]


def user_name(user: User | None) -> str | None:
    return _name(user)
