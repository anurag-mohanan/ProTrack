"""Quote-to-Delivery management report.

Aggregates ``ProjectEngineeringMetrics`` (the project page payload) over a filtered
population. No hour, variance or delivery rule is re-implemented here; this module
only selects projects, sums the shared per-project values and counts statuses.

Populations
-----------
* ``completed`` (historical): status Completed with ``completed_at`` inside the
  period — the Engineering Performance population (cancelled/deleted excluded).
* ``active`` (operational): status Planning, In progress or On hold as of today;
  the period does not apply. Delivery is judged against current target dates.

The delivery section always shows both: historical results for the completed
population and current overdue work for the active population, never mixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from statistics import median
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    PLANNED_STAGES,
    ExecutionStatus,
    ProjectClassification,
    ProjectStage,
)
from app.models.models import Project
from app.schemas.engineering_metrics import ProjectEngineeringMetrics
from app.schemas.engineering_performance import KpiDefinition, PerformanceDataWarning
from app.schemas.quote_to_delivery import (
    QtdDelivery,
    QtdHistoricalDelivery,
    QtdOperationalDelivery,
    QtdPeriod,
    QtdPopulation,
    QtdProjectPage,
    QtdProjectRow,
    QtdStageRow,
    QtdStageSection,
    QtdSummary,
    QuoteToDeliveryReport,
)
from app.services.delivery_variance_service import SIGN_CONVENTION, stage_label
from app.services.engineering_metrics_service import (
    STAGE_SOURCE,
    build_engineering_metrics_batch,
)
from app.services.reporting.engineering_performance import (
    PerformanceFilters,
    _apply_filters,
    _completed_query,
    _fy_start_month,
    _lookup_names,
)
from app.services.reporting.periods import financial_period_bounds

ZERO = Decimal("0")
HUNDRED = Decimal("100")
METRICS_CHUNK = 500

OPEN_STATUSES = (
    ExecutionStatus.planning,
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
)
APPROVED_ESTIMATE_SOURCES = {"stage_estimates", "milestone_hours"}
ATTRIBUTED_STATUSES = {"complete", "no_hours"}

CLASSIFICATION_LABELS = {
    ProjectClassification.full_design.value: "Full design",
    ProjectClassification.small_task.value: "Small task",
    ProjectClassification.unclassified.value: "Unclassified",
}

POPULATION_LABELS = {
    "completed": (
        "Completed projects",
        "Projects with status Completed whose actual completion date (completed_at) falls in "
        "the selected period.",
    ),
    "active": (
        "Open projects",
        "Projects currently in Planning, In progress or On hold, as of today. The period "
        "filter does not apply; delivery uses current target dates.",
    ),
}

SUMMARY_SEGMENTS = {"over_estimate", "under_estimate", "on_estimate", "not_comparable", "metrics_incomplete"}
STAGE_SEGMENTS = {"stage_eligible", "stage_over", "stage_missing_attribution", "stage_no_estimate"}
HISTORICAL_SEGMENTS = {"delivered_on_or_before", "delivered_after", "delivery_not_evaluable"}
OPERATIONAL_SEGMENTS = {"overdue_milestones", "past_target", "no_target"}
SEGMENTS = SUMMARY_SEGMENTS | STAGE_SEGMENTS | HISTORICAL_SEGMENTS | OPERATIONAL_SEGMENTS

SORT_KEYS = {
    "code",
    "customer",
    "status",
    "quoted_hours",
    "current_estimate_hours",
    "actual_hours",
    "variance_hours",
    "utilization_percent",
    "actual_completion_date",
    "current_target_date",
    "delivery_variance_days",
}
DEFAULT_SORT = {"completed": "-actual_completion_date", "active": "current_target_date"}

STAGE_ELIGIBILITY_RULE = (
    "A project counts for a stage only when it has an approved estimate for that stage, its "
    "actual hours are known, and every one of its timesheet hours is attributed to a stage "
    "(or none are booked yet). Stage estimates are never inferred and unattributed hours are "
    "never allocated."
)

HISTORICAL_RULE = (
    "Completed projects in the period (actual completion date) with an original approved "
    "baseline completion date. Projects measured only against an unverified baseline or a due "
    "date are excluded and counted separately; revised targets are never used as the original "
    "commitment."
)

OPERATIONAL_RULE = (
    "Open projects (Planning, In progress, On hold) as of today, judged against their current "
    "target date (due date, else current baseline). The period filter does not apply."
)

EMPTY_MESSAGES = {
    "completed": "No projects were completed during the selected period.",
    "active": "No open projects match the selected filters.",
}

DEFINITIONS = [
    KpiDefinition(
        key="eligible_projects",
        label="Eligible projects",
        definition=(
            "Completed population: status Completed with an actual completion date in the "
            "period. Open population: Planning, In progress or On hold today. Cancelled and "
            "deleted projects are never included."
        ),
    ),
    KpiDefinition(
        key="quoted_hours_total",
        label="Original quoted hours",
        definition=(
            "Sum of the project's quoted hours, over projects that have quoted hours. Never "
            "added to approved estimate totals."
        ),
    ),
    KpiDefinition(
        key="current_estimate_total",
        label="Current approved estimate",
        definition=(
            "Sum of the current approved estimate (approved stage estimates including approved "
            "revisions, else milestone planned hours) over projects that have one. Projects "
            "whose only estimate is quoted hours are excluded and counted under estimate source."
        ),
    ),
    KpiDefinition(
        key="actual_hours_total",
        label="Actual hours",
        definition=(
            "Sum of approved timesheet hours over projects whose actual hours are known. "
            "Completed projects with no approved hours are 'missing', not zero."
        ),
    ),
    KpiDefinition(
        key="variance_hours",
        label="Aggregate variance",
        definition=(
            "Σ actual − Σ current approved estimate over comparable projects only (approved "
            "estimate above zero and known actual hours). Positive means over estimate. For open "
            "projects this is consumption to date, not a forecast."
        ),
    ),
    KpiDefinition(
        key="utilization_percent",
        label="Utilization",
        definition=(
            "Σ actual ÷ Σ current approved estimate × 100 over comparable projects — never an "
            "average of project percentages."
        ),
    ),
    KpiDefinition(
        key="over_under",
        label="Over / under estimate",
        definition=(
            "Comparable projects whose actual hours are above / below their current approved "
            "estimate. Projects that are not comparable are counted separately."
        ),
    ),
    KpiDefinition(
        key="metrics_incomplete",
        label="Missing or incomplete metrics",
        definition=(
            "Unavailable: no estimate or actual hours missing. Limited: calculated, but the "
            "project has data-quality warnings (for example partial stage attribution). "
            "Incomplete data is not a risk rating."
        ),
    ),
    KpiDefinition(
        key="stage_rows",
        label="Stage comparison",
        definition=STAGE_ELIGIBILITY_RULE,
    ),
    KpiDefinition(
        key="historical_delivery",
        label="Historical delivery",
        definition=HISTORICAL_RULE + " Variance days = actual completion − original baseline.",
    ),
    KpiDefinition(
        key="operational_delivery",
        label="Current overdue work",
        definition=OPERATIONAL_RULE
        + " A milestone is overdue when it is not completed and its current target date has passed.",
    ),
    KpiDefinition(
        key="delivery_variance_days",
        label="Delivery variance (table)",
        definition=(
            "Shown only for completed projects measured against an original approved baseline; "
            "blank otherwise so unreliable references are not presented as results."
        ),
    ),
]


@dataclass
class QtdFilters:
    base: PerformanceFilters
    population: str = "completed"
    classification: ProjectClassification | None = None
    status: ExecutionStatus | None = None


@dataclass
class QtdTableOptions:
    search: str | None = None
    segment: str | None = None
    stage: str | None = None
    sort: str | None = None
    page: int = 1
    page_size: int | None = 25


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _ratio(actual: Decimal, estimate: Decimal) -> Decimal | None:
    if estimate <= 0:
        return None
    return _q(actual / estimate * HUNDRED)


def validate_options(filters: QtdFilters, options: QtdTableOptions) -> None:
    if filters.population not in POPULATION_LABELS:
        raise ValueError("population must be 'completed' or 'active'")
    if filters.status is not None:
        allowed = OPEN_STATUSES if filters.population == "active" else (ExecutionStatus.completed,)
        if filters.status not in allowed:
            raise ValueError(
                "status must be one of: " + ", ".join(s.value for s in allowed)
                + f" for the {filters.population} population"
            )
    if options.segment is not None:
        if options.segment not in SEGMENTS:
            raise ValueError(f"segment must be one of: {', '.join(sorted(SEGMENTS))}")
        if options.segment in HISTORICAL_SEGMENTS and filters.population != "completed":
            raise ValueError("Historical delivery segments require the completed population")
        if options.segment in OPERATIONAL_SEGMENTS and filters.population != "active":
            raise ValueError("Current overdue segments require the open population")
        if options.segment in STAGE_SEGMENTS:
            if options.stage is None:
                raise ValueError("Stage segments require a stage")
            if options.stage not in {s.value for s in ProjectStage}:
                raise ValueError("Unknown stage")
    if options.sort is not None and options.sort.lstrip("-") not in SORT_KEYS:
        raise ValueError(f"sort must be one of: {', '.join(sorted(SORT_KEYS))} (prefix '-' to reverse)")


def _extra_filters(stmt, filters: QtdFilters):
    if filters.classification is not None:
        stmt = stmt.where(Project.project_classification == filters.classification)
    return stmt


def _active_query(filters: QtdFilters):
    statuses = (filters.status,) if filters.status is not None else OPEN_STATUSES
    stmt = select(Project).where(
        Project.execution_status.in_(statuses),
        Project.is_deleted.is_(False),
    )
    return _extra_filters(_apply_filters(stmt, filters.base), filters)


def _completed_population(filters: QtdFilters, start: date, end: date):
    return _extra_filters(_completed_query(filters.base, start, end), filters)


def _metrics(db: Session, projects: list[Project], today: date) -> dict[UUID, ProjectEngineeringMetrics]:
    result: dict[UUID, ProjectEngineeringMetrics] = {}
    for offset in range(0, len(projects), METRICS_CHUNK):
        result.update(
            build_engineering_metrics_batch(
                db, projects[offset : offset + METRICS_CHUNK], finance_details_visible=False, today=today
            )
        )
    return result


def is_comparable(metrics: ProjectEngineeringMetrics) -> bool:
    estimate = metrics.estimate.current_estimate_hours
    return (
        metrics.estimate.estimate_source in APPROVED_ESTIMATE_SOURCES
        and estimate is not None
        and estimate > 0
        and metrics.actual.total_hours is not None
    )


def _summary(items: list[ProjectEngineeringMetrics]) -> QtdSummary:
    summary = QtdSummary(eligible_projects=len(items))
    quoted = ZERO
    estimate_total = ZERO
    actual_total = ZERO
    comparable_estimate = ZERO
    comparable_actual = ZERO
    sources: dict[str, int] = {}
    for m in items:
        sources[m.estimate.estimate_source] = sources.get(m.estimate.estimate_source, 0) + 1
        if m.estimate.quoted_hours is not None:
            quoted += m.estimate.quoted_hours
            summary.projects_with_quoted_hours += 1
        if (
            m.estimate.estimate_source in APPROVED_ESTIMATE_SOURCES
            and m.estimate.current_estimate_hours is not None
        ):
            estimate_total += m.estimate.current_estimate_hours
            summary.projects_with_current_estimate += 1
        if m.actual.total_hours is not None:
            actual_total += m.actual.total_hours
            summary.projects_with_actual_hours += 1
        if m.actual.status == "missing":
            summary.projects_actual_missing += 1
        if m.data_quality_status == "unavailable":
            summary.projects_metrics_unavailable += 1
        elif m.data_quality_status == "available_with_limitations":
            summary.projects_metrics_limited += 1
        if is_comparable(m):
            est = m.estimate.current_estimate_hours or ZERO
            act = m.actual.total_hours or ZERO
            comparable_estimate += est
            comparable_actual += act
            summary.comparable_projects += 1
            if act > est:
                summary.projects_over_estimate += 1
            elif act < est:
                summary.projects_under_estimate += 1
            else:
                summary.projects_on_estimate += 1
        else:
            summary.projects_not_comparable += 1
    summary.quoted_hours_total = _q(quoted)
    summary.current_estimate_total = _q(estimate_total)
    summary.actual_hours_total = _q(actual_total)
    summary.comparable_estimate_hours = _q(comparable_estimate)
    summary.comparable_actual_hours = _q(comparable_actual)
    summary.estimate_source_counts = sources
    if summary.comparable_projects:
        summary.variance_hours = _q(comparable_actual - comparable_estimate)
        summary.utilization_percent = _ratio(comparable_actual, comparable_estimate)
    return summary


def _stage_row(metrics: ProjectEngineeringMetrics, key: str):
    for row in metrics.stage_attribution.rows:
        if row.key == key:
            return row
    return None


def stage_eligible(metrics: ProjectEngineeringMetrics, key: str) -> bool:
    row = _stage_row(metrics, key)
    return (
        row is not None
        and row.has_approved_estimate
        and row.actual_hours is not None
        and metrics.stage_attribution.status in ATTRIBUTED_STATUSES
    )


def _stage_segment(metrics: ProjectEngineeringMetrics, key: str, segment: str) -> bool:
    row = _stage_row(metrics, key)
    if row is None:
        return False
    eligible = stage_eligible(metrics, key)
    if segment == "stage_eligible":
        return eligible
    if segment == "stage_over":
        return eligible and (row.actual_hours or ZERO) > (row.current_estimate_hours or ZERO)
    if segment == "stage_missing_attribution":
        return row.has_approved_estimate and not eligible
    return not row.has_approved_estimate


def _stages(items: list[ProjectEngineeringMetrics]) -> QtdStageSection:
    present = {row.key for m in items for row in m.stage_attribution.rows}
    rows: list[QtdStageRow] = []
    for stage in ProjectStage:
        if stage.value not in present:
            continue
        key = stage.value
        in_plan = [m for m in items if _stage_row(m, key) is not None]
        eligible = [m for m in in_plan if stage_eligible(m, key)]
        estimate = sum((_stage_row(m, key).current_estimate_hours or ZERO for m in eligible), ZERO)
        actual = sum((_stage_row(m, key).actual_hours or ZERO for m in eligible), ZERO)
        without_estimate = sum(1 for m in in_plan if not _stage_row(m, key).has_approved_estimate)
        missing = sum(1 for m in in_plan if _stage_segment(m, key, "stage_missing_attribution"))
        over = sum(1 for m in in_plan if _stage_segment(m, key, "stage_over"))
        explanation = None
        if without_estimate == len(in_plan):
            explanation = "No project in this population has an approved estimate for this stage."
            if stage not in PLANNED_STAGES:
                explanation += (
                    " Approved stage estimates cover Blockout, Intermediate Design and Final "
                    "Design only."
                )
        elif not eligible:
            explanation = (
                "Stage actual hours cannot be stated: timesheet hours are not fully linked to "
                "staged milestones for any project with an estimate."
            )
        elif missing:
            explanation = (
                f"{missing} project(s) with an estimate are excluded because their hours are not "
                "fully attributed to stages."
            )
        rows.append(
            QtdStageRow(
                key=key,
                label=stage_label(stage) or key,
                projects_in_plan=len(in_plan),
                eligible_projects=len(eligible),
                estimate_hours=_q(estimate) if eligible else None,
                actual_hours=_q(actual) if eligible else None,
                variance_hours=_q(actual - estimate) if eligible else None,
                utilization_percent=_ratio(actual, estimate) if eligible else None,
                projects_over_estimate=over,
                projects_missing_attribution=missing,
                projects_without_estimate=without_estimate,
                explanation=explanation,
            )
        )
    return QtdStageSection(rows=rows, eligibility_rule=STAGE_ELIGIBILITY_RULE, source=STAGE_SOURCE)


def historically_evaluable(metrics: ProjectEngineeringMetrics) -> bool:
    delivery = metrics.delivery.project
    return (
        delivery.reference_source == "original_baseline"
        and delivery.schedule_variance_days is not None
    )


def _historical(
    items: list[ProjectEngineeringMetrics], completed_without_date: int
) -> QtdHistoricalDelivery:
    evaluable = [m for m in items if historically_evaluable(m)]
    days = [m.delivery.project.schedule_variance_days for m in evaluable]
    excluded = [m.delivery.project.reference_source for m in items if not historically_evaluable(m)]
    return QtdHistoricalDelivery(
        population_rule=HISTORICAL_RULE,
        completed_projects=len(items),
        eligible_projects=len(evaluable),
        on_or_before_baseline=sum(1 for d in days if d is not None and d <= 0),
        after_baseline=sum(1 for d in days if d is not None and d > 0),
        average_variance_days=round(sum(days) / len(days), 1) if days else None,  # type: ignore[arg-type]
        median_variance_days=float(median(days)) if days else None,  # type: ignore[type-var]
        excluded_baseline_unverified=excluded.count("baseline_unverified"),
        excluded_due_date_only=excluded.count("current_due_date"),
        excluded_no_reference=excluded.count("none") + excluded.count("original_baseline"),
        completed_without_completion_date=completed_without_date,
    )


def _operational(items: list[ProjectEngineeringMetrics], today: date) -> QtdOperationalDelivery:
    return QtdOperationalDelivery(
        population_rule=OPERATIONAL_RULE,
        as_of=today,
        active_projects=len(items),
        projects_with_overdue_milestones=sum(1 for m in items if m.milestones.open_overdue > 0),
        overdue_milestones=sum(m.milestones.open_overdue for m in items),
        projects_past_current_target=sum(1 for m in items if m.delivery.project.status == "overdue"),
        projects_without_current_target=sum(
            1 for m in items if m.delivery.project.status == "no_target"
        ),
        projects_without_original_baseline=sum(
            1 for m in items if m.delivery.project.reference_source != "original_baseline"
        ),
    )


def _in_segment(metrics: ProjectEngineeringMetrics, options: QtdTableOptions) -> bool:
    segment = options.segment
    if segment is None:
        return True
    comparable = is_comparable(metrics)
    actual = metrics.actual.total_hours or ZERO
    estimate = metrics.estimate.current_estimate_hours or ZERO
    delivery = metrics.delivery.project
    checks = {
        "over_estimate": lambda: comparable and actual > estimate,
        "under_estimate": lambda: comparable and actual < estimate,
        "on_estimate": lambda: comparable and actual == estimate,
        "not_comparable": lambda: not comparable,
        "metrics_incomplete": lambda: metrics.data_quality_status != "available",
        "delivered_on_or_before": lambda: historically_evaluable(metrics)
        and (delivery.schedule_variance_days or 0) <= 0,
        "delivered_after": lambda: historically_evaluable(metrics)
        and (delivery.schedule_variance_days or 0) > 0,
        "delivery_not_evaluable": lambda: not historically_evaluable(metrics),
        "overdue_milestones": lambda: metrics.milestones.open_overdue > 0,
        "past_target": lambda: delivery.status == "overdue",
        "no_target": lambda: delivery.status == "no_target",
    }
    if segment in STAGE_SEGMENTS:
        return _stage_segment(metrics, options.stage or "", segment)
    return checks[segment]()


def _row(project: Project, metrics: ProjectEngineeringMetrics, names: dict) -> QtdProjectRow:
    delivery = metrics.delivery.project
    classification = (
        project.project_classification.value if project.project_classification is not None else None
    )
    reliable = historically_evaluable(metrics)
    return QtdProjectRow(
        project_id=project.id,
        code=project.code,
        tool_number=project.tool_number,
        part_description=project.part_description,
        customer_name=names["customers"].get(project.customer_id),
        classification=classification,
        classification_label=CLASSIFICATION_LABELS.get(classification or ""),
        project_type_name=names["types"].get(project.project_type_id) if project.project_type_id else None,
        execution_status=metrics.execution_status,
        design_leader_name=names["users"].get(project.design_leader_id) if project.design_leader_id else None,
        designer_name=names["users"].get(project.designer_id) if project.designer_id else None,
        quoted_hours=metrics.estimate.quoted_hours,
        current_estimate_hours=metrics.estimate.current_estimate_hours,
        estimate_source=metrics.estimate.estimate_source,
        estimate_source_label=metrics.estimate.estimate_source_label,
        actual_hours=metrics.actual.total_hours,
        actual_status=metrics.actual.status,
        variance_hours=metrics.variance_hours.value,
        utilization_percent=metrics.utilization_percent.value,
        comparable=is_comparable(metrics),
        original_baseline_completion_date=delivery.original_baseline_completion_date,
        current_baseline_completion_date=delivery.current_baseline_completion_date,
        current_target_date=delivery.current_target_date,
        delivery_reference_source=delivery.reference_source,
        actual_completion_date=delivery.actual_completion_date,
        delivery_variance_days=delivery.schedule_variance_days if reliable else None,
        delivery_status=delivery.status,
        days_overdue=delivery.days_overdue,
        open_overdue_milestones=metrics.milestones.open_overdue,
        stage_attribution_status=metrics.stage_attribution.status,
        data_quality_status=metrics.data_quality_status,
        data_quality_issues=[issue.code for issue in metrics.issues],
        data_quality_warnings=[issue.message for issue in metrics.issues if issue.severity == "warning"],
    )


def _matches_search(row: QtdProjectRow, needle: str) -> bool:
    haystack = (row.code, row.tool_number, row.part_description, row.customer_name)
    return any(value and needle in value.lower() for value in haystack)


def _sort_rows(rows: list[QtdProjectRow], sort: str) -> list[QtdProjectRow]:
    key = sort.lstrip("-")
    reverse = sort.startswith("-")
    attr = {"customer": "customer_name", "status": "execution_status"}.get(key, key)

    def value(row: QtdProjectRow):
        raw = getattr(row, attr)
        return raw.lower() if isinstance(raw, str) else raw

    present = [r for r in rows if value(r) is not None]
    missing = [r for r in rows if value(r) is None]
    present.sort(key=lambda r: (value(r), (r.code or "").lower()), reverse=reverse)
    missing.sort(key=lambda r: (r.code or "").lower())
    return present + missing


def _completed_without_date(db: Session, filters: QtdFilters) -> list[Project]:
    stmt = select(Project).where(
        Project.execution_status == ExecutionStatus.completed,
        Project.completed_at.is_(None),
        Project.is_deleted.is_(False),
    )
    return list(db.scalars(_extra_filters(_apply_filters(stmt, filters.base), filters)).all())


def _warnings(
    selected: list[ProjectEngineeringMetrics], undated: list[Project], population: str
) -> list[PerformanceDataWarning]:
    warnings: list[PerformanceDataWarning] = []

    def codes(items) -> list[str]:
        return sorted(m.code or m.tool_number or str(m.project_id) for m in items)

    if undated:
        warnings.append(
            PerformanceDataWarning(
                code="completed_without_date",
                message=(
                    f"{len(undated)} completed project(s) have no actual completion date, so they "
                    "are not in any period and not in historical delivery results."
                ),
                project_codes=sorted(p.code or p.tool_number or str(p.id) for p in undated),
            )
        )
    missing = [m for m in selected if m.actual.status == "missing"]
    if missing:
        warnings.append(
            PerformanceDataWarning(
                code="actual_hours_missing",
                message=(
                    f"{len(missing)} project(s) have completed work but no timesheet hours; their "
                    "actual hours are missing (not zero) and they are excluded from hour totals."
                ),
                project_codes=codes(missing),
            )
        )
    quoted_only = [m for m in selected if m.estimate.estimate_source == "quoted_hours"]
    if quoted_only:
        warnings.append(
            PerformanceDataWarning(
                code="estimate_from_quoted_hours",
                message=(
                    f"{len(quoted_only)} project(s) have no approved estimate, only quoted hours; "
                    "they are excluded from approved-estimate totals, variance and utilization."
                ),
                project_codes=codes(quoted_only),
            )
        )
    if population == "active":
        warnings.append(
            PerformanceDataWarning(
                code="active_consumption_to_date",
                message=(
                    "Open projects: actual hours, variance and utilization are hours consumed to "
                    "date against the approved estimate, not a forecast of the final result."
                ),
            )
        )
    return warnings


def build_quote_to_delivery(
    db: Session,
    filters: QtdFilters,
    options: QtdTableOptions,
    *,
    filter_labels: dict[str, str | None] | None = None,
    today: date | None = None,
) -> QuoteToDeliveryReport:
    """Read-only. ``options.page_size=None`` returns every matching row (export)."""
    validate_options(filters, options)
    today = today or date.today()
    fy_month = _fy_start_month(db)
    start, end, label = financial_period_bounds(
        filters.base.period_type,
        anchor=filters.base.anchor,
        fy_start_month=fy_month,
        start_date=filters.base.start_date,
        end_date=filters.base.end_date,
    )

    completed = list(
        db.scalars(_completed_population(filters, start, end).order_by(Project.completed_at)).all()
    )
    active = list(db.scalars(_active_query(filters).order_by(Project.code)).all())
    metrics = _metrics(db, completed + active, today)
    completed_metrics = [metrics[p.id] for p in completed]
    active_metrics = [metrics[p.id] for p in active]
    undated = _completed_without_date(db, filters)

    selected_projects = completed if filters.population == "completed" else active
    selected = completed_metrics if filters.population == "completed" else active_metrics

    names = _lookup_names(db, selected_projects)
    rows = [
        _row(project, metrics[project.id], names)
        for project in selected_projects
        if _in_segment(metrics[project.id], options)
    ]
    search = (options.search or "").strip()
    if search:
        needle = search.lower()
        rows = [row for row in rows if _matches_search(row, needle)]
    sort = options.sort or DEFAULT_SORT[filters.population]
    rows = _sort_rows(rows, sort)
    total = len(rows)
    if options.page_size is None:
        page, page_size, pages, items = 1, total, 1 if total else 0, rows
    else:
        page_size = options.page_size
        pages = math.ceil(total / page_size) if total else 0
        page = max(1, options.page)
        items = rows[(page - 1) * page_size : page * page_size]

    pop_label, pop_basis = POPULATION_LABELS[filters.population]
    return QuoteToDeliveryReport(
        population=QtdPopulation(
            key=filters.population,  # type: ignore[arg-type]
            label=pop_label,
            date_basis=pop_basis,
            as_of=today,
        ),
        period=QtdPeriod(
            period_type=filters.base.period_type,
            label=label,
            start_date=start,
            end_date=end,
            financial_year_start_month=fy_month,
            applies_to=(
                "Completed population and historical delivery: actual completion date. "
                "Not applied to open projects or current overdue work."
            ),
        ),
        filters=filter_labels or {},
        summary=_summary(selected),
        projects=QtdProjectPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            search=search or None,
            segment=options.segment,
            stage=options.stage,
            sort=sort,
        ),
        stages=_stages(selected),
        delivery=QtdDelivery(
            sign_convention=SIGN_CONVENTION,
            historical=_historical(completed_metrics, len(undated)),
            operational=_operational(active_metrics, today),
        ),
        warnings=_warnings(selected, undated, filters.population),
        definitions=DEFINITIONS,
        empty_message=EMPTY_MESSAGES[filters.population] if not selected else None,
        generated_at=datetime.now(timezone.utc),
    )
