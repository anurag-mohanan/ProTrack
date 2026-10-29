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
    ProjectEstimateRevision,
    ProjectStageEstimate,
    Timesheet,
    TimesheetEntry,
)
from app.schemas.engineering_metrics import (
    ActualHoursMetrics,
    DataQualityIssue,
    DeliveryMetrics,
    EstimateMetrics,
    MetricValue,
    MilestoneReadiness,
    ProjectEngineeringMetrics,
    QuoteLinkage,
    StageAttributionMetrics,
    StageHoursRow,
)
from app.schemas.engineering_performance import KpiDefinition
from app.services.delivery_variance_service import (
    BaselineHistory,
    baseline_histories,
    build_delivery_metrics,
    stage_label,
)
from app.services.project_calculation_service import ProjectHours, batch_calculate_hours

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
            "milestone are reported separately and never spread across stages. Only stages "
            "in the project's own plan are listed; stage rows plus unattributed hours equal "
            "total actual hours."
        ),
    ),
    KpiDefinition(
        key="stage_variance",
        label="Stage variance and utilization",
        definition=(
            "Stage actual hours minus the current approved stage estimate (positive = over), "
            "and actual ÷ estimate as a percentage. Shown only where an approved stage "
            "estimate exists; utilization is not applicable for a zero estimate. The project "
            "estimate is never split across stages."
        ),
    ),
    KpiDefinition(
        key="delivery_variance",
        label="Schedule variance (days)",
        definition=(
            "Actual completion date minus the reference date, in calendar days (negative = "
            "early, 0 = on time, positive = late). The reference is the original approved "
            "baseline; without baseline history the stored baseline or current due date is "
            "used and labelled. Incomplete work is overdue only after its current target date "
            "(due date, else current baseline) has passed."
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
    """``stages`` holds the three planned stages; ``other_stages`` any other stage.

    ``attributed`` / ``unattributed`` are relative to the planned stages (used by the
    Engineering Performance stage table); ``staged`` / ``unstaged`` are relative to
    every stage (used for per-project stage rows).
    """

    stages: dict[ProjectStage, Decimal] = field(
        default_factory=lambda: {stage: ZERO for stage in PLANNED_STAGES}
    )
    other_stages: dict[ProjectStage, Decimal] = field(default_factory=dict)
    no_stage: Decimal = ZERO
    no_milestone: Decimal = ZERO
    invalid_milestone: Decimal = ZERO

    @property
    def other_stage(self) -> Decimal:
        return sum(self.other_stages.values(), ZERO)

    @property
    def attributed(self) -> Decimal:
        return sum(self.stages.values(), ZERO)

    @property
    def unattributed(self) -> Decimal:
        return self.other_stage + self.unstaged

    @property
    def staged(self) -> Decimal:
        return self.attributed + self.other_stage

    @property
    def unstaged(self) -> Decimal:
        return self.no_stage + self.no_milestone + self.invalid_milestone

    @property
    def total(self) -> Decimal:
        return self.attributed + self.unattributed

    def stage_hours(self, stage: ProjectStage) -> Decimal:
        if stage in self.stages:
            return self.stages[stage]
        return self.other_stages.get(stage, ZERO)


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
            bucket.other_stages[stage] = bucket.other_stages.get(stage, ZERO) + value
    return result


# --------------------------------------------------------------------------- calculations


def hour_metrics(
    estimate: Decimal | None,
    actual: Decimal | None,
    *,
    missing_actual_reason: str | None = None,
    missing_estimate_reason: str | None = None,
) -> tuple[MetricValue, MetricValue, MetricValue]:
    """Return (variance, utilization %, remaining) for one estimate/actual pair."""
    if actual is None:
        reason = missing_actual_reason or "Actual hours are unavailable."
        missing = MetricValue(status="unavailable", reason=reason)
        return missing, missing, missing
    if estimate is None:
        reason = missing_estimate_reason or "No approved estimate is recorded for this project."
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


STAGE_SOURCE = (
    "Timesheet entry → its milestone → that milestone's engineering stage (same project only). "
    "Entries without a milestone, on milestones without a stage, or on another project's "
    "milestone are unattributed. Nothing is allocated proportionally."
)


def project_plan_stages(
    estimate_rows: list[ProjectStageEstimate],
    milestone_rows: list[Milestone],
    buckets: StageHourBuckets,
) -> list[ProjectStage]:
    """Stages that exist for this project: an estimate, an active milestone, or booked hours."""
    present = {row.stage for row in estimate_rows}
    present |= {
        m.project_stage
        for m in milestone_rows
        if m.project_stage is not None and m.status not in _SKIPPED_MILESTONES
    }
    present |= {stage for stage, hours in buckets.stages.items() if hours > 0}
    present |= {stage for stage, hours in buckets.other_stages.items() if hours > 0}
    return [stage for stage in ProjectStage if stage in present]


def stage_attribution_status(buckets: StageHourBuckets, stages: list[ProjectStage]) -> str:
    if not stages:
        return "unavailable"
    if buckets.total <= 0:
        return "no_hours"
    if buckets.staged <= 0:
        return "unavailable"
    if buckets.unstaged > 0:
        return "partial"
    return "complete"


def _stage_attribution(
    buckets: StageHourBuckets,
    resolution: EstimateResolution,
    stages: list[ProjectStage],
    *,
    actual_missing: bool,
) -> StageAttributionMetrics:
    total = buckets.total
    status = stage_attribution_status(buckets, stages)

    rows: list[StageHoursRow] = []
    for stage in stages:
        notes: list[str] = []
        actual_reason: str | None = None
        actual: Decimal | None
        if actual_missing:
            actual = None
            actual_reason = "The project's actual hours are missing, so stage hours cannot be stated."
        elif status == "no_hours":
            actual = ZERO
        elif status == "unavailable":
            actual = None
            actual_reason = "No timesheet hours are linked to this project's staged milestones."
        else:
            actual = round_hours(buckets.stage_hours(stage))
            if status == "partial":
                notes.append(
                    f"{round_hours(buckets.unstaged)} h of the project's hours are not attributed "
                    "to any stage, so this stage's actual hours may be understated."
                )
        if actual_reason:
            notes.append(actual_reason)

        current = resolution.stage_current.get(stage)
        original = resolution.stage_original.get(stage)
        estimate_reason = None
        if current is None:
            estimate_reason = "No approved estimate exists for this stage."
            if stage not in PLANNED_STAGES:
                estimate_reason += (
                    " Approved stage estimates cover Blockout, Intermediate Design and Final "
                    "Design only."
                )
            notes.append(estimate_reason)
        elif current <= 0:
            notes.append("The approved stage estimate is zero hours, so utilization is not applicable.")
        variance, utilization, remaining = hour_metrics(
            current,
            actual,
            missing_actual_reason=actual_reason,
            missing_estimate_reason=estimate_reason,
        )
        if actual is None:
            quality = "unavailable"
        elif status in {"complete", "no_hours"} and current is not None and current > 0:
            quality = "complete"
        else:
            quality = "limited"
        rows.append(
            StageHoursRow(
                key=stage.value,
                label=stage_label(stage) or stage.value,
                has_approved_estimate=current is not None,
                original_estimate_hours=round_hours(original) if original is not None else None,
                current_estimate_hours=round_hours(current) if current is not None else None,
                actual_hours=actual,
                percent_of_project_actual=round_hours(actual / total * Decimal("100"))
                if actual is not None and total > 0
                else None,
                variance_hours=variance.value,
                variance=variance,
                utilization_percent=utilization,
                remaining_hours=remaining,
                data_quality=quality,  # type: ignore[arg-type]
                data_quality_notes=notes,
            )
        )
    return StageAttributionMetrics(
        status=status,  # type: ignore[arg-type]
        coverage_percent=round_hours(buckets.staged / total * Decimal("100")) if total > 0 else None,
        total_hours=None if actual_missing else round_hours(total),
        attributed_hours=round_hours(buckets.staged),
        unattributed_hours=round_hours(buckets.unstaged),
        other_stage_hours=round_hours(buckets.other_stage),
        no_stage_hours=round_hours(buckets.no_stage),
        no_milestone_hours=round_hours(buckets.no_milestone),
        invalid_milestone_hours=round_hours(buckets.invalid_milestone),
        source=STAGE_SOURCE,
        rows=rows,
    )


@dataclass
class MetricInputs:
    """Source records for one project, loaded in bulk by ``load_metric_inputs``."""

    estimate_rows: list[ProjectStageEstimate] = field(default_factory=list)
    milestone_rows: list[Milestone] = field(default_factory=list)
    revision_count: int = 0
    last_revised_at: datetime | None = None
    hours: ProjectHours | None = None
    entry_count: int = 0
    by_status: dict[TimesheetStatus | None, Decimal] = field(default_factory=dict)
    buckets: StageHourBuckets = field(default_factory=StageHourBuckets)
    history: BaselineHistory = field(default_factory=BaselineHistory)
    quotes: list[Quote] = field(default_factory=list)
    quote_revisions: dict[UUID, QuoteRevision | None] = field(default_factory=dict)


def load_metric_inputs(db: Session, projects: list[Project]) -> dict[UUID, MetricInputs]:
    """A fixed number of grouped queries regardless of how many projects are passed."""
    ids = [project.id for project in projects]
    result = {pid: MetricInputs() for pid in ids}
    if not ids:
        return result
    for row in db.scalars(
        select(ProjectStageEstimate).where(ProjectStageEstimate.project_id.in_(ids))
    ):
        result[row.project_id].estimate_rows.append(row)
    for row in db.scalars(select(Milestone).where(Milestone.project_id.in_(ids))):
        result[row.project_id].milestone_rows.append(row)
    for project_id, count, last in db.execute(
        select(
            ProjectEstimateRevision.project_id,
            func.count(ProjectEstimateRevision.id),
            func.max(ProjectEstimateRevision.revised_at),
        )
        .where(ProjectEstimateRevision.project_id.in_(ids))
        .group_by(ProjectEstimateRevision.project_id)
    ):
        result[project_id].revision_count = int(count or 0)
        result[project_id].last_revised_at = last
    for project_id, hours in batch_calculate_hours(db, projects).items():
        result[project_id].hours = hours
    for project_id, status, count, hours in db.execute(
        select(
            TimesheetEntry.project_id,
            Timesheet.status,
            func.count(TimesheetEntry.id),
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .select_from(TimesheetEntry)
        .outerjoin(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(TimesheetEntry.project_id.in_(ids), TimesheetEntry.is_deleted.is_(False))
        .group_by(TimesheetEntry.project_id, Timesheet.status)
    ):
        result[project_id].entry_count += int(count or 0)
        result[project_id].by_status[status] = _dec(hours)
    for project_id, buckets in stage_hour_buckets(db, ids).items():
        result[project_id].buckets = buckets
    for project_id, history in baseline_histories(db, ids).items():
        result[project_id].history = history
    quotes = db.scalars(
        select(Quote).where(Quote.project_id.in_(ids), Quote.is_active.is_(True))
    ).all()
    for quote in quotes:
        result[quote.project_id].quotes.append(quote)
    if quotes:
        revisions = {
            (row.quote_id, row.version, row.revision): row
            for row in db.scalars(
                select(QuoteRevision).where(QuoteRevision.quote_id.in_([q.id for q in quotes]))
            )
        }
        for quote in quotes:
            result[quote.project_id].quote_revisions[quote.id] = revisions.get(
                (quote.id, quote.current_version, quote.current_revision)
            )
    return result


def _milestone_readiness(
    project: Project, milestone_rows: list[Milestone], delivery: DeliveryMetrics
) -> MilestoneReadiness:
    counted = [m for m in milestone_rows if m.status not in _SKIPPED_MILESTONES]
    completed = [m for m in counted if m.status == MilestoneStatus.completed]
    open_rows = [m for m in counted if m.status != MilestoneStatus.completed]
    open_statuses = [
        row.status for row in delivery.milestones if row.status in {"overdue", "not_due", "no_target"}
    ]
    return MilestoneReadiness(
        total=len(milestone_rows),
        completed=len(completed),
        open=len(open_rows),
        skipped=len(milestone_rows) - len(counted),
        open_required=sum(1 for m in open_rows if m.is_required),
        open_without_target_date=open_statuses.count("no_target"),
        open_overdue=open_statuses.count("overdue"),
        completed_with_completion_date=sum(
            1 for m in completed if m.completed_date or m.completed_at
        ),
        with_baseline_finish_date=sum(1 for m in counted if m.baseline_finish_date),
        with_original_planned_hours=sum(1 for m in counted if m.original_planned_hours is not None),
        current_target_date=project.due_date,
        baseline_completion_date=project.baseline_completion_date,
        original_baseline_completion_date=delivery.project.original_baseline_completion_date,
        baseline_revision_count=delivery.project.baseline_revision_count,
        actual_completion_date=delivery.project.actual_completion_date,
    )


def _quote_linkage(
    project: Project,
    inputs: MetricInputs,
    *,
    details_visible: bool,
    issues: list[DataQualityIssue],
) -> QuoteLinkage:
    quotes = inputs.quotes
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
    revision = inputs.quote_revisions.get(quote.id)
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
    inputs = load_metric_inputs(db, [project])[project.id]
    return compute_project_metrics(
        project, inputs, finance_details_visible=finance_details_visible, today=today
    )


def build_engineering_metrics_batch(
    db: Session,
    projects: list[Project],
    *,
    finance_details_visible: bool,
    today: date | None = None,
) -> dict[UUID, ProjectEngineeringMetrics]:
    """Same rules as ``build_project_engineering_metrics`` for many projects; read-only."""
    today = today or date.today()
    inputs = load_metric_inputs(db, projects)
    return {
        project.id: compute_project_metrics(
            project, inputs[project.id], finance_details_visible=finance_details_visible, today=today
        )
        for project in projects
    }


def compute_project_metrics(
    project: Project,
    inputs: MetricInputs,
    *,
    finance_details_visible: bool,
    today: date | None = None,
) -> ProjectEngineeringMetrics:
    today = today or date.today()
    issues: list[DataQualityIssue] = []

    estimate_rows = inputs.estimate_rows
    milestone_rows = inputs.milestone_rows
    resolution = resolve_estimate(project, estimate_rows, milestone_rows)
    revisions = (inputs.revision_count, inputs.last_revised_at)

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

    hours = inputs.hours
    if hours is None:
        raise ValueError("MetricInputs.hours must be loaded with load_metric_inputs")
    entry_count, by_status = inputs.entry_count, inputs.by_status
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

    buckets = inputs.buckets
    stages = project_plan_stages(estimate_rows, milestone_rows, buckets)
    stage_attribution = _stage_attribution(
        buckets, resolution, stages, actual_missing=actual_status == "missing"
    )
    total = buckets.total
    if stage_attribution.status == "partial":
        issues.append(
            DataQualityIssue(
                code="stage_attribution_partial",
                severity="warning",
                message=(
                    f"{round_hours(buckets.unstaged)} h of {round_hours(total)} h are not linked "
                    "to a staged milestone; stage hours are incomplete and are not adjusted."
                ),
            )
        )
    elif stage_attribution.status == "unavailable" and total > 0:
        issues.append(
            DataQualityIssue(
                code="stage_attribution_unavailable",
                severity="info",
                message=(
                    "Hours are not linked to staged milestones, so stage-wise actual hours "
                    "cannot be reported. Total actual hours are unaffected."
                    if stages
                    else "This project's milestones carry no engineering stage, so stage-wise "
                    "hours do not apply. Total actual hours are unaffected."
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

    delivery = build_delivery_metrics(project, milestone_rows, inputs.history, today)
    milestones = _milestone_readiness(project, milestone_rows, delivery)
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
    project_delivery = delivery.project
    if project_delivery.reference_source in {"current_due_date", "none"}:
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
    elif project_delivery.reference_source == "baseline_unverified":
        issues.append(
            DataQualityIssue(
                code="baseline_history_missing",
                severity="info",
                message=(
                    "A baseline is stored but its revision history is incomplete, so it may not "
                    "be the original approved baseline."
                ),
            )
        )
    undated = [
        row
        for row in delivery.milestones
        if row.status in {"no_target", "completion_date_missing"}
    ]
    if undated:
        issues.append(
            DataQualityIssue(
                code="milestone_delivery_dates_missing",
                severity="info",
                message=(
                    f"{len(undated)} milestone(s) have no target or completion date, so their "
                    "delivery variance cannot be calculated."
                ),
            )
        )

    quote_linkage = _quote_linkage(
        project, inputs, details_visible=finance_details_visible, issues=issues
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
        delivery=delivery,
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
