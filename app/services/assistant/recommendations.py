"""Recommendation decisions. A decision records who decided; it never performs the suggested action."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import is_admin
from app.models.assistant import (
    REC_ACCEPTED,
    REC_COMPLETED,
    REC_DEFERRED,
    REC_NEW,
    REC_REJECTED,
    AIRecommendation,
)
from app.models.enums import ActivityAction, EntityType
from app.models.models import Project, User
from app.services.activity_service import log_activity

TRANSITIONS: dict[str, set[str]] = {
    REC_NEW: {REC_ACCEPTED, REC_REJECTED, REC_DEFERRED},
    REC_DEFERRED: {REC_ACCEPTED, REC_REJECTED},
    REC_ACCEPTED: {REC_COMPLETED, REC_DEFERRED},
    REC_REJECTED: set(),
    REC_COMPLETED: set(),
}

WORKFLOW_ROUTES = {"finance": "/finance", "resources": "/resource-planning", "management": "/analytics"}


class RecommendationError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def visible_stmt(db: Session, user: User):
    stmt = select(AIRecommendation)
    if not is_admin(db, user):
        stmt = stmt.where(AIRecommendation.created_by_id == user.id)
    return stmt


def get_visible(db: Session, user: User, rec_id) -> AIRecommendation:
    row = db.scalar(visible_stmt(db, user).where(AIRecommendation.id == rec_id))
    if row is None:
        raise RecommendationError("Recommendation not found.", 404)
    return row


def workflow_route(row: AIRecommendation) -> str | None:
    """Where the user would act on an accepted recommendation, using existing screens."""
    if row.category == "skills":
        return "/skills"
    if row.module == "projects" and row.project_id:
        return f"/projects/{row.project_id}"
    return WORKFLOW_ROUTES.get(row.module)


def decide(db: Session, user: User, row: AIRecommendation, *, status: str, note: str | None,
           feedback: str | None) -> AIRecommendation:
    if row.created_by_id != user.id and not is_admin(db, user):
        raise RecommendationError("Only the person who received the recommendation or an administrator can decide it.", 403)
    if status not in TRANSITIONS.get(row.status, set()):
        raise RecommendationError(f"A {row.status} recommendation cannot be marked {status}.", 409)
    previous = row.status
    now = datetime.utcnow()
    row.status = status
    if status == REC_COMPLETED:
        row.completed_by_id, row.completed_at = user.id, now
    else:
        row.decided_by_id, row.decided_at = user.id, now
    if note:
        row.resolution_notes = note
    if feedback:
        row.feedback = feedback
    project = db.get(Project, row.project_id) if row.project_id else None
    log_activity(
        db, user=user, entity_type=EntityType.ai_recommendation, entity_id=row.id,
        action=ActivityAction.ai_recommendation_decided, old_value=previous,
        new_value=json.dumps({"status": status, "title": row.title, "category": row.category,
                              "project": (project.code or project.tool_number) if project else None,
                              "note": note}, default=str),
        outcome="success", module="assistant", commit=False,
    )
    db.commit()
    db.refresh(row)
    return row
