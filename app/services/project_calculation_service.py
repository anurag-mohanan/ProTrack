from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MilestoneStatus, ProjectHealth, ProjectStatus
from app.models.models import Milestone, Project


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _coerce_uuid(project_id: UUID | str) -> UUID:
    if isinstance(project_id, UUID):
        return project_id
    return UUID(str(project_id))


def calculate_progress_percent(db: Session, project_id: UUID | str) -> Decimal:
    project_id = _coerce_uuid(project_id)
    completed_milestones = int(
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
    total_milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.project_id == project_id)
        )
        or 0
    )

    if total_milestones == 0:
        return Decimal("0.00")

    return _round_percent(
        (Decimal(completed_milestones) / Decimal(total_milestones)) * Decimal("100")
    )


def calculate_project_health(
    project: Project,
    today: date | None = None,
) -> ProjectHealth:
    today = today or date.today()

    if project.status == ProjectStatus.completed:
        return ProjectHealth.green

    if project.due_date < today:
        return ProjectHealth.red

    if project.due_date <= today + timedelta(days=5):
        return ProjectHealth.yellow

    return ProjectHealth.green


def recalculate_project_progress(db: Session, project_id: UUID | str) -> Project | None:
    project_id = _coerce_uuid(project_id)
    project = db.get(Project, project_id)
    if project is None:
        return None

    progress_percent = calculate_progress_percent(db, project_id)

    if progress_percent == Decimal("0.00"):
        project.status = ProjectStatus.not_started
    elif progress_percent < Decimal("100.00"):
        project.status = ProjectStatus.in_progress
    else:
        project.status = ProjectStatus.completed

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_milestone_summary(
    db: Session,
    project_id: UUID | str,
) -> tuple[int, int, Decimal]:
    project_id = _coerce_uuid(project_id)
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
    remaining = max(total - completed, 0)
    progress_percent = calculate_progress_percent(db, project_id)
    return completed, remaining, progress_percent


def count_projects_by_health(
    db: Session,
    today: date | None = None,
) -> tuple[int, int, int]:
    projects = db.scalars(select(Project)).all()
    green = yellow = red = 0
    for project in projects:
        health = calculate_project_health(project, today)
        if health == ProjectHealth.green:
            green += 1
        elif health == ProjectHealth.yellow:
            yellow += 1
        else:
            red += 1
    return green, yellow, red
