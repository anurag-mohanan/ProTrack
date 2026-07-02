from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Project
from app.schemas.project import ProjectRead
from app.services.dashboard_service import _batch_current_milestones
from app.services.project_calculation_service import (
    batch_calculate_progress,
    calculate_progress,
)


def build_project_read(db: Session, project: Project) -> ProjectRead:
    progress = calculate_progress(db, project)
    milestone_names = _batch_current_milestones(db, [project.id])
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": progress.progress_percent,
            "health": project.health,
            "current_milestone": milestone_names.get(project.id),
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    if not projects:
        return []

    project_ids = [project.id for project in projects]
    progress_by_project = batch_calculate_progress(db, project_ids)
    milestone_names = _batch_current_milestones(db, project_ids)
    return [
        ProjectRead.model_validate(project, from_attributes=True).model_copy(
            update={
                "progress_percent": progress_by_project[project.id].progress_percent,
                "health": project.health,
                "current_milestone": milestone_names.get(project.id),
            }
        )
        for project in projects
    ]
