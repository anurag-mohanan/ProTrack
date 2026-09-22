"""Authoritative project stage / completion sync from milestone progress.

Milestone completion drives Project.project_stage. All required milestones closed
drives Project.execution_status = completed and project_stage = completed.
Timesheet entries on completed projects do not reopen the project.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectStage
from app.models.models import Milestone, Project, ProjectStageHistory, User
from app.services.activity_service import log_activity
from app.models.enums import ActivityAction, EntityType


STAGE_RANK: dict[ProjectStage, int] = {
    ProjectStage.feasibility: 0,
    ProjectStage.preliminary: 1,
    ProjectStage.intermediate: 2,
    ProjectStage.final: 3,
    ProjectStage.completed: 4,
}

_DONE_STATUSES = frozenset(
    {
        MilestoneStatus.completed,
        MilestoneStatus.not_applicable,
        MilestoneStatus.cancelled,
    }
)

TRIGGER_MILESTONE_COMPLETION = "milestone_completion"
TRIGGER_MILESTONE_REOPEN = "milestone_reopen"
TRIGGER_MANUAL_OVERRIDE = "manual_override"
TRIGGER_SYSTEM_SYNC = "system_sync"


def _status_done(status: object) -> bool:
    if status in _DONE_STATUSES:
        return True
    status_val = status.value if hasattr(status, "value") else str(status)
    return status_val in {"completed", "not_applicable", "na", "n_a", "cancelled"}


def _stage_value(stage: ProjectStage | str | None) -> str | None:
    if stage is None:
        return None
    return stage.value if hasattr(stage, "value") else str(stage)


def _as_stage(value: object | None) -> ProjectStage | None:
    if value is None:
        return None
    if isinstance(value, ProjectStage):
        return value
    raw = value.value if hasattr(value, "value") else str(value)
    try:
        return ProjectStage(raw)
    except ValueError:
        return None


def required_milestones(db: Session, project: Project) -> list[Milestone]:
    """Required milestones for completion, ordered by sort_order."""
    rows = list(
        db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project.id)
            .order_by(Milestone.sort_order.asc(), Milestone.name.asc())
        ).all()
    )
    required = [row for row in rows if bool(getattr(row, "is_required", True))]
    if required:
        return required
    # No flags set — treat all as required (legacy projects).
    return rows


def evaluate_project_completion(db: Session, project_id: UUID) -> bool:
    project = db.get(Project, project_id)
    if project is None:
        return False
    required = required_milestones(db, project)
    if not required:
        return False
    return all(_status_done(row.status) for row in required)


def calculate_project_stage(db: Session, project_id: UUID) -> ProjectStage:
    """Highest contiguous stage whose earlier required milestones are closed.

    Unmapped milestones (e.g. File Release / BOM Release) are checkpoints that
    do not advance stage by themselves; when all required are closed → completed.
    """
    project = db.get(Project, project_id)
    if project is None:
        return ProjectStage.preliminary

    required = required_milestones(db, project)
    if not required:
        return _as_stage(project.project_stage) or ProjectStage.preliminary

    if all(_status_done(row.status) for row in required):
        return ProjectStage.completed

    current = ProjectStage.feasibility
    # Walk in order; stop at first incomplete required. Stage is the last mapped
    # stage among completed required milestones before that stop.
    for row in required:
        if not _status_done(row.status):
            break
        mapped = _as_stage(getattr(row, "project_stage", None))
        if mapped is not None and mapped != ProjectStage.completed:
            if STAGE_RANK[mapped] >= STAGE_RANK[current]:
                current = mapped
    return current


def _record_stage_history(
    db: Session,
    *,
    project: Project,
    previous_stage: str | None,
    new_stage: str,
    trigger: str,
    actor: User | None,
    related_milestone: Milestone | None,
    reason: str | None,
) -> None:
    db.add(
        ProjectStageHistory(
            project_id=project.id,
            previous_stage=previous_stage,
            new_stage=new_stage,
            changed_at=datetime.now(timezone.utc),
            trigger=trigger,
            triggered_by_user_id=actor.id if actor is not None else None,
            related_milestone_id=related_milestone.id if related_milestone is not None else None,
            reason=reason,
        )
    )


def sync_project_stage_from_milestones(
    db: Session,
    project: Project,
    *,
    actor: User | None = None,
    trigger: str = TRIGGER_SYSTEM_SYNC,
    related_milestone: Milestone | None = None,
    reason: str | None = None,
) -> dict:
    """Recalculate and apply project stage / completion. Returns change summary."""
    if project.execution_status == ExecutionStatus.cancelled:
        return {
            "changed": False,
            "stage_before": _stage_value(project.project_stage),
            "stage_after": _stage_value(project.project_stage),
            "project_completed": False,
            "skipped": "cancelled",
        }

    stage_before = _as_stage(project.project_stage) or ProjectStage.preliminary
    status_before = project.execution_status
    derived_stage = calculate_project_stage(db, project.id)
    all_required_done = evaluate_project_completion(db, project.id)

    stage_after = derived_stage
    status_after = status_before
    completed_now = False

    if all_required_done:
        stage_after = ProjectStage.completed
        if status_before != ExecutionStatus.completed:
            status_after = ExecutionStatus.completed
            completed_now = True
            if project.completed_at is None:
                project.completed_at = datetime.now(timezone.utc)
    else:
        # Required milestone reopened while project was completed.
        if status_before == ExecutionStatus.completed:
            status_after = ExecutionStatus.currently_being_worked_on
            # Preserve original completed_at for history; do not clear.
            if trigger == TRIGGER_SYSTEM_SYNC:
                trigger = TRIGGER_MILESTONE_REOPEN

    changed = False
    if stage_after != stage_before:
        project.project_stage = stage_after
        changed = True
        _record_stage_history(
            db,
            project=project,
            previous_stage=_stage_value(stage_before),
            new_stage=_stage_value(stage_after) or stage_after.value,
            trigger=trigger,
            actor=actor,
            related_milestone=related_milestone,
            reason=reason
            or (
                f"Milestone '{related_milestone.name}' updated"
                if related_milestone is not None
                else "Milestone-driven stage sync"
            ),
        )
    if status_after != status_before:
        project.execution_status = status_after
        changed = True

    if changed:
        db.add(project)
        if actor is not None:
            log_activity(
                db,
                user=actor,
                entity_type=EntityType.project,
                entity_id=project.id,
                action=ActivityAction.project_updated,
                old_value=f"stage={_stage_value(stage_before)};status={status_before.value if hasattr(status_before, 'value') else status_before}",
                new_value=f"stage={_stage_value(stage_after)};status={status_after.value if hasattr(status_after, 'value') else status_after}",
                commit=False,
            )

    return {
        "changed": changed,
        "stage_before": _stage_value(stage_before),
        "stage_after": _stage_value(stage_after),
        "status_before": status_before.value if hasattr(status_before, "value") else str(status_before),
        "status_after": status_after.value if hasattr(status_after, "value") else str(status_after),
        "project_completed": all_required_done,
        "completed_now": completed_now,
    }


def record_manual_stage_override(
    db: Session,
    project: Project,
    *,
    previous_stage: ProjectStage | str | None,
    new_stage: ProjectStage | str,
    actor: User | None,
    reason: str | None = None,
) -> None:
    _record_stage_history(
        db,
        project=project,
        previous_stage=_stage_value(previous_stage),
        new_stage=_stage_value(new_stage) or str(new_stage),
        trigger=TRIGGER_MANUAL_OVERRIDE,
        actor=actor,
        related_milestone=None,
        reason=reason or "Manual project stage override",
    )
