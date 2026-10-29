"""Engineering metrics — approved estimate, actual hours and variance for projects.

One place for:

* which estimate a project is measured against (``resolve_estimate``), shared with
  the Engineering Performance report;
* how a project's timesheet hours split across stages (``stage_hour_buckets``);
* the per-project metrics shown on the project workspace, with explicit
  data-quality indicators instead of misleading zeros.

Actual hours follow the existing project rule (``calculate_hours``): every
non-deleted timesheet entry booked to the project, any timesheet status, any
date, including post-completion hours. The split by timesheet status is
reported so unapproved or rejected hours stay visible.

Sign convention: variance = actual − estimate (positive means over the
estimate); remaining = estimate − actual (negative means overrun; never clamped).
These are performance indicators, not forecasts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    PLANNED_STAGE_LABELS,
    PLANNED_STAGES,
    ExecutionStatus,
    MilestoneStatus,
    ProjectStage,
    TimesheetStatus,
)
from app.models.finance import Quote, QuoteRevision
from app.models.models import (
    Milestone,
    Project,
    ProjectBaselineRevision,
    ProjectEstimateRevision,
    ProjectStageEstimate,
    Timesheet,
    TimesheetEntry,
)
from app.schemas.engineering_metrics import (
    ActualHoursMetrics,
    DataQualityIssue,
    EstimateMetrics,
    MetricValue,
    MilestoneReadiness,
    ProjectEngineeringMetrics,
    QuoteLinkage,
    StageAttributionMetrics,
    StageHoursRow,
)
from app.schemas.engineering_performance import KpiDefinition
from app.services.project_calculation_service import calculate_hours

ZERO = Decimal("0")
_SKIPPED_MILESTONES = {MilestoneStatus.cancelled, MilestoneStatus.not_applicable}

ESTIMATE_SOURCE_LABELS = {
    "stage_estimates": "Approved stage estimates",
    "milestone_hours": "Milestone planned hours (no stage estimates)",
    "quoted_hours": "Quoted hours (no stage estimates or milestone hours)",
    "none": "No estimate recorded",
}

METRIC_DEFINITIONS = [
    KpiDefinition(
        key="current_estimate",
        label="Current approved estimate",
        definition=(
            "The current stage estimates (original plus approved revisions) plus planned hours "
            "of milestones outside the three stages. Projects without stage estimates use "
            "milestone planned hours, then quoted hours. Same rule as the Engineering "
            "Performance report."
        ),
    ),
    KpiDefinition(
        key="original_estimate",
        label="Original estimate",
        definition=(
            "The stage estimates entered at creation (plus planned hours outside the stages); "
            "projects without stage estimates use quoted hours. Revisions never overwrite it."
        ),
    ),
    KpiDefinition(
        key="actual_hours",
        label="Actual hours",
        definition=(
            "All non-deleted timesheet hours booked to the project, any timesheet status and "
            "date, including post-completion hours. Same rule as the project page and the "
            "Engineering Performance report."
        ),
    ),
    KpiDefinition(
        key="variance",
        label="Hour variance",
        definition="Actual hours minus the current approved estimate. Positive means over the estimate.",
    ),
    KpiDefinition(
        key="utilization",
        label="Estimate utilization",
        definition=(
            "Actual hours divided by the current approved estimate, as a percentage. Not "
            "applicable when the estimate is zero."
        ),
    ),
    KpiDefinition(
        key="remaining",
        label="Remaining estimated hours",
        definition=(
            "Current approved estimate minus actual hours. Negative means the estimate is "
            "overrun. This is not a forecast of the hours still needed."
        ),
    ),
    KpiDefinition(
        key="stage_hours",
        label="Stage actual hours",
        definition=(
            "Timesheet hours booked to milestones of each stage of the same project. Hours "
            "without a milestone, on milestones without a stage, or on another project's "
            "milestone are reported separately and never spread across stages."
        ),
    ),
]


def round_hours(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


# --------------------------------------------------------------------------- estimate


@dataclass(frozen=True)
class EstimateResolution:
    original: Decimal | None
    current: Decimal | None
    source: str
    stage_original: dict[ProjectStage, Decimal] = field(default_factory=dict)
    stage_current: dict[ProjectStage, Decimal] = field(default_factory=dict)
    other_planned: Decimal = ZERO


def resolve_estimate(
    project: Project,
    estimate_rows: list[ProjectStageEstimate],
    milestone_rows: list[Milestone],
) -> EstimateResolution:
    stage_original = {row.stage: _dec(row.original_hours) for row in estimate_rows}
    stage_current = {row.stage: _dec(row.current_hours) for row in estimate_rows}
    other_planned = sum(
        (
            _dec(m.planned_hours)
            for m in milestone_rows
            if m.project_stage not in PLANNED_STAGES and m.status not in _SKIPPED_MILESTONES
        ),
        ZERO,
    )
    quoted = _dec(project.quoted_hours) if project.quoted_hours else None
    milestone_planned = _dec(project.current_planned_hours)
    if estimate_rows:
        return EstimateResolution(
            original=sum(stage_original.values(), ZERO) + other_planned,
            current=sum(stage_current.values(), ZERO) + other_planned,
            source="stage_estimates",
            stage_original=stage_original,
            stage_current=stage_current,
            other_planned=other_planned,
        )
    if milestone_planned > 0:
        return EstimateResolution(
            original=quoted if quoted and quoted > 0 else milestone_planned,
            current=milestone_planned,
            source="milestone_hours",
            other_planned=other_planned,
        )
    if quoted and quoted > 0:
        return EstimateResolution(original=quoted, current=quoted, source="quoted_hours")
    return EstimateResolution(original=None, current=None, source="none")


# --------------------------------------------------------------------------- stage buckets


@dataclass
class StageHourBuckets:
    stages: dict[ProjectStage, Decimal] = field(
        default_factory=lambda: {stage: ZERO for stage in PLANNED_STAGES}
    )
    other_stage: Decimal = ZERO
    no_stage: Decimal = ZERO
    no_milestone: Decimal = ZERO
    invalid_milestone: Decimal = ZERO

    @property
    def attributed(self) -> Decimal:
        return sum(self.stages.values(), ZERO)

    @property
    def unattributed(self) -> Decimal:
        return self.other_stage + self.no_stage + self.no_milestone + self.invalid_milestone

    @property
    def total(self) -> Decimal:
        return self.attributed + self.unattributed


def stage_hour_buckets(db: Session, project_ids: list[UUID]) -> dict[UUID, StageHourBuckets]:
    """Each non-deleted entry lands in exactly one bucket (entry → milestone is many-to-one)."""
    result: dict[UUID, StageHourBuckets] = {pid: StageHourBuckets() for pid in project_ids}
    if not project_ids:
        return result
    linked = case((TimesheetEntry.milestone_id.is_(None), 0), else_=1).label("linked")
    rows = db.execute(
        select(
            TimesheetEntry.project_id,
            linked,
            Milestone.project_id,
            Milestone.project_stage,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .outerjoin(Milestone, Milestone.id == TimesheetEntry.milestone_id)
        .where(
            TimesheetEntry.project_id.in_(project_ids),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.project_id, linked, Milestone.project_id, Milestone.project_stage)
    ).all()
    for project_id, is_linked, milestone_project_id, stage, hours in rows:
        bucket = result.setdefault(project_id, StageHourBuckets())
        value = _dec(hours)
        if not is_linked:
            bucket.no_milestone += value
        elif milestone_project_id is None or milestone_project_id != project_id:
            bucket.invalid_milestone += value
        elif stage in PLANNED_STAGES:
            bucket.stages[stage] += value
        elif stage is None:
            bucket.no_stage += value
        else:
            bucket.other_stage += value
    return result


# --------------------------------------------------------------------------- calculations


def hour_metrics(
    estimate: Decimal | None, actual: Decimal | None, *, missing_actual_reason: str | None = None
) -> tuple[MetricValue, MetricValue, MetricValue]:
    """Return (variance, utilization %, remaining) for one estimate/actual pair."""
    if actual is None:
        reason = missing_actual_reason or "Actual hours are unavailable."
        missing = MetricValue(status="unavailable", reason=reason)
        return missing, missing, missing
    if estimate is None:
        reason = "No approved estimate is recorded for this project."
        missing = MetricValue(status="unavailable", reason=reason)
        return missing, missing, missing
    variance = MetricValue(value=round_hours(actual - estimate), status="available")
    remaining = MetricValue(value=round_hours(estimate - actual), status="available")
    if estimate <= 0:
        utilization = MetricValue(
            status="not_applicable", reason="The approved estimate is zero hours."
        )
    else:
        utilization = MetricValue(
            value=round_hours(actual / estimate * Decimal("100")), status="available"
        )
    return variance, utilization, remaining


def _status_hours(db: Session, project_id: UUID) -> tuple[int, dict[TimesheetStatus | None, Decimal]]:
    rows = db.execute(
        select(
            Timesheet.status,
            func.count(TimesheetEntry.id),
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .select_from(TimesheetEntry)
        .outerjoin(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(TimesheetEntry.project_id == project_id, TimesheetEntry.is_deleted.is_(False))
        .group_by(Timesheet.status)
    ).all()
    count = sum(int(n or 0) for _, n, _ in rows)
    return count, {status: _dec(hours) for status, _, hours in rows}


def _milestone_readiness(
    db: Session, project: Project, milestone_rows: list[Milestone], today: date
) -> MilestoneReadiness:
    counted = [m for m in milestone_rows if m.status not in _SKIPPED_MILESTONES]
    completed = [m for m in counted if m.status == MilestoneStatus.completed]
    open_rows = [m for m in counted if m.status != MilestoneStatus.completed]
    baseline_revisions = db.scalars(
        select(ProjectBaselineRevision)
        .where(ProjectBaselineRevision.project_id == project.id)
        .order_by(ProjectBaselineRevision.revision_number)
    ).all()
    original_baseline = (
        baseline_revisions[0].previous_completion_date
        if baseline_revisions and baseline_revisions[0].previous_completion_date
        else project.baseline_completion_date
    )

    def target(m: Milestone) -> date | None:
        return m.baseline_finish_date or m.due_date

    return MilestoneReadiness(
        total=len(milestone_rows),
        completed=len(completed),
        open=len(open_rows),
        skipped=len(milestone_rows) - len(counted),
        open_required=sum(1 for m in open_rows if m.is_required),
        open_without_target_date=sum(1 for m in open_rows if target(m) is None),
        open_overdue=sum(1 for m in open_rows if target(m) is not None and target(m) < today),
        completed_with_completion_date=sum(
            1 for m in completed if m.completed_date or m.completed_at
        ),
        with_baseline_finish_date=sum(1 for m in counted if m.baseline_finish_date),
        with_original_planned_hours=sum(1 for m in counted if m.original_planned_hours is not None),
        current_target_date=project.due_date,
        baseline_completion_date=project.baseline_completion_date,
        original_baseline_completion_date=original_baseline,
        baseline_revision_count=len(baseline_revisions),
        actual_completion_date=project.completed_at.date() if project.completed_at else None,
    )


def _current_quote_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    return db.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
    )


def _quote_linkage(
    db: Session, project: Project, *, details_visible: bool, issues: list[DataQualityIssue]
) -> QuoteLinkage:
    quotes = db.scalars(
        select(Quote).where(Quote.project_id == project.id, Quote.is_active.is_(True))
    ).all()
    if not quotes:
        issues.append(
            DataQualityIssue(
                code="quote_unlinked",
                severity="info",
                message="No active Finance quote is linked to this project; estimates come from project records only.",
            )
        )
        return QuoteLinkage(status="unlinked", details_visible=details_visible)
    if len(quotes) > 1:
        issues.append(
            DataQualityIssue(
                code="quote_link_ambiguous",
                severity="warning",
                message=(
                    f"{len(quotes)} active Finance quotes are linked to this project; there is no "
                    "rule for choosing between them, so none is used."
                ),
            )
        )
        return QuoteLinkage(
            status="ambiguous", active_quote_count=len(quotes), details_visible=details_visible
        )
    quote = quotes[0]
    revision = _current_quote_revision(db, quote)
    if revision is None:
        issues.append(
            DataQualityIssue(
                code="quote_revision_unresolved",
                severity="warning",
                message=(
                    "The linked quote's current version/revision does not match any stored "
                    "revision, so its quoted hours cannot be confirmed."
                ),
            )
        )
    else:
        quote_hours = round_hours(_dec(revision.quoted_hours))
        project_quoted = round_hours(_dec(project.quoted_hours))
        if quote_hours != project_quoted:
            detail = (
                f" ({quote_hours} h on the quote vs {project_quoted} h on the project)"
                if details_visible
                else ""
            )
            issues.append(
                DataQualityIssue(
                    code="quote_hours_differ",
                    severity="info",
                    message=(
                        "The linked quote's current revision hours differ from the project's "
                        f"quoted hours{detail}. Project quoted hours are copied once and not re-synced."
                    ),
                )
            )
    if not details_visible:
        return QuoteLinkage(status="linked", active_quote_count=1, details_visible=False)
    return QuoteLinkage(
        status="linked",
        active_quote_count=1,
        details_visible=True,
        quote_reference=quote.external_quote_number or quote.tool_number,
        quote_version=quote.current_version,
        quote_revision=quote.current_revision,
        quote_hours=round_hours(_dec(revision.quoted_hours)) if revision is not None else None,
    )


def build_project_engineering_metrics(
    db: Session,
    project: Project,
    *,
    finance_details_visible: bool,
    today: date | None = None,
) -> ProjectEngineeringMetrics:
    """Read-only: never writes to the session."""
    today = today or date.today()
    issues: list[DataQualityIssue] = []

    estimate_rows = list(
        db.scalars(
            select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == project.id)
        ).all()
    )
    milestone_rows = list(
        db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all()
    )
    resolution = resolve_estimate(project, estimate_rows, milestone_rows)
    revisions = db.execute(
        select(func.count(ProjectEstimateRevision.id), func.max(ProjectEstimateRevision.revised_at))
        .where(ProjectEstimateRevision.project_id == project.id)
    ).one()

    quoted = round_hours(_dec(project.quoted_hours)) if project.quoted_hours else None
    estimate = EstimateMetrics(
        quoted_hours=quoted,
        original_estimate_hours=round_hours(resolution.original) if resolution.original is not None else None,
        current_estimate_hours=round_hours(resolution.current) if resolution.current is not None else None,
        estimate_source=resolution.source,  # type: ignore[arg-type]
        estimate_source_label=ESTIMATE_SOURCE_LABELS[resolution.source],
        revision_count=int(revisions[0] or 0),
        last_revised_at=revisions[1],
    )
    if resolution.source == "none":
        issues.append(
            DataQualityIssue(
                code="estimate_unavailable",
                severity="warning",
                message="No stage estimates, milestone planned hours or quoted hours are recorded.",
            )
        )
    elif resolution.current is not None and resolution.current <= 0:
        issues.append(
            DataQualityIssue(
                code="estimate_zero",
                severity="warning",
                message="The approved estimate is zero hours, so utilization cannot be calculated.",
            )
        )
    if resolution.source == "milestone_hours":
        issues.append(
            DataQualityIssue(
                code="estimate_from_milestone_plan",
                severity="info",
                message=(
                    "No approved stage estimates; the project is measured against milestone "
                    "planned hours, which are not revision-tracked."
                ),
            )
        )
    elif resolution.source == "quoted_hours":
        issues.append(
            DataQualityIssue(
                code="estimate_from_quoted_hours",
                severity="info",
                message="No stage estimates or milestone hours; the project is measured against its quoted hours.",
            )
        )
    if resolution.source == "stage_estimates" and quoted is not None:
        stage_original_total = round_hours(sum(resolution.stage_original.values(), ZERO))
        if stage_original_total != quoted:
            issues.append(
                DataQualityIssue(
                    code="quoted_hours_differ_from_original",
                    severity="info",
                    message=(
                        f"Quoted hours ({quoted} h) differ from the original stage estimate total "
                        f"({stage_original_total} h); quoted hours were edited outside the "
                        "estimate revision history."
                    ),
                )
            )

    hours = calculate_hours(db, project)
    entry_count, by_status = _status_hours(db, project.id)
    has_progress = project.execution_status == ExecutionStatus.completed or any(
        m.status == MilestoneStatus.completed for m in milestone_rows
    )
    if entry_count > 0:
        actual_status = "recorded"
    elif has_progress:
        actual_status = "missing"
    else:
        actual_status = "none_recorded"
    actual_total = None if actual_status == "missing" else round_hours(hours.actual)
    unknown_status = by_status.get(None, ZERO)
    actual = ActualHoursMetrics(
        status=actual_status,  # type: ignore[arg-type]
        total_hours=actual_total,
        entry_count=entry_count,
        before_completion_hours=round_hours(hours.original),
        post_completion_hours=round_hours(hours.post_completion_total),
        approved_hours=round_hours(by_status.get(TimesheetStatus.approved, ZERO)),
        submitted_hours=round_hours(by_status.get(TimesheetStatus.submitted, ZERO)),
        draft_hours=round_hours(by_status.get(TimesheetStatus.draft, ZERO)),
        rejected_hours=round_hours(by_status.get(TimesheetStatus.rejected, ZERO)),
    )
    missing_reason = None
    if actual_status == "missing":
        missing_reason = (
            "No timesheet hours are recorded although work has been completed; actual hours "
            "are missing rather than zero."
        )
        issues.append(
            DataQualityIssue(code="actual_hours_missing", severity="warning", message=missing_reason)
        )
    elif actual_status == "none_recorded":
        issues.append(
            DataQualityIssue(
                code="no_hours_recorded",
                severity="info",
                message="No timesheet hours have been booked to this project yet.",
            )
        )
    if actual.rejected_hours > 0:
        issues.append(
            DataQualityIssue(
                code="includes_rejected_hours",
                severity="warning",
                message=(
                    f"{actual.rejected_hours} h are on rejected timesheets. They still count "
                    "toward actual hours under the current project rule."
                ),
            )
        )
    pending = actual.draft_hours + actual.submitted_hours
    if pending > 0:
        issues.append(
            DataQualityIssue(
                code="includes_unapproved_hours",
                severity="info",
                message=f"{pending} h are on draft or submitted timesheets that are not yet approved.",
            )
        )
    if unknown_status > 0:
        issues.append(
            DataQualityIssue(
                code="entries_without_timesheet",
                severity="warning",
                message=f"{round_hours(unknown_status)} h belong to entries whose timesheet record is missing.",
            )
        )

    variance, utilization, remaining = hour_metrics(
        resolution.current, actual_total, missing_actual_reason=missing_reason
    )
    original_variance, _, _ = hour_metrics(
        resolution.original, actual_total, missing_actual_reason=missing_reason
    )

    buckets = stage_hour_buckets(db, [project.id])[project.id]
    has_stage_plan = bool(estimate_rows) or any(
        m.project_stage in PLANNED_STAGES for m in milestone_rows
    )
    total = buckets.total
    if not has_stage_plan:
        stage_status = "unavailable"
    elif total <= 0:
        stage_status = "no_hours"
    elif buckets.attributed <= 0:
        stage_status = "unavailable"
    elif buckets.unattributed > 0:
        stage_status = "partial"
    else:
        stage_status = "complete"
    rows: list[StageHoursRow] = []
    if stage_status in {"complete", "partial"}:
        for stage in PLANNED_STAGES:
            current_stage = resolution.stage_current.get(stage)
            stage_actual = round_hours(buckets.stages[stage])
            rows.append(
                StageHoursRow(
                    key=stage.value,
                    label=PLANNED_STAGE_LABELS[stage],
                    original_estimate_hours=round_hours(resolution.stage_original[stage])
                    if stage in resolution.stage_original
                    else None,
                    current_estimate_hours=round_hours(current_stage) if current_stage is not None else None,
                    actual_hours=stage_actual,
                    variance_hours=round_hours(stage_actual - current_stage)
                    if current_stage is not None
                    else None,
                )
            )
    stage_attribution = StageAttributionMetrics(
        status=stage_status,  # type: ignore[arg-type]
        coverage_percent=round_hours(buckets.attributed / total * Decimal("100")) if total > 0 else None,
        attributed_hours=round_hours(buckets.attributed),
        other_stage_hours=round_hours(buckets.other_stage),
        no_stage_hours=round_hours(buckets.no_stage),
        no_milestone_hours=round_hours(buckets.no_milestone),
        invalid_milestone_hours=round_hours(buckets.invalid_milestone),
        rows=rows,
    )
    if stage_status == "partial":
        issues.append(
            DataQualityIssue(
                code="stage_attribution_partial",
                severity="warning",
                message=(
                    f"{round_hours(buckets.unattributed)} h of {round_hours(total)} h are not linked "
                    "to a staged milestone; stage hours are incomplete and are not adjusted."
                ),
            )
        )
    elif stage_status == "unavailable" and total > 0:
        issues.append(
            DataQualityIssue(
                code="stage_attribution_unavailable",
                severity="info",
                message=(
                    "Hours are not linked to staged milestones, so stage-wise actual hours "
                    "cannot be reported. Total actual hours are unaffected."
                ),
            )
        )
    if buckets.invalid_milestone > 0:
        issues.append(
            DataQualityIssue(
                code="invalid_milestone_link",
                severity="warning",
                message=(
                    f"{round_hours(buckets.invalid_milestone)} h are linked to a milestone that "
                    "belongs to another project or no longer exists."
                ),
            )
        )

    milestones = _milestone_readiness(db, project, milestone_rows, today)
    if project.execution_status == ExecutionStatus.completed:
        if project.completed_at is None:
            issues.append(
                DataQualityIssue(
                    code="completed_without_date",
                    severity="warning",
                    message="The project is completed but has no actual completion date.",
                )
            )
        if milestones.open_required:
            issues.append(
                DataQualityIssue(
                    code="open_milestones_on_completed_project",
                    severity="warning",
                    message=(
                        f"{milestones.open_required} required milestone(s) are still open on a "
                        "completed project."
                    ),
                )
            )
    if milestones.original_baseline_completion_date is None:
        issues.append(
            DataQualityIssue(
                code="original_commitment_unavailable",
                severity="info",
                message=(
                    "No baseline is recorded, so the original delivery commitment cannot be "
                    "separated from the current due date."
                ),
            )
        )

    quote_linkage = _quote_linkage(
        db, project, details_visible=finance_details_visible, issues=issues
    )

    if resolution.current is None or actual_status == "missing":
        overall = "unavailable"
    elif any(issue.severity == "warning" for issue in issues):
        overall = "available_with_limitations"
    else:
        overall = "available"

    return ProjectEngineeringMetrics(
        project_id=project.id,
        code=project.code,
        tool_number=project.tool_number,
        part_description=project.part_description,
        execution_status=project.execution_status.value
        if project.execution_status is not None
        else "unknown",
        data_quality_status=overall,  # type: ignore[arg-type]
        estimate=estimate,
        actual=actual,
        variance_hours=variance,
        utilization_percent=utilization,
        remaining_hours=remaining,
        original_variance_hours=original_variance,
        stage_attribution=stage_attribution,
        milestones=milestones,
        quote_linkage=quote_linkage,
        issues=issues,
        definitions=METRIC_DEFINITIONS,
        calculated_at=datetime.now(timezone.utc),
    )


def stage_estimates_by_project(
    db: Session, project_ids: list[UUID]
) -> dict[UUID, list[ProjectStageEstimate]]:
    result: dict[UUID, list[ProjectStageEstimate]] = defaultdict(list)
    if not project_ids:
        return result
    for row in db.scalars(
        select(ProjectStageEstimate).where(ProjectStageEstimate.project_id.in_(project_ids))
    ):
        result[row.project_id].append(row)
    return result
