from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth
from app.models.models import Milestone, Project, TimesheetEntry


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _coerce_uuid(project_id: UUID | str) -> UUID:
    if isinstance(project_id, UUID):
        return project_id
    return UUID(str(project_id))


@dataclass(frozen=True)
class MilestoneProgress:
    completed_milestones: int
    remaining_milestones: int
    total_milestones: int
    progress_percent: Decimal


@dataclass(frozen=True)
class ProjectHours:
    quoted: Decimal
    actual: Decimal
    remaining: Decimal
    variance: Decimal


def _milestone_counts(db: Session, project_id: UUID) -> tuple[int, int]:
    completed = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(
                Milestone.project_id == project_id,
                Milestone.status == MilestoneStatus.completed,
            )
        )
        or 0
    )
    total = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == project_id)
        )
        or 0
    )
    return completed, total


def batch_calculate_progress(
    db: Session,
    project_ids: list[UUID],
) -> dict[UUID, MilestoneProgress]:
    if not project_ids:
        return {}

    total_rows = db.execute(
        select(Milestone.project_id, func.count())
        .where(Milestone.project_id.in_(project_ids))
        .group_by(Milestone.project_id)
    ).all()
    completed_rows = db.execute(
        select(Milestone.project_id, func.count())
        .where(
            Milestone.project_id.in_(project_ids),
            Milestone.status == MilestoneStatus.completed,
        )
        .group_by(Milestone.project_id)
    ).all()

    totals = {project_id: int(count) for project_id, count in total_rows}
    completed_map = {project_id: int(count) for project_id, count in completed_rows}

    progress_by_project: dict[UUID, MilestoneProgress] = {}
    for project_id in project_ids:
        total = totals.get(project_id, 0)
        completed = completed_map.get(project_id, 0)
        remaining = max(total - completed, 0)
        if total == 0:
            progress_percent = Decimal("0.00")
        else:
            progress_percent = _round_percent(
                (Decimal(completed) / Decimal(total)) * Decimal("100")
            )
        progress_by_project[project_id] = MilestoneProgress(
            completed_milestones=completed,
            remaining_milestones=remaining,
            total_milestones=total,
            progress_percent=progress_percent,
        )
    return progress_by_project


def calculate_progress(db: Session, project: Project) -> MilestoneProgress:
    completed, total = _milestone_counts(db, project.id)
    remaining = max(total - completed, 0)

    if total == 0:
        progress_percent = Decimal("0.00")
    else:
        progress_percent = _round_percent(
            (Decimal(completed) / Decimal(total)) * Decimal("100")
        )

    return MilestoneProgress(
        completed_milestones=completed,
        remaining_milestones=remaining,
        total_milestones=total,
        progress_percent=progress_percent,
    )


def calculate_project_health(
    project: Project,
    today: date | None = None,
) -> ProjectHealth:
    today = today or date.today()

    if project.execution_status == ExecutionStatus.completed:
        return ProjectHealth.green

    if project.due_date < today:
        return ProjectHealth.red

    if project.due_date <= today + timedelta(days=5):
        return ProjectHealth.yellow

    return ProjectHealth.green


def calculate_hours(db: Session, project: Project) -> ProjectHours:
    total = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
            TimesheetEntry.project_id == project.id
        )
    )
    quoted = _round_hours(_decimal(project.quoted_hours))
    actual = _round_hours(_decimal(total))
    remaining = _round_hours(quoted - actual)
    variance = _round_hours(actual - quoted)
    return ProjectHours(
        quoted=quoted,
        actual=actual,
        remaining=remaining,
        variance=variance,
    )


def recalculate_project(db: Session, project_id: UUID | str) -> Project | None:
    project_id = _coerce_uuid(project_id)
    project = db.get(Project, project_id)
    if project is None:
        return None

    hours = calculate_hours(db, project)
    project.actual_hours = hours.actual
    project.health = calculate_project_health(project)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_milestone_summary(
    db: Session,
    project_id: UUID | str,
) -> tuple[int, int, Decimal]:
    project_id = _coerce_uuid(project_id)
    project = db.get(Project, project_id)
    if project is None:
        return 0, 0, Decimal("0.00")

    progress = calculate_progress(db, project)
    return (
        progress.completed_milestones,
        progress.remaining_milestones,
        progress.progress_percent,
    )


def count_projects_by_health(db: Session) -> tuple[int, int, int]:
    green = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.health == ProjectHealth.green)
        )
        or 0
    )
    yellow = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.health == ProjectHealth.yellow)
        )
        or 0
    )
    red = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.health == ProjectHealth.red)
        )
        or 0
    )
    return green, yellow, red


def aggregate_portfolio_hours(db: Session) -> ProjectHours:
    total_quoted = _round_hours(
        _decimal(db.scalar(select(func.coalesce(func.sum(Project.quoted_hours), 0))))
    )
    total_actual = _round_hours(
        _decimal(db.scalar(select(func.coalesce(func.sum(Project.actual_hours), 0))))
    )
    return ProjectHours(
        quoted=total_quoted,
        actual=total_actual,
        remaining=_round_hours(total_quoted - total_actual),
        variance=_round_hours(total_actual - total_quoted),
    )
