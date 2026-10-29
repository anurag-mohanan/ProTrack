"""Engineering Performance report — the single source for completed-project KPIs.

Completed-project rule
----------------------
A project counts in a period only when ALL of these hold:
* ``execution_status`` is ``completed`` (cancelled projects never count);
* it has an actual completion date (``completed_at``) inside the period;
* it is not deleted (archived completed projects are included unless excluded).

Completed projects without an actual completion date are never guessed into a
period; they are listed as a data-quality warning instead.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    PLANNED_STAGE_LABELS,
    PLANNED_STAGES,
    ExecutionStatus,
    MilestoneStatus,
    ProjectStage,
)
from app.models.foundation import CompanySettings
from app.models.models import (
    Customer,
    Milestone,
    Project,
    ProjectTemplate,
    ProjectType,
    Team,
    User,
)
from app.schemas.engineering_performance import (
    Breakdown,
    BreakdownRow,
    EngineeringPerformanceReport,
    KpiDefinition,
    PerformanceDataWarning,
    PerformancePeriod,
    PerformanceSummary,
    ProjectPerformanceRow,
    StagePerformance,
    StagePerformanceRow,
)
from app.services.engineering_metrics_service import (
    StageHourBuckets,
    resolve_estimate,
    stage_estimates_by_project,
    stage_hour_buckets,
)
from app.services.project_calculation_service import batch_calculate_hours
from app.services.reporting.periods import financial_period_bounds

EMPTY_MESSAGE = "No projects were completed during the selected period."

_SKIPPED_MILESTONES = {MilestoneStatus.cancelled, MilestoneStatus.not_applicable}

DIMENSION_LABELS = {
    "customer": "Customer",
    "end_customer": "End Customer",
    "team": "Team",
    "design_leader": "Design Leader / PM",
    "designer": "Designer",
    "surfacer": "Surfacer",
    "project_type": "Project Type",
    "template": "Template",
    "period": "Completion Period",
}

DEFINITIONS = [
    KpiDefinition(
        key="projects_completed",
        label="Projects completed",
        definition=(
            "Projects with status Completed and an actual completion date inside the period. "
            "Cancelled and deleted projects are excluded."
        ),
    ),
    KpiDefinition(
        key="planned_hours",
        label="Planned hours",
        definition=(
            "Current basis: the current approved stage estimates (original plus approved "
            "revisions); projects without stage estimates use milestone planned hours, then "
            "quoted hours. Original basis: the stage estimates entered at creation; projects "
            "without stage estimates use quoted hours."
        ),
    ),
    KpiDefinition(
        key="actual_hours",
        label="Actual hours",
        definition="All non-deleted timesheet hours booked to the project (any date).",
    ),
    KpiDefinition(
        key="eac_hours",
        label="Estimate at completion (EAC)",
        definition="For completed projects EAC equals actual hours; no work remains.",
    ),
    KpiDefinition(
        key="variance",
        label="Hours variance",
        definition=(
            "Actual minus planned hours; positive means over plan. Variance % divides by planned "
            "hours and is blank when nothing was planned. Projects without a plan are excluded "
            "from planned and variance totals."
        ),
    ),
    KpiDefinition(
        key="on_time_rate",
        label="On-time delivery",
        definition=(
            "A project is on time when its actual completion date is on or before its baseline "
            "completion date. Projects created before baselines existed use their due date "
            "(shown as 'legacy due date'). Projects with neither are excluded from the rate."
        ),
    ),
    KpiDefinition(
        key="milestone_on_time",
        label="Milestone on-time rate",
        definition=(
            "Completed milestones finished on or before their baseline finish date (or due date "
            "for legacy milestones), divided by completed milestones that have such a date. "
            "Cancelled and not-applicable milestones are excluded."
        ),
    ),
    KpiDefinition(
        key="stage_hours",
        label="Stage hours",
        definition=(
            "Blockout, Intermediate Design and Final Design. Planned hours come from stage "
            "estimates; actual hours are timesheet hours booked to milestones of that stage. "
            "Only projects with stage estimates are included in stage rows."
        ),
    ),
]


@dataclass
class PerformanceFilters:
    period_type: str = "monthly"
    anchor: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    plan_basis: str = "current"
    customer_id: UUID | None = None
    end_customer_id: UUID | None = None
    team_ids: frozenset[UUID] | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    project_type_id: UUID | None = None
    template_family_id: UUID | None = None
    include_archived: bool = True
    visibility_clause: object | None = None


@dataclass
class _ProjectFacts:
    project: Project
    completed_on: date
    original: Decimal | None
    current: Decimal | None
    plan_source: str
    actual: Decimal
    stage_original: dict[ProjectStage, Decimal] = field(default_factory=dict)
    stage_current: dict[ProjectStage, Decimal] = field(default_factory=dict)
    stage_actual: dict[ProjectStage, Decimal] = field(default_factory=dict)
    unstaged_actual: Decimal = Decimal("0")
    reference: date | None = None
    reference_source: str = "none"
    milestones_total: int = 0
    milestones_completed: int = 0
    milestones_on_time: int = 0
    milestones_dated: int = 0

    @property
    def stage_planned(self) -> bool:
        return bool(self.stage_original)

    def planned(self, basis: str) -> Decimal | None:
        return self.original if basis == "original" else self.current

    @property
    def on_time(self) -> bool | None:
        if self.reference is None:
            return None
        return self.completed_on <= self.reference

    @property
    def days_late(self) -> int | None:
        if self.reference is None:
            return None
        return max((self.completed_on - self.reference).days, 0)


def _f(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _pct(numerator: Decimal, denominator: Decimal) -> float | None:
    if denominator <= 0:
        return None
    return float((numerator / denominator * Decimal("100")).quantize(Decimal("0.01")))


def _rate(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total * 100, 2)


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    full = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full or user.email


def _fy_start_month(db: Session) -> int:
    value = db.scalar(select(CompanySettings.financial_year_start_month).limit(1))
    return int(value) if value else 4


def _completed_query(filters: PerformanceFilters, start: date, end: date):
    window_start = datetime.combine(start, time.min)
    window_end = datetime.combine(end + timedelta(days=1), time.min)
    stmt = select(Project).where(
        Project.execution_status == ExecutionStatus.completed,
        Project.completed_at.is_not(None),
        Project.completed_at >= window_start,
        Project.completed_at < window_end,
        Project.is_deleted.is_(False),
    )
    return _apply_filters(stmt, filters)


def _apply_filters(stmt, filters: PerformanceFilters):
    if not filters.include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    if filters.visibility_clause is not None:
        stmt = stmt.where(filters.visibility_clause)
    if filters.team_ids is not None:
        if not filters.team_ids:
            return stmt.where(Project.id.is_(None))
        stmt = stmt.where(Project.team_id.in_(filters.team_ids))
    if filters.customer_id is not None:
        stmt = stmt.where(Project.customer_id == filters.customer_id)
    if filters.end_customer_id is not None:
        stmt = stmt.where(Project.end_customer_id == filters.end_customer_id)
    if filters.design_leader_id is not None:
        stmt = stmt.where(Project.design_leader_id == filters.design_leader_id)
    if filters.designer_id is not None:
        stmt = stmt.where(Project.designer_id == filters.designer_id)
    if filters.surfacer_id is not None:
        stmt = stmt.where(Project.surfacer_id == filters.surfacer_id)
    if filters.project_type_id is not None:
        stmt = stmt.where(Project.project_type_id == filters.project_type_id)
    if filters.template_family_id is not None:
        family_ids = select(ProjectTemplate.id).where(
            (ProjectTemplate.template_family_id == filters.template_family_id)
            | (ProjectTemplate.id == filters.template_family_id)
        )
        stmt = stmt.where(Project.project_template_id.in_(family_ids))
    return stmt


def _milestones(db: Session, project_ids: list[UUID]) -> dict[UUID, list[Milestone]]:
    result: dict[UUID, list[Milestone]] = defaultdict(list)
    if not project_ids:
        return result
    for row in db.scalars(select(Milestone).where(Milestone.project_id.in_(project_ids))):
        result[row.project_id].append(row)
    return result


def _build_facts(db: Session, projects: list[Project]) -> list[_ProjectFacts]:
    ids = [project.id for project in projects]
    hours = batch_calculate_hours(db, projects)
    estimates = stage_estimates_by_project(db, ids)
    buckets = stage_hour_buckets(db, ids)
    milestones = _milestones(db, ids)
    facts: list[_ProjectFacts] = []
    for project in projects:
        milestone_rows = milestones.get(project.id, [])
        estimate = resolve_estimate(project, estimates.get(project.id, []), milestone_rows)
        bucket = buckets.get(project.id, StageHourBuckets())
        stage_actual = dict(bucket.stages)
        unstaged = bucket.unattributed

        if project.baseline_completion_date is not None:
            reference, reference_source = project.baseline_completion_date, "baseline"
        elif project.due_date is not None:
            reference, reference_source = project.due_date, "legacy_due_date"
        else:
            reference, reference_source = None, "none"

        counted = [m for m in milestone_rows if m.status not in _SKIPPED_MILESTONES]
        completed = [m for m in counted if m.status == MilestoneStatus.completed]
        on_time = 0
        dated = 0
        for m in completed:
            finished = m.completed_date or (m.completed_at.date() if m.completed_at else None)
            target = m.baseline_finish_date or m.due_date
            if finished is None or target is None:
                continue
            dated += 1
            if finished <= target:
                on_time += 1

        facts.append(
            _ProjectFacts(
                project=project,
                completed_on=project.completed_at.date(),
                original=estimate.original,
                current=estimate.current,
                plan_source=estimate.source,
                actual=Decimal(str(hours[project.id].actual)),
                stage_original=estimate.stage_original,
                stage_current=estimate.stage_current,
                stage_actual=stage_actual,
                unstaged_actual=unstaged,
                reference=reference,
                reference_source=reference_source,
                milestones_total=len(counted),
                milestones_completed=len(completed),
                milestones_on_time=on_time,
                milestones_dated=dated,
            )
        )
    return facts


def _aggregate_row(key: str, label: str, items: list[_ProjectFacts], basis: str) -> BreakdownRow:
    planned_items = [item for item in items if item.planned(basis) is not None]
    planned = sum((item.planned(basis) for item in planned_items), Decimal("0"))  # type: ignore[misc]
    actual_planned = sum((item.actual for item in planned_items), Decimal("0"))
    actual = sum((item.actual for item in items), Decimal("0"))
    evaluable = [item for item in items if item.on_time is not None]
    on_time = sum(1 for item in evaluable if item.on_time)
    variance = actual_planned - planned
    return BreakdownRow(
        key=key,
        label=label,
        projects=len(items),
        planned_hours=_f(planned) or 0.0,
        actual_hours=_f(actual) or 0.0,
        variance_hours=_f(variance) or 0.0,
        variance_percent=_pct(variance, planned),
        on_time_projects=on_time,
        on_time_rate=_rate(on_time, len(evaluable)),
    )


def _period_bucket(day: date, period_type: str, start: date, end: date) -> tuple[str, str]:
    span = (end - start).days
    if period_type == "weekly" or span <= 7:
        return day.isoformat(), day.strftime("%a %d %b")
    if period_type == "monthly" or span <= 62:
        week_start = day - timedelta(days=day.weekday())
        return week_start.isoformat(), f"Week of {week_start.strftime('%d %b')}"
    return day.strftime("%Y-%m"), day.strftime("%b %Y")


def _breakdowns(
    facts: list[_ProjectFacts],
    *,
    basis: str,
    names: dict[str, dict[UUID, str]],
    period_type: str,
    start: date,
    end: date,
) -> list[Breakdown]:
    def keyed(dimension: str, item: _ProjectFacts) -> tuple[str, str]:
        project = item.project
        lookup = {
            "customer": ("customers", project.customer_id),
            "end_customer": ("customers", project.end_customer_id),
            "team": ("teams", project.team_id),
            "design_leader": ("users", project.design_leader_id),
            "designer": ("users", project.designer_id),
            "surfacer": ("users", project.surfacer_id),
            "project_type": ("types", project.project_type_id),
            "template": ("template_families", project.project_template_id),
        }
        if dimension == "period":
            return _period_bucket(item.completed_on, period_type, start, end)
        table, ref = lookup[dimension]
        if ref is None:
            return "none", "Not set"
        if table == "template_families":
            family_key, family_label = names["template_families"].get(ref, (str(ref), "Unknown template"))  # type: ignore[misc]
            return family_key, family_label
        return str(ref), names[table].get(ref, "Unknown")

    result: list[Breakdown] = []
    for dimension, label in DIMENSION_LABELS.items():
        groups: dict[str, list[_ProjectFacts]] = defaultdict(list)
        labels: dict[str, str] = {}
        for item in facts:
            key, text = keyed(dimension, item)
            groups[key].append(item)
            labels[key] = text
        rows = [_aggregate_row(key, labels[key], items, basis) for key, items in groups.items()]
        if dimension == "period":
            rows.sort(key=lambda row: row.key)
        else:
            rows.sort(key=lambda row: (-row.projects, row.label.lower()))
        result.append(Breakdown(dimension=dimension, label=label, rows=rows))  # type: ignore[arg-type]
    return result


def _lookup_names(db: Session, projects: list[Project]) -> dict[str, dict]:
    customer_ids = {p.customer_id for p in projects if p.customer_id} | {
        p.end_customer_id for p in projects if p.end_customer_id
    }
    team_ids = {p.team_id for p in projects if p.team_id}
    user_ids = {
        uid for p in projects for uid in (p.design_leader_id, p.designer_id, p.surfacer_id) if uid
    }
    type_ids = {p.project_type_id for p in projects if p.project_type_id}
    template_ids = {p.project_template_id for p in projects if p.project_template_id}

    def by_id(model, ids, attr="name"):
        if not ids:
            return {}
        return {row.id: getattr(row, attr) for row in db.scalars(select(model).where(model.id.in_(ids)))}

    users = (
        {row.id: _name(row) for row in db.scalars(select(User).where(User.id.in_(user_ids)))}
        if user_ids
        else {}
    )
    families: dict[UUID, tuple[str, str]] = {}
    template_names: dict[UUID, str] = {}
    if template_ids:
        for row in db.scalars(select(ProjectTemplate).where(ProjectTemplate.id.in_(template_ids))):
            family = row.template_family_id or row.id
            families[row.id] = (str(family), row.name)
            template_names[row.id] = f"{row.name} (v{row.version or 1})"
    return {
        "customers": by_id(Customer, customer_ids),
        "teams": by_id(Team, team_ids),
        "users": users,
        "types": by_id(ProjectType, type_ids),
        "template_families": families,
        "templates": template_names,
    }


def _warnings(
    db: Session, filters: PerformanceFilters, facts: list[_ProjectFacts]
) -> list[PerformanceDataWarning]:
    warnings: list[PerformanceDataWarning] = []
    missing = db.scalars(
        _apply_filters(
            select(Project).where(
                Project.execution_status == ExecutionStatus.completed,
                Project.completed_at.is_(None),
                Project.is_deleted.is_(False),
            ),
            filters,
        )
    ).all()
    if missing:
        warnings.append(
            PerformanceDataWarning(
                code="completed_without_date",
                message=(
                    f"{len(missing)} completed project(s) have no actual completion date and are "
                    "not counted in any period. Enter the completion date on each project."
                ),
                project_codes=sorted(p.code or p.tool_number or str(p.id) for p in missing),
            )
        )
    unplanned = [item for item in facts if item.plan_source == "none"]
    if unplanned:
        warnings.append(
            PerformanceDataWarning(
                code="no_planned_hours",
                message=(
                    f"{len(unplanned)} completed project(s) have no planned or quoted hours; they "
                    "are excluded from planned-hours and variance totals."
                ),
                project_codes=sorted(
                    item.project.code or item.project.tool_number or str(item.project.id)
                    for item in unplanned
                ),
            )
        )
    legacy = [item for item in facts if item.reference_source == "legacy_due_date"]
    if legacy:
        warnings.append(
            PerformanceDataWarning(
                code="legacy_due_date",
                message=(
                    f"{len(legacy)} project(s) have no baseline; on-time delivery uses their due "
                    "date instead."
                ),
                project_codes=sorted(
                    item.project.code or item.project.tool_number or str(item.project.id)
                    for item in legacy
                ),
            )
        )
    return warnings


def build_engineering_performance(
    db: Session, filters: PerformanceFilters, *, filter_labels: dict[str, str | None] | None = None
) -> EngineeringPerformanceReport:
    fy_month = _fy_start_month(db)
    start, end, label = financial_period_bounds(
        filters.period_type,
        anchor=filters.anchor,
        fy_start_month=fy_month,
        start_date=filters.start_date,
        end_date=filters.end_date,
    )
    basis = "original" if filters.plan_basis == "original" else "current"
    projects = list(
        db.scalars(_completed_query(filters, start, end).order_by(Project.completed_at)).all()
    )
    facts = _build_facts(db, projects)
    names = _lookup_names(db, projects)

    planned_items = [item for item in facts if item.planned(basis) is not None]
    planned_total = sum((item.planned(basis) for item in planned_items), Decimal("0"))  # type: ignore[misc]
    actual_on_planned = sum((item.actual for item in planned_items), Decimal("0"))
    actual_total = sum((item.actual for item in facts), Decimal("0"))
    variance_total = actual_on_planned - planned_total
    evaluable = [item for item in facts if item.on_time is not None]
    on_time = sum(1 for item in evaluable if item.on_time)
    late_items = [item for item in evaluable if not item.on_time]
    milestones_dated = sum(item.milestones_dated for item in facts)
    milestones_on_time = sum(item.milestones_on_time for item in facts)

    summary = PerformanceSummary(
        projects_completed=len(facts),
        plan_basis=basis,  # type: ignore[arg-type]
        planned_hours=_f(planned_total) or 0.0,
        projects_without_plan=len(facts) - len(planned_items),
        actual_hours=_f(actual_total) or 0.0,
        eac_hours=_f(actual_total) or 0.0,
        variance_hours=_f(variance_total) or 0.0,
        variance_percent=_pct(variance_total, planned_total),
        on_time_projects=on_time,
        late_projects=len(late_items),
        projects_without_reference_date=len(facts) - len(evaluable),
        on_time_rate=_rate(on_time, len(evaluable)),
        average_days_late=(
            round(sum(item.days_late or 0 for item in late_items) / len(late_items), 1)
            if late_items
            else None
        ),
        milestones_total=sum(item.milestones_total for item in facts),
        milestones_completed=sum(item.milestones_completed for item in facts),
        milestones_on_time=milestones_on_time,
        milestone_on_time_rate=_rate(milestones_on_time, milestones_dated),
    )

    staged = [item for item in facts if item.stage_planned]
    stage_rows = []
    for stage in PLANNED_STAGES:
        original = sum((item.stage_original.get(stage, Decimal("0")) for item in staged), Decimal("0"))
        current = sum((item.stage_current.get(stage, Decimal("0")) for item in staged), Decimal("0"))
        actual = sum((item.stage_actual.get(stage, Decimal("0")) for item in staged), Decimal("0"))
        reference = original if basis == "original" else current
        variance = actual - reference
        stage_rows.append(
            StagePerformanceRow(
                stage=stage.value,
                label=PLANNED_STAGE_LABELS[stage],
                projects=len(staged),
                original_hours=_f(original) or 0.0,
                current_hours=_f(current) or 0.0,
                actual_hours=_f(actual) or 0.0,
                variance_hours=_f(variance) or 0.0,
                variance_percent=_pct(variance, reference),
            )
        )
    stage_performance = StagePerformance(
        projects_with_stage_plan=len(staged),
        projects_without_stage_plan=len(facts) - len(staged),
        rows=stage_rows,
        unstaged_actual_hours=_f(sum((item.unstaged_actual for item in staged), Decimal("0"))) or 0.0,
    )

    project_rows = []
    for item in facts:
        project = item.project
        planned = item.planned(basis)
        variance = (item.actual - planned) if planned is not None else None
        project_rows.append(
            ProjectPerformanceRow(
                project_id=project.id,
                code=project.code,
                tool_number=project.tool_number,
                part_description=project.part_description,
                customer_name=names["customers"].get(project.customer_id),
                end_customer_name=names["customers"].get(project.end_customer_id)
                if project.end_customer_id
                else None,
                team_name=names["teams"].get(project.team_id) if project.team_id else None,
                design_leader_name=names["users"].get(project.design_leader_id)
                if project.design_leader_id
                else None,
                designer_name=names["users"].get(project.designer_id) if project.designer_id else None,
                surfacer_name=names["users"].get(project.surfacer_id) if project.surfacer_id else None,
                project_type_name=names["types"].get(project.project_type_id)
                if project.project_type_id
                else None,
                template_name=names["templates"].get(project.project_template_id)
                if project.project_template_id
                else None,
                start_date=project.start_date,
                actual_start_date=project.actual_start_date,
                actual_completion_date=item.completed_on,
                reference_completion_date=item.reference,
                reference_source=item.reference_source,  # type: ignore[arg-type]
                on_time=item.on_time,
                days_late=item.days_late,
                original_planned_hours=_f(item.original),
                current_planned_hours=_f(item.current),
                planned_hours=_f(planned),
                plan_source=item.plan_source,
                actual_hours=_f(item.actual) or 0.0,
                variance_hours=_f(variance),
                variance_percent=_pct(variance, planned) if planned is not None and variance is not None else None,
                stage_planned=item.stage_planned,
                milestones_total=item.milestones_total,
                milestones_completed=item.milestones_completed,
                milestones_on_time=item.milestones_on_time,
            )
        )

    return EngineeringPerformanceReport(
        period=PerformancePeriod(
            period_type=filters.period_type,  # type: ignore[arg-type]
            label=label,
            start_date=start,
            end_date=end,
            financial_year_start_month=fy_month,
        ),
        filters=filter_labels or {},
        summary=summary,
        stage_performance=stage_performance,
        breakdowns=_breakdowns(
            facts, basis=basis, names=names, period_type=filters.period_type, start=start, end=end
        ),
        projects=project_rows,
        warnings=_warnings(db, filters, facts),
        definitions=DEFINITIONS,
        empty_message=EMPTY_MESSAGE if not facts else None,
    )
