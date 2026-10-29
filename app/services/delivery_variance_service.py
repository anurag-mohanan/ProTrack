"""Delivery variance — original baseline, current target and actual completion dates.

Shared by the project engineering metrics and the Engineering Performance report.

Original approved baseline (never replaced by a later revision):

* Project: the earliest ``ProjectBaselineRevision``. Revision 1 written by
  ``apply_baseline`` has no previous dates, so its new completion date is the
  original baseline. If the earliest recorded revision already has previous dates,
  a baseline existed before revision history and that previous date is reported as
  ``baseline_unverified``.
* Milestone: the first revision snapshot (``previous_milestones_json``) holding a
  baseline finish date for the milestone; otherwise its current baseline finish
  date, because it has not been re-baselined since it received one.
* With no revision history at all, a stored baseline is ``baseline_unverified``.
* With no baseline, the current due date is used and labelled as such; the
  original commitment is then unknown. Project due-date changes are not versioned.

Current target: the due date (the date the existing overdue checks use), else the
current baseline. Completed work is classified early / on time / late against the
reference and is never overdue; incomplete work is overdue only after its current
target date has passed. Dates are compared as stored calendar dates (milestone
``completed_date``, else ``completed_at``'s date; project ``completed_at``'s date),
the same convention as the Engineering Performance report and stage plan.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    PLANNED_STAGE_LABELS,
    ExecutionStatus,
    MilestoneStatus,
    ProjectStage,
)
from app.models.models import Milestone, Project, ProjectBaselineRevision
from app.schemas.engineering_metrics import (
    DeliveryMetrics,
    MilestoneDelivery,
    ProjectDelivery,
)

_SKIPPED_MILESTONES = {MilestoneStatus.cancelled, MilestoneStatus.not_applicable}

SIGN_CONVENTION = (
    "Schedule variance in calendar days = actual completion date − reference date. "
    "Negative is early, 0 is on time, positive is late. Overdue applies only to incomplete "
    "work whose current target date has passed."
)

REFERENCE_LABELS = {
    "original_baseline": "Original approved baseline",
    "baseline_unverified": "Baseline without revision history (may not be the original)",
    "current_due_date": "Current due date (no baseline recorded; original commitment unknown)",
    "none": "No baseline or due date recorded",
}


def stage_label(stage: ProjectStage | None) -> str | None:
    if stage is None:
        return None
    return PLANNED_STAGE_LABELS.get(stage, stage.value.replace("_", " ").title())


@dataclass
class BaselineHistory:
    revision_count: int = 0
    original_completion: date | None = None
    predates_history: bool = False
    milestone_original_finish: dict[UUID, date] = field(default_factory=dict)


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def baseline_histories(db: Session, project_ids: list[UUID]) -> dict[UUID, BaselineHistory]:
    result: dict[UUID, BaselineHistory] = {pid: BaselineHistory() for pid in project_ids}
    if not project_ids:
        return result
    revisions: dict[UUID, list[ProjectBaselineRevision]] = defaultdict(list)
    for row in db.scalars(
        select(ProjectBaselineRevision)
        .where(ProjectBaselineRevision.project_id.in_(project_ids))
        .order_by(ProjectBaselineRevision.project_id, ProjectBaselineRevision.revision_number)
    ):
        revisions[row.project_id].append(row)
    for project_id, rows in revisions.items():
        history = result.setdefault(project_id, BaselineHistory())
        history.revision_count = len(rows)
        first = rows[0]
        if first.previous_completion_date is not None:
            history.original_completion = first.previous_completion_date
            history.predates_history = True
        else:
            history.original_completion = first.new_completion_date
        for row in rows:
            if not row.previous_milestones_json:
                continue
            try:
                snapshot = json.loads(row.previous_milestones_json)
            except (TypeError, ValueError):
                continue
            for item in snapshot if isinstance(snapshot, list) else []:
                finish = _parse_date(item.get("baseline_finish_date"))
                try:
                    milestone_id = UUID(str(item.get("milestone_id")))
                except (TypeError, ValueError):
                    continue
                if finish is not None:
                    history.milestone_original_finish.setdefault(milestone_id, finish)
    return result


def milestone_completion_date(milestone: Milestone) -> date | None:
    if milestone.completed_date is not None:
        return milestone.completed_date
    return milestone.completed_at.date() if milestone.completed_at else None


def project_completion_date(project: Project) -> date | None:
    return project.completed_at.date() if project.completed_at else None


def project_current_target(project: Project) -> date | None:
    return project.due_date or project.baseline_completion_date


def milestone_current_target(milestone: Milestone) -> date | None:
    return milestone.due_date or milestone.baseline_finish_date


def is_milestone_skipped(milestone: Milestone) -> bool:
    return milestone.status in _SKIPPED_MILESTONES


def is_milestone_overdue(milestone: Milestone, today: date) -> bool:
    """Open (not completed, cancelled or not applicable) and past its current target."""
    if is_milestone_skipped(milestone) or milestone.status == MilestoneStatus.completed:
        return False
    target = milestone_current_target(milestone)
    return target is not None and today > target


def _classify(
    *,
    skipped: bool,
    completed: bool,
    actual: date | None,
    reference: date | None,
    current_target: date | None,
    today: date,
) -> tuple[str, int | None, int | None]:
    """Return (status, schedule variance days, days overdue)."""
    if skipped:
        return "not_applicable", None, None
    if completed:
        if actual is None:
            return "completion_date_missing", None, None
        if reference is None:
            return "no_target", None, None
        days = (actual - reference).days
        return ("early" if days < 0 else "on_time" if days == 0 else "late"), days, None
    if current_target is None:
        return "no_target", None, None
    if today > current_target:
        return "overdue", None, (today - current_target).days
    return "not_due", None, None


def project_reference(project: Project, history: BaselineHistory) -> tuple[date | None, str]:
    if history.revision_count and history.original_completion is not None:
        source = "baseline_unverified" if history.predates_history else "original_baseline"
        return history.original_completion, source
    if project.baseline_completion_date is not None:
        return project.baseline_completion_date, "baseline_unverified"
    if project.due_date is not None:
        return project.due_date, "current_due_date"
    return None, "none"


def project_delivery(project: Project, history: BaselineHistory, today: date) -> ProjectDelivery:
    reference, source = project_reference(project, history)
    current_target = project_current_target(project)
    actual = project_completion_date(project)
    completed = project.execution_status == ExecutionStatus.completed
    status, variance, overdue = _classify(
        skipped=project.execution_status == ExecutionStatus.cancelled,
        completed=completed,
        actual=actual,
        reference=reference,
        current_target=current_target,
        today=today,
    )
    original = reference if source in {"original_baseline", "baseline_unverified"} else None
    return ProjectDelivery(
        status=status,  # type: ignore[arg-type]
        reference_source=source,  # type: ignore[arg-type]
        reference_label=REFERENCE_LABELS[source],
        reference_date=reference,
        original_baseline_completion_date=original,
        current_baseline_completion_date=project.baseline_completion_date,
        current_due_date=project.due_date,
        current_target_date=current_target,
        actual_completion_date=actual,
        schedule_variance_days=variance,
        current_target_variance_days=(actual - current_target).days
        if completed and actual is not None and current_target is not None
        else None,
        days_overdue=overdue,
        target_moved_days=(current_target - original).days
        if original is not None and current_target is not None
        else None,
        baseline_revision_count=history.revision_count,
    )


def milestone_delivery(milestone: Milestone, history: BaselineHistory, today: date) -> MilestoneDelivery:
    original = history.milestone_original_finish.get(milestone.id)
    if original is not None:
        source = "baseline_unverified" if history.predates_history else "original_baseline"
    elif milestone.baseline_finish_date is not None:
        original = milestone.baseline_finish_date
        source = "original_baseline" if history.revision_count else "baseline_unverified"
    elif milestone.due_date is not None:
        source = "current_due_date"
    else:
        source = "none"
    reference = original if original is not None else milestone.due_date
    current_target = milestone_current_target(milestone)
    actual = milestone_completion_date(milestone)
    status, variance, overdue = _classify(
        skipped=is_milestone_skipped(milestone),
        completed=milestone.status == MilestoneStatus.completed,
        actual=actual,
        reference=reference,
        current_target=current_target,
        today=today,
    )
    return MilestoneDelivery(
        milestone_id=milestone.id,
        name=milestone.name,
        stage=milestone.project_stage.value if milestone.project_stage else None,
        stage_label=stage_label(milestone.project_stage),
        milestone_status=milestone.status.value if milestone.status else "unknown",
        is_required=bool(milestone.is_required),
        original_baseline_finish_date=original,
        current_baseline_finish_date=milestone.baseline_finish_date,
        current_due_date=milestone.due_date,
        current_target_date=current_target,
        actual_completion_date=actual,
        reference_date=reference,
        reference_source=source,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        schedule_variance_days=variance,
        days_overdue=overdue,
    )


def build_delivery_metrics(
    project: Project, milestone_rows: list[Milestone], history: BaselineHistory, today: date
) -> DeliveryMetrics:
    ordered = sorted(milestone_rows, key=lambda m: (m.sort_order or 0, m.name or ""))
    milestones = [milestone_delivery(m, history, today) for m in ordered]
    return DeliveryMetrics(
        sign_convention=SIGN_CONVENTION,
        project=project_delivery(project, history, today),
        milestones=milestones,
        milestone_status_counts=dict(Counter(row.status for row in milestones)),
    )
