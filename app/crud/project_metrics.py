from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.base import select
from app.models.models import Customer, Project, ProjectType, Team, User, WorkingModel
from app.schemas.project import ProjectRead
from app.services.dashboard_service import _batch_current_milestones
from app.services.project_calculation_service import (
    batch_calculate_progress,
    calculate_progress,
)


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _batch_display_names(
    db: Session, projects: list[Project]
) -> dict[str, dict[UUID, object]]:
    """Resolve related display names for a batch of projects in bulk.

    Avoids per-project (N+1) queries by loading each related table once.
    """

    customer_ids = {p.customer_id for p in projects if p.customer_id}
    type_ids = {p.project_type_id for p in projects if p.project_type_id}
    model_ids = {p.working_model_id for p in projects if p.working_model_id}
    team_ids = {p.team_id for p in projects if p.team_id}
    user_ids = {
        uid
        for p in projects
        for uid in (p.design_leader_id, p.designer_id, p.surfacer_id)
        if uid
    }

    customers = (
        {c.id: c for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids)))}
        if customer_ids
        else {}
    )
    types = (
        {t.id: t for t in db.scalars(select(ProjectType).where(ProjectType.id.in_(type_ids)))}
        if type_ids
        else {}
    )
    working_models = (
        {
            m.id: m
            for m in db.scalars(select(WorkingModel).where(WorkingModel.id.in_(model_ids)))
        }
        if model_ids
        else {}
    )
    teams = (
        {t.id: t for t in db.scalars(select(Team).where(Team.id.in_(team_ids)))}
        if team_ids
        else {}
    )
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
        if user_ids
        else {}
    )
    return {"customers": customers, "types": types, "working_models": working_models, "teams": teams, "users": users}


def _name_updates(project: Project, names: dict[str, dict[UUID, object]]) -> dict:
    customer = names["customers"].get(project.customer_id)
    project_type = names["types"].get(project.project_type_id)
    working_model = names["working_models"].get(project.working_model_id)
    team = names["teams"].get(project.team_id)
    return {
        "customer_name": getattr(customer, "name", None),
        "project_type_name": getattr(project_type, "name", None),
        "working_model_name": getattr(working_model, "name", None),
        "working_model_code": getattr(working_model, "code", None),
        "team_name": getattr(team, "name", None),
        "design_leader_name": _full_name(names["users"].get(project.design_leader_id)),
        "designer_name": _full_name(names["users"].get(project.designer_id)),
        "surfacer_name": _full_name(names["users"].get(project.surfacer_id)),
    }


def build_project_read(db: Session, project: Project) -> ProjectRead:
    progress = calculate_progress(db, project)
    milestone_names = _batch_current_milestones(db, [project.id])
    names = _batch_display_names(db, [project])
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": progress.progress_percent,
            "health": project.health,
            "current_milestone": milestone_names.get(project.id),
            **_name_updates(project, names),
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    if not projects:
        return []

    project_ids = [project.id for project in projects]
    progress_by_project = batch_calculate_progress(db, project_ids)
    milestone_names = _batch_current_milestones(db, project_ids)
    names = _batch_display_names(db, projects)
    return [
        ProjectRead.model_validate(project, from_attributes=True).model_copy(
            update={
                "progress_percent": progress_by_project[project.id].progress_percent,
                "health": project.health,
                "current_milestone": milestone_names.get(project.id),
                **_name_updates(project, names),
            }
        )
        for project in projects
    ]
