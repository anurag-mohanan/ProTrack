"""Management actions: owned, dated follow-ups from reviews, objectives and initiatives.

Owners are notified through the existing notification service. Completion needs evidence; every
status change is appended to the history. People without organisation-wide review access see
only the actions they own.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EntityType, NotificationType
from app.models.management import (
    ACTION_CLOSED,
    ManagementAction,
    ManagementReview,
    StrategicInitiative,
    StrategicObjective,
)
from app.models.models import Project, User
from app.schemas.management import ActionCreate, ActionUpdate
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.events import list_events, record_event, user_name
from app.services.notification_service import create_notification

OWNER_FIELDS = {"status", "status_reason", "completion_evidence"}


def _notify(db: Session, action: ManagementAction, owner_id: UUID, actor: User) -> None:
    if owner_id == actor.id:
        return
    due = f" (due {action.due_date:%d %b %Y})" if action.due_date else ""
    create_notification(db, user_id=owner_id, notification_type=NotificationType.management_action_assigned,
                        title="Management action assigned to you", message=f"{action.title}{due}",
                        entity_type=EntityType.management_action, entity_id=action.id, send_email=False, commit=False)


def visible_statement(access: ManagementAccess):
    stmt = select(ManagementAction)
    if not access.reviews:
        stmt = stmt.where(ManagementAction.owner_id == access.user.id)
    return stmt


def get_action(db: Session, access: ManagementAccess, action_id: UUID) -> ManagementAction:
    row = db.scalar(visible_statement(access).where(ManagementAction.id == action_id))
    if row is None:
        raise LookupError("Action not found")
    return row


def _check(db: Session, *, owner_id=None, review_id=None, objective_id=None, initiative_id=None, project_id=None) -> None:
    for value, model, label in ((owner_id, User, "owner"), (review_id, ManagementReview, "review"),
                                (objective_id, StrategicObjective, "objective"),
                                (initiative_id, StrategicInitiative, "initiative"), (project_id, Project, "project")):
        if value is not None and db.get(model, value) is None:
            raise ValueError(f"Unknown {label}")


def serialize(db: Session, row: ManagementAction, today: date | None = None, *, detail: bool = False,
              access: ManagementAccess | None = None) -> dict:
    today = today or date.today()
    owner = db.get(User, row.owner_id) if row.owner_id else None
    review = db.get(ManagementReview, row.review_id) if row.review_id else None
    objective = db.get(StrategicObjective, row.objective_id) if row.objective_id else None
    initiative = db.get(StrategicInitiative, row.initiative_id) if row.initiative_id else None
    project = db.get(Project, row.project_id) if row.project_id else None
    out = {
        "id": str(row.id), "title": row.title, "description": row.description,
        "owner_id": str(row.owner_id) if row.owner_id else None, "owner": user_name(owner),
        "priority": row.priority, "due_date": row.due_date.isoformat() if row.due_date else None,
        "status": row.status,
        "overdue": bool(row.due_date and row.due_date < today and row.status not in ACTION_CLOSED),
        "completion_evidence": row.completion_evidence,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "review": {"id": str(review.id), "title": review.title} if review else None,
        "objective": {"id": str(objective.id), "title": objective.title} if objective else None,
        "initiative": {"id": str(initiative.id), "name": initiative.name} if initiative else None,
        "project": {"id": str(project.id), "code": project.code} if project else None,
        "from_decision": row.decision_event_id is not None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if access is not None:
        out["can_edit"] = access.manage or row.owner_id == access.user.id
    if detail:
        out["events"] = list_events(db, "action", row.id)
    return out


def list_actions(db: Session, access: ManagementAccess, *, status: str | None = None, mine: bool = False,
                 review_id: UUID | None = None, objective_id: UUID | None = None, open_only: bool = False,
                 today: date | None = None) -> list[dict]:
    today = today or date.today()
    stmt = visible_statement(access)
    if status:
        stmt = stmt.where(ManagementAction.status == status)
    if open_only:
        stmt = stmt.where(ManagementAction.status.notin_(ACTION_CLOSED))
    if mine:
        stmt = stmt.where(ManagementAction.owner_id == access.user.id)
    if review_id:
        stmt = stmt.where(ManagementAction.review_id == review_id)
    if objective_id:
        stmt = stmt.where(ManagementAction.objective_id == objective_id)
    rows = db.scalars(stmt.order_by(ManagementAction.due_date.is_(None), ManagementAction.due_date,
                                    ManagementAction.created_at)).all()
    return [serialize(db, r, today, access=access) for r in rows]


def create_action(db: Session, access: ManagementAccess, body: ActionCreate, *, decision_event_id: UUID | None = None,
                  review_id: UUID | None = None) -> ManagementAction:
    if not access.manage:
        raise ManagementForbidden("Creating management actions needs the Manage strategy permission.")
    review_id = review_id or body.review_id
    _check(db, owner_id=body.owner_id, review_id=review_id, objective_id=body.objective_id,
           initiative_id=body.initiative_id, project_id=body.project_id)
    row = ManagementAction(
        title=body.title, description=body.description, review_id=review_id, objective_id=body.objective_id,
        initiative_id=body.initiative_id, project_id=body.project_id, decision_event_id=decision_event_id,
        owner_id=body.owner_id, priority=body.priority, due_date=body.due_date, status="open",
        created_by_id=access.user.id,
    )
    db.add(row)
    db.flush()
    record_event(db, entity_type="action", entity_id=row.id, event_type="created", summary="Action created",
                 actor=access.user, new={"title": row.title, "owner_id": str(row.owner_id), "due_date": row.due_date})
    _notify(db, row, body.owner_id, access.user)
    return row


def update_action(db: Session, access: ManagementAccess, row: ManagementAction, body: ActionUpdate) -> None:
    owner = row.owner_id == access.user.id
    if not (access.manage or owner):
        raise ManagementForbidden("Only the owner or a strategy manager can change this action.")
    data = body.model_dump(exclude_unset=True)
    if not access.manage and set(data) - OWNER_FIELDS:
        raise ManagementForbidden("The owner can update status and completion evidence only.")
    _check(db, owner_id=data.get("owner_id"))
    old, new = {}, {}
    for name in ("title", "description", "priority", "due_date", "completion_evidence"):
        if name in data and getattr(row, name) != data[name]:
            old[name], new[name] = getattr(row, name), data[name]
            setattr(row, name, data[name])
    reassigned = "owner_id" in data and data["owner_id"] is not None and data["owner_id"] != row.owner_id
    if reassigned:
        old["owner_id"], new["owner_id"] = row.owner_id, data["owner_id"]
        row.owner_id = data["owner_id"]
    if old or new:
        record_event(db, entity_type="action", entity_id=row.id, event_type="updated", summary="Action updated",
                     actor=access.user, old=old, new=new)
    if reassigned:
        _notify(db, row, row.owner_id, access.user)
    status = data.get("status")
    if status and status != row.status:
        reason = data.get("status_reason")
        if status in {"blocked", "cancelled"} and not reason:
            raise ValueError("Give a reason for this status")
        if status == "completed" and not (row.completion_evidence or "").strip():
            raise ValueError("Completing an action needs completion evidence")
        if row.status in ACTION_CLOSED and not access.manage:
            raise ManagementForbidden("Reopening a closed action needs the Manage strategy permission.")
        record_event(db, entity_type="action", entity_id=row.id,
                     event_type="completed" if status == "completed" else "status_changed",
                     summary=f"Status {row.status} -> {status}", actor=access.user, old=row.status, new=status,
                     reason=reason, body=row.completion_evidence if status == "completed" else None)
        row.status = status
        if status == "completed":
            row.completed_at, row.completed_by_id = datetime.utcnow(), access.user.id
        elif status not in ACTION_CLOSED:
            row.completed_at = row.completed_by_id = None


def outstanding_summary(db: Session, access: ManagementAccess, today: date | None = None) -> dict:
    today = today or date.today()
    rows = db.scalars(visible_statement(access).where(ManagementAction.status.notin_(ACTION_CLOSED))).all()
    return {
        "open": len(rows),
        "overdue": sum(1 for r in rows if r.due_date and r.due_date < today),
        "blocked": sum(1 for r in rows if r.status == "blocked"),
        "due_next_14_days": sum(1 for r in rows if r.due_date and today <= r.due_date <= today + timedelta(days=14)),
    }


def owner_or_manager(access: ManagementAccess, owner_id) -> bool:
    return access.manage or owner_id == access.user.id
