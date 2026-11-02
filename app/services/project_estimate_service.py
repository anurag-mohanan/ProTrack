"""Stage estimates: original vs current approved hours, revisions and breakdown.

Definitions (shared by the project page, reports and exports)
------------------------------------------------------------
* Original estimate — stage hours entered at project creation (or the first time
  a legacy project is configured). Never overwritten.
* Current approved estimate — original plus every approved revision.
* Actual hours — non-deleted timesheet hours booked to the stage's milestones
  (the same rule as project actual hours).
* Forecast remaining — for each open milestone, current planned minus actual,
  floored at zero; completed/cancelled milestones contribute nothing.
* EAC (estimate at completion) — actual + forecast remaining.
* Variance — EAC minus current approved estimate (positive = over plan).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import (
    PLANNED_STAGE_LABELS,
    PLANNED_STAGES,
    MilestoneStatus,
    ProjectStage,
)
from app.models.models import (
    Milestone,
    Project,
    ProjectEstimateRevision,
    ProjectStageEstimate,
    TimesheetEntry,
    User,
)
from app.services.actual_hours import official_entry_clause
from app.services.milestone_lifecycle import active_milestone_clause, is_active

_CLOSED = {MilestoneStatus.completed, MilestoneStatus.cancelled, MilestoneStatus.not_applicable}
OTHER_STAGE_KEY = "other"


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stage_estimates(db: Session, project_id: UUID) -> dict[ProjectStage, ProjectStageEstimate]:
    rows = db.scalars(
        select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == project_id)
    ).all()
    return {row.stage: row for row in rows}


def add_initial_stage_estimates(
    db: Session,
    project: Project,
    stage_hours: dict[ProjectStage, Decimal],
    *,
    created_by_id: UUID | None = None,
) -> None:
    for stage in PLANNED_STAGES:
        hours = _q2(stage_hours.get(stage, Decimal("0")))
        if hours < 0:
            raise ProTrackValidationError(f"{PLANNED_STAGE_LABELS[stage]} hours cannot be negative")
        db.add(
            ProjectStageEstimate(
                project_id=project.id,
                stage=stage,
                original_hours=hours,
                current_hours=hours,
                created_by_id=created_by_id,
            )
        )
    db.flush()


def _distribute(total: Decimal, milestones: list[Milestone]) -> dict[UUID, Decimal]:
    if not milestones:
        return {}
    weights = [Decimal(str(row.planned_hours or 0)) for row in milestones]
    if sum(weights) <= 0:
        weights = [Decimal("1")] * len(milestones)
    weight_total = sum(weights)
    result: dict[UUID, Decimal] = {}
    allocated = Decimal("0")
    for index, (row, weight) in enumerate(zip(milestones, weights, strict=True)):
        if index == len(milestones) - 1:
            result[row.id] = _q2(total - allocated)
        else:
            share = _q2(total * weight / weight_total)
            result[row.id] = share
            allocated += share
    return result


def configure_stage_estimates(
    db: Session,
    project: Project,
    stage_hours: dict[ProjectStage, Decimal],
    *,
    user: User,
) -> None:
    """First-time stage estimates for a project created before stage planning.

    Milestones of a stage only receive hours when none of them has hours yet;
    otherwise their existing allocation is kept.
    """
    if stage_estimates(db, project.id):
        raise ProTrackValidationError(
            "Stage estimates are already configured; use an estimate revision to change them"
        )
    add_initial_stage_estimates(db, project, stage_hours, created_by_id=user.id)
    milestones = list(
        db.scalars(
            select(Milestone).where(Milestone.project_id == project.id, active_milestone_clause())
        ).all()
    )
    for stage in PLANNED_STAGES:
        rows = sorted(
            (row for row in milestones if row.project_stage == stage),
            key=lambda row: row.sort_order,
        )
        if not rows or any(Decimal(str(row.planned_hours or 0)) > 0 for row in rows):
            continue
        shares = _distribute(_q2(stage_hours.get(stage, Decimal("0"))), rows)
        for row in rows:
            row.planned_hours = shares[row.id]
            if row.original_planned_hours is None:
                row.original_planned_hours = shares[row.id]
                row.estimate_basis = "equal_split"
            db.add(row)
    project.quoted_hours = _q2(sum(stage_hours.get(stage, Decimal("0")) for stage in PLANNED_STAGES))
    db.add(project)
    db.flush()


def revise_stage_estimate(
    db: Session,
    project: Project,
    *,
    stage: ProjectStage,
    new_hours: Decimal,
    reason: str,
    user: User,
) -> ProjectEstimateRevision:
    if stage not in PLANNED_STAGES:
        raise ProTrackValidationError("Only Blockout, Intermediate and Final Design can be revised")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ProTrackValidationError("Give a reason for the estimate revision (at least 5 characters)")
    new_hours = _q2(new_hours)
    if new_hours < 0:
        raise ProTrackValidationError("Estimate hours cannot be negative")
    estimate = stage_estimates(db, project.id).get(stage)
    if estimate is None:
        raise ProTrackValidationError("Configure stage estimates before revising them")
    if new_hours == _q2(estimate.current_hours):
        raise ProTrackValidationError("The new estimate is the same as the current estimate")

    milestones = sorted(
        db.scalars(
            select(Milestone).where(
                Milestone.project_id == project.id,
                Milestone.project_stage == stage,
                active_milestone_clause(),
            )
        ).all(),
        key=lambda row: row.sort_order,
    )
    closed_hours = sum(
        (Decimal(str(row.planned_hours or 0)) for row in milestones if row.status in _CLOSED),
        Decimal("0"),
    )
    if new_hours < closed_hours:
        raise ProTrackValidationError(
            f"The new estimate ({new_hours} h) is below the hours already planned on completed "
            f"milestones in this stage ({_q2(closed_hours)} h)"
        )
    open_rows = [row for row in milestones if row.status not in _CLOSED]
    shares = _distribute(new_hours - closed_hours, open_rows)
    for row in open_rows:
        row.planned_hours = shares[row.id]
        db.add(row)

    revision = ProjectEstimateRevision(
        project_id=project.id,
        stage=stage,
        previous_hours=_q2(estimate.current_hours),
        new_hours=new_hours,
        reason=reason,
        revised_by_id=user.id,
        revised_at=_now(),
    )
    estimate.current_hours = new_hours
    db.add(estimate)
    db.add(revision)
    db.flush()
    return revision


# --------------------------------------------------------------------------- breakdown


@dataclass
class MilestoneLine:
    milestone: Milestone
    actual_hours: Decimal
    forecast_remaining: Decimal
    overdue: bool
    forecast_late: bool


@dataclass
class StageLine:
    key: str
    label: str
    configured: bool
    original_hours: Decimal | None
    current_hours: Decimal | None
    milestone_planned_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    forecast_remaining: Decimal = Decimal("0")
    milestones: list[MilestoneLine] = field(default_factory=list)

    @property
    def eac(self) -> Decimal:
        return _q2(self.actual_hours + self.forecast_remaining)

    @property
    def reference_hours(self) -> Decimal:
        return self.current_hours if self.current_hours is not None else self.milestone_planned_hours

    @property
    def variance(self) -> Decimal:
        return _q2(self.eac - self.reference_hours)

    @property
    def variance_percent(self) -> Decimal | None:
        if self.reference_hours <= 0:
            return None
        return _q2(self.variance / self.reference_hours * Decimal("100"))


def milestone_actual_hours(db: Session, milestone_ids: list[UUID]) -> dict[UUID, Decimal]:
    if not milestone_ids:
        return {}
    rows = db.execute(
        select(TimesheetEntry.milestone_id, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .where(TimesheetEntry.milestone_id.in_(milestone_ids), official_entry_clause())
        .group_by(TimesheetEntry.milestone_id)
    ).all()
    return {milestone_id: _q2(hours or 0) for milestone_id, hours in rows}


def unassigned_actual_hours(db: Session, project_id: UUID) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.milestone_id.is_(None),
            official_entry_clause(),
        )
    )
    return _q2(value or 0)


def stage_breakdown(db: Session, project: Project, *, today: date | None = None) -> list[StageLine]:
    today = today or date.today()
    estimates = stage_estimates(db, project.id)
    milestones = sorted(
        db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all(),
        key=lambda row: row.sort_order,
    )
    actuals = milestone_actual_hours(db, [row.id for row in milestones])
    lines: dict[str, StageLine] = {}
    for stage in PLANNED_STAGES:
        estimate = estimates.get(stage)
        lines[stage.value] = StageLine(
            key=stage.value,
            label=PLANNED_STAGE_LABELS[stage],
            configured=estimate is not None,
            original_hours=_q2(estimate.original_hours) if estimate else None,
            current_hours=_q2(estimate.current_hours) if estimate else None,
        )
    lines[OTHER_STAGE_KEY] = StageLine(
        key=OTHER_STAGE_KEY,
        label="Other milestones (outside the three stages)",
        configured=True,
        original_hours=None,
        current_hours=None,
    )
    for row in milestones:
        key = row.project_stage.value if row.project_stage in PLANNED_STAGES else OTHER_STAGE_KEY
        line = lines[key]
        planned = _q2(row.planned_hours or 0)
        actual = actuals.get(row.id, Decimal("0.00"))
        if not is_active(row):
            # Hours booked on merged/superseded records still count; their plan does not.
            line.actual_hours = _q2(line.actual_hours + actual)
            continue
        remaining = Decimal("0.00") if row.status in _CLOSED else max(planned - actual, Decimal("0"))
        due = row.baseline_finish_date or row.due_date
        overdue = row.status not in _CLOSED and due is not None and due < today
        forecast_late = (
            row.status not in _CLOSED
            and row.forecast_finish_date is not None
            and due is not None
            and row.forecast_finish_date > due
        )
        line.milestones.append(MilestoneLine(row, actual, _q2(remaining), overdue, forecast_late))
        line.milestone_planned_hours = _q2(line.milestone_planned_hours + planned)
        line.actual_hours = _q2(line.actual_hours + actual)
        line.forecast_remaining = _q2(line.forecast_remaining + remaining)
    unassigned = unassigned_actual_hours(db, project.id)
    if unassigned:
        other = lines[OTHER_STAGE_KEY]
        other.actual_hours = _q2(other.actual_hours + unassigned)
    result = [lines[stage.value] for stage in PLANNED_STAGES]
    if lines[OTHER_STAGE_KEY].milestones or lines[OTHER_STAGE_KEY].actual_hours:
        result.append(lines[OTHER_STAGE_KEY])
    return result
