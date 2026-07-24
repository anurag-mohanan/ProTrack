"""Soft project stage / completion gates (R2 operational control)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectStage
from app.models.models import Milestone, Project, ProjectTemplateMilestone


_DONE_STATUSES = frozenset(
    {
        MilestoneStatus.completed,
        MilestoneStatus.not_applicable,
        MilestoneStatus.cancelled,
    }
)


def _status_done(status: object) -> bool:
    if status in _DONE_STATUSES:
        return True
    status_val = status.value if hasattr(status, "value") else str(status)
    return status_val in {"completed", "not_applicable", "na", "n_a", "cancelled"}


def required_milestone_names(db: Session, project: Project) -> set[str] | None:
    """Names marked required on the project template.

    Returns None when no template is linked — callers treat all milestones as required.
    """
    if project.project_template_id is None:
        return None
    rows = db.scalars(
        select(ProjectTemplateMilestone).where(
            ProjectTemplateMilestone.project_template_id == project.project_template_id,
            ProjectTemplateMilestone.is_required.is_(True),
        )
    ).all()
    return {row.milestone_name for row in rows}


def incomplete_required_milestones(db: Session, project_id: UUID) -> list[Milestone]:
    project = db.get(Project, project_id)
    if project is None:
        return []

    required_names = required_milestone_names(db, project)
    rows = db.scalars(select(Milestone).where(Milestone.project_id == project_id)).all()
    incomplete: list[Milestone] = []
    for row in rows:
        if required_names is not None and row.name not in required_names:
            continue
        if _status_done(row.status):
            continue
        incomplete.append(row)
    return incomplete


def assert_stage_gate(
    db: Session,
    project: Project,
    *,
    next_execution_status: ExecutionStatus | str | None = None,
    next_project_stage: ProjectStage | str | None = None,
) -> None:
    """Block complete/final when required milestones remain open."""
    exec_raw = next_execution_status
    if hasattr(exec_raw, "value"):
        exec_raw = exec_raw.value  # type: ignore[union-attr]
    stage_raw = next_project_stage
    if hasattr(stage_raw, "value"):
        stage_raw = stage_raw.value  # type: ignore[union-attr]

    needs_gate = exec_raw == ExecutionStatus.completed.value or stage_raw == ProjectStage.final.value
    if not needs_gate:
        return

    open_rows = incomplete_required_milestones(db, project.id)
    if not open_rows:
        return
    names = ", ".join(row.name for row in open_rows[:5])
    extra = f" (+{len(open_rows) - 5} more)" if len(open_rows) > 5 else ""
    raise ProTrackValidationError(
        "Cannot mark project complete/final until required milestones are done: "
        f"{names}{extra}."
    )


def project_setup_gaps(project: Project) -> list[str]:
    """Fields still needed after quote→project shell create (handoff checklist)."""
    gaps: list[str] = []
    if project.project_type_id is None:
        gaps.append("project_type")
    if project.team_id is None:
        gaps.append("team")
    if project.design_leader_id is None:
        gaps.append("design_leader")
    if project.due_date is None:
        gaps.append("due_date")
    if project.project_template_id is None:
        gaps.append("template")
    return gaps


def project_needs_setup(project: Project) -> bool:
    gaps = project_setup_gaps(project)
    if not gaps:
        return False
    status = project.execution_status
    status_val = status.value if hasattr(status, "value") else str(status)
    # Shells / early lifecycle only — don't flag completed or cancelled work.
    return status_val in {
        ExecutionStatus.planning.value,
        "planning",
    }
