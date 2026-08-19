from uuid import UUID

from sqlalchemy.orm import Session

from app.core.field_normalization import normalize_optional_text
from app.crud.base import select
from app.models.models import Customer, Project, ProjectType, Team, User, WorkingModel
from app.schemas.project import ProjectRead, ProjectWorkstreamSummary
from app.services.dashboard_service import _batch_current_milestones
from app.services.project_calculation_service import (
    batch_calculate_hours,
    batch_calculate_progress,
    calculate_hours,
    calculate_progress,
)
from app.services.project_template_service import can_change_project_template


def _batch_workstream_summaries(
    db: Session, project_ids: list[UUID]
) -> dict[UUID, list[ProjectWorkstreamSummary]]:
    if not project_ids:
        return {}
    from decimal import Decimal

    from app.models.workstream import ProjectWorkstream, Workstream

    links = list(
        db.scalars(
            select(ProjectWorkstream).where(ProjectWorkstream.project_id.in_(project_ids))
        ).all()
    )
    if not links:
        return {pid: [] for pid in project_ids}
    ws_ids = {link.workstream_id for link in links}
    team_ids = {link.team_id for link in links if link.team_id}
    workstreams = {
        w.id: w for w in db.scalars(select(Workstream).where(Workstream.id.in_(ws_ids)))
    }
    teams = (
        {t.id: t for t in db.scalars(select(Team).where(Team.id.in_(team_ids)))}
        if team_ids
        else {}
    )
    by_project: dict[UUID, list[ProjectWorkstreamSummary]] = {pid: [] for pid in project_ids}
    for link in links:
        ws = workstreams.get(link.workstream_id)
        team = teams.get(link.team_id) if link.team_id else None
        remaining = None
        if link.estimated_hours is not None:
            remaining = Decimal(link.estimated_hours) - Decimal(link.actual_hours or 0)
        by_project.setdefault(link.project_id, []).append(
            ProjectWorkstreamSummary(
                workstream_id=link.workstream_id,
                workstream_name=ws.name if ws else None,
                workstream_code=ws.code if ws else None,
                team_id=link.team_id,
                team_name=getattr(team, "name", None),
                estimated_hours=link.estimated_hours,
                actual_hours=link.actual_hours,
                remaining_hours=remaining,
                progress_percent=link.progress_percent,
            )
        )
    return by_project


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    first = normalize_optional_text(user.first_name) or ""
    last = normalize_optional_text(user.last_name) or ""
    name = f"{first} {last}".strip()
    return name or None


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
    from app.services.project_stage_gate_service import (
        project_needs_setup,
        project_setup_gaps,
    )

    progress = calculate_progress(db, project)
    hours = calculate_hours(db, project)
    milestone_names = _batch_current_milestones(db, [project.id])
    names = _batch_display_names(db, [project])
    workstreams = _batch_workstream_summaries(db, [project.id])
    can_change, blocked_reason = can_change_project_template(db, project.id)
    gaps = project_setup_gaps(project)
    return ProjectRead.model_validate(project, from_attributes=True).model_copy(
        update={
            "progress_percent": progress.progress_percent,
            "actual_hours": hours.actual,
            "original_hours": hours.original,
            "additional_work_hours": hours.additional_work,
            "rework_hours": hours.rework,
            "customer_change_hours": hours.customer_change,
            "internal_correction_hours": hours.internal_correction,
            "post_completion_hours": hours.post_completion_total,
            "has_post_completion_activity": hours.post_completion_total > 0,
            "health": project.health,
            "current_milestone": milestone_names.get(project.id),
            "can_change_template": can_change,
            "template_change_blocked_reason": blocked_reason,
            "needs_setup": project_needs_setup(project),
            "setup_gaps": gaps,
            "workstreams": workstreams.get(project.id, []),
            **_name_updates(project, names),
        }
    )


def build_project_reads(db: Session, projects: list[Project]) -> list[ProjectRead]:
    if not projects:
        return []

    from app.services.project_stage_gate_service import (
        project_needs_setup,
        project_setup_gaps,
    )

    project_ids = [project.id for project in projects]
    progress_by_project = batch_calculate_progress(db, project_ids)
    hours_by_project = batch_calculate_hours(db, projects)
    milestone_names = _batch_current_milestones(db, project_ids)
    names = _batch_display_names(db, projects)
    workstreams = _batch_workstream_summaries(db, project_ids)
    reads: list[ProjectRead] = []
    for project in projects:
        can_change, blocked_reason = can_change_project_template(db, project.id)
        gaps = project_setup_gaps(project)
        reads.append(
            ProjectRead.model_validate(project, from_attributes=True).model_copy(
                update={
                    "progress_percent": progress_by_project[project.id].progress_percent,
                    "actual_hours": hours_by_project[project.id].actual,
                    "original_hours": hours_by_project[project.id].original,
                    "additional_work_hours": hours_by_project[project.id].additional_work,
                    "rework_hours": hours_by_project[project.id].rework,
                    "customer_change_hours": hours_by_project[project.id].customer_change,
                    "internal_correction_hours": hours_by_project[project.id].internal_correction,
                    "post_completion_hours": hours_by_project[project.id].post_completion_total,
                    "has_post_completion_activity": hours_by_project[project.id].post_completion_total > 0,
                    "health": project.health,
                    "current_milestone": milestone_names.get(project.id),
                    "can_change_template": can_change,
                    "template_change_blocked_reason": blocked_reason,
                    "needs_setup": project_needs_setup(project),
                    "setup_gaps": gaps,
                    "workstreams": workstreams.get(project.id, []),
                    **_name_updates(project, names),
                }
            )
        )
    return reads
