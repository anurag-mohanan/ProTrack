"""Auto-assign milestone responsible engineers from project team roles."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Milestone, Project


def is_feasibility_milestone(name: str) -> bool:
    return "feasibility" in name.strip().lower()


def resolve_auto_assigned_user_id(project: Project, milestone_name: str) -> UUID | None:
    if is_feasibility_milestone(milestone_name):
        return project.surfacer_id
    return project.designer_id


def sync_milestone_assignments(db: Session, project_id: UUID) -> int:
    """Apply role-based assignments for milestones not manually overridden."""
    project = db.get(Project, project_id)
    if project is None:
        return 0

    milestones = list(
        db.scalars(select(Milestone).where(Milestone.project_id == project_id)).all()
    )
    updated = 0
    for row in milestones:
        if row.assignment_manual:
            continue
        target = resolve_auto_assigned_user_id(project, row.name)
        if row.assigned_user_id != target:
            row.assigned_user_id = target
            db.add(row)
            updated += 1

    if updated:
        db.commit()
    return updated
