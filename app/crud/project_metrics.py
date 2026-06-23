from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MilestoneStatus, ProjectHealth, ProjectStatus
from app.models.models import Milestone, Project, TimesheetEntry
from app.schemas.project import ProjectRead


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recalculate_project_actual_hours(db: Session, project_id: UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
            TimesheetEntry.project_id == project_id
        )
    )
    actual_hours = Decimal(str(total or 0))
    project = db.get(Project, project_id)
    if project is not None:
        project.actual_hours = actual_hours
        db.add(project)
        db.commit()
        db.refresh(project)
    return actual_hours


def calculate_progress_percent(db: Session, project_id: UUID) -> Decimal:
    completed = db.scalar(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
            Milestone.status == MilestoneStatus.completed,
        )
    )
    total = db.scalar(
        select(func.count())
        .select_from(Milestone)
        .where(Milestone.project_id == project_id)
    )
    completed_count = int(completed or 0)
    total_count = int(total or 0)
    if total_count == 0:
        return Decimal("0.00")
    return _round_percent(
        (Decimal(completed_count) / Decimal(total_count)) * Decimal("100")
    )


def calculate_project_health(project: Project) -> ProjectHealth:
    if project.status == ProjectStatus.completed:
        return ProjectHealth.green

    quoted_hours = Decimal(project.quoted_hours)
    actual_hours = Decimal(project.actual_hours or 0)

    if quoted_hours <= 0:
        return ProjectHealth.green

    variance_pct = (actual_hours / quoted_hours) * Decimal("100")
    if variance_pct <= Decimal("90"):
        return ProjectHealth.green
    if variance_pct <= Decimal("110"):
        return ProjectHealth.yellow
    return ProjectHealth.red


def build_project_read(db: Session, project: Project) -> ProjectRead:
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": calculate_progress_percent(db, project.id),
            "health": calculate_project_health(project),
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    return [build_project_read(db, project) for project in projects]
