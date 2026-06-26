from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Project
from app.schemas.project import ProjectRead
from app.services.project_calculation_service import (
    batch_calculate_progress,
    calculate_progress,
)


def build_project_read(db: Session, project: Project) -> ProjectRead:
    progress = calculate_progress(db, project)
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": progress.progress_percent,
            "health": project.health,
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    if not projects:
        return []

    progress_by_project = batch_calculate_progress(db, [project.id for project in projects])
    return [
        ProjectRead.model_validate(project, from_attributes=True).model_copy(
            update={
                "progress_percent": progress_by_project[project.id].progress_percent,
                "health": project.health,
            }
        )
        for project in projects
    ]
