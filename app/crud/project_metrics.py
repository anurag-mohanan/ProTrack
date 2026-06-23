from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Project, TimesheetEntry
from app.schemas.project import ProjectRead
from app.services.project_calculation_service import (
    calculate_progress_percent,
    calculate_project_health,
)


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


def build_project_read(db: Session, project: Project) -> ProjectRead:
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": calculate_progress_percent(db, project.id),
            "health": calculate_project_health(project),
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    return [build_project_read(db, project) for project in projects]
