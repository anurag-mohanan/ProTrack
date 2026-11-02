"""Prediction inputs built from the shared engineering metrics. No metric is recalculated here.

Predictors work on these plain dataclasses, never on ORM rows, so scenarios can change a copy
of the inputs without any risk of touching project records.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus
from app.models.models import Customer, Project, ProjectType
from app.schemas.engineering_metrics import ProjectEngineeringMetrics
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from app.services.predictive.stats import MIN_SAMPLE
from app.services.reporting.quote_to_delivery import APPROVED_ESTIMATE_SOURCES, OPEN_STATUSES


@dataclass(frozen=True)
class ProjectFacts:
    project_id: UUID
    label: str
    customer_id: UUID | None
    customer_name: str | None
    project_type_id: UUID | None
    project_type_name: str | None
    template_id: UUID | None
    complexity: str | None
    classification: str | None
    team_id: UUID | None
    designer_id: UUID | None
    design_leader_id: UUID | None
    execution_status: str
    start_date: date | None
    start_source: str | None
    committed_date: date | None
    committed_source: str
    current_target: date | None
    target_moved_days: int | None
    completed_on: date | None
    estimate_approved: bool
    estimate_source: str
    quoted_hours: Decimal | None
    original_estimate: Decimal | None
    current_estimate: Decimal | None
    actual_hours: Decimal | None
    actual_status: str
    unapproved_hours: Decimal
    rejected_hours: Decimal
    open_milestones: int
    overdue_milestones: int
    open_without_target: int
    issue_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_open(self) -> bool:
        return self.execution_status in {s.value for s in OPEN_STATUSES}

    def with_changes(self, **changes) -> ProjectFacts:
        return replace(self, **changes)


def project_label(project: Project) -> str:
    parts = [p for p in (project.code, project.tool_number) if p]
    label = " · ".join(dict.fromkeys(parts)) or str(project.id)
    if project.part_description:
        label = f"{label} — {project.part_description[:80]}"
    return label


def _start(project: Project) -> tuple[date | None, str | None]:
    if project.actual_start_date:
        return project.actual_start_date, "actual start"
    if project.start_date:
        return project.start_date, "planned start"
    if project.baseline_start_date:
        return project.baseline_start_date, "baseline start"
    return None, None


def facts_from(project: Project, metrics: ProjectEngineeringMetrics, names: dict, types: dict) -> ProjectFacts:
    delivery = metrics.delivery.project
    committed = delivery.reference_date if delivery.reference_source in ("original_baseline", "baseline_unverified") else None
    start, start_source = _start(project)
    approved = metrics.estimate.estimate_source in APPROVED_ESTIMATE_SOURCES
    return ProjectFacts(
        project_id=project.id,
        label=project_label(project),
        customer_id=project.customer_id,
        customer_name=names.get(project.customer_id),
        project_type_id=project.project_type_id,
        project_type_name=types.get(project.project_type_id),
        template_id=project.project_template_id,
        complexity=project.complexity.value if project.complexity else None,
        classification=project.project_classification.value if project.project_classification else None,
        team_id=project.team_id,
        designer_id=project.designer_id,
        design_leader_id=project.design_leader_id,
        execution_status=metrics.execution_status,
        start_date=start,
        start_source=start_source,
        committed_date=committed,
        committed_source=delivery.reference_source,
        current_target=delivery.current_target_date,
        target_moved_days=delivery.target_moved_days,
        completed_on=project.completed_at.date() if project.completed_at else None,
        estimate_approved=approved,
        estimate_source=metrics.estimate.estimate_source,
        quoted_hours=metrics.estimate.quoted_hours,
        original_estimate=metrics.estimate.original_estimate_hours if approved else None,
        current_estimate=metrics.estimate.current_estimate_hours if approved else None,
        actual_hours=metrics.actual.total_hours,
        actual_status=metrics.actual.status,
        unapproved_hours=metrics.actual.draft_hours + metrics.actual.submitted_hours,
        rejected_hours=metrics.actual.rejected_hours,
        open_milestones=metrics.milestones.open,
        overdue_milestones=metrics.milestones.open_overdue,
        open_without_target=metrics.milestones.open_without_target_date,
        issue_codes=tuple(issue.code for issue in metrics.issues),
    )


def load_facts(db: Session, projects: list[Project], as_of: date) -> dict[UUID, ProjectFacts]:
    if not projects:
        return {}
    metrics = build_engineering_metrics_batch(db, projects, finance_details_visible=False, today=as_of)
    customer_ids = {p.customer_id for p in projects if p.customer_id}
    type_ids = {p.project_type_id for p in projects if p.project_type_id}
    names = dict(db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids))).all()) if customer_ids else {}
    types = dict(db.execute(select(ProjectType.id, ProjectType.name).where(ProjectType.id.in_(type_ids))).all()) if type_ids else {}
    return {p.id: facts_from(p, metrics[p.id], names, types) for p in projects}


def open_projects(db: Session, *, visibility_clause=None, project_ids: set[UUID] | None = None) -> list[Project]:
    stmt = select(Project).where(
        Project.is_deleted.is_(False), Project.is_archived.is_(False), Project.execution_status.in_(OPEN_STATUSES)
    )
    if visibility_clause is not None:
        stmt = stmt.where(visibility_clause)
    if project_ids is not None:
        stmt = stmt.where(Project.id.in_(project_ids))
    return list(db.scalars(stmt.order_by(Project.tool_number)).all())


def completed_projects(db: Session, as_of: date) -> list[Project]:
    """History is org-wide so a prediction does not depend on who asks; nothing after ``as_of``."""
    cutoff = datetime.combine(as_of, time.max)
    return list(
        db.scalars(
            select(Project).where(
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
                Project.completed_at.is_not(None),
                Project.completed_at <= cutoff,
            )
        ).all()
    )


# --- Comparable groups -------------------------------------------------------------------------

# Most specific first. Every level keeps the project type (an unset type only matches unset
# types), so fundamentally different workflows are never pooled. Customer refines a group of
# the same type and complexity; it is never used on its own.
GROUP_LEVELS: tuple[tuple[str, ...], ...] = (
    ("project_type_id", "complexity", "customer_id"),
    ("project_type_id", "complexity"),
    ("project_type_id",),
)
LEVEL_LABELS = {
    ("project_type_id", "complexity", "customer_id"): "same project type, complexity and customer",
    ("project_type_id", "complexity"): "same project type and complexity",
    ("project_type_id",): "same project type",
}


def comparable_group(target: ProjectFacts, samples: list, minimum: int = MIN_SAMPLE) -> tuple[str | None, list, int]:
    """Most specific group with enough history: (label, group, largest group size seen).

    Samples expose ``.facts``. Label and group are empty when no level reaches ``minimum``.
    """
    largest = 0
    for level in GROUP_LEVELS:
        if any(key != "project_type_id" and getattr(target, key) is None for key in level):
            continue
        group = [s for s in samples if all(getattr(s.facts, key) == getattr(target, key) for key in level)]
        largest = max(largest, len(group))
        if len(group) >= minimum:
            label = LEVEL_LABELS[level]
            if target.project_type_id is None:
                label += " (projects without a project type)"
            return label, group, largest
    return None, [], largest


def type_label(target: ProjectFacts) -> str:
    return target.project_type_name or "no project type"
