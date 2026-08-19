"""Timesheet-eligible active projects (no assignment restriction)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.enums import ExecutionStatus, MilestoneStatus
from app.models.models import (
    Customer,
    Milestone,
    Project,
    ProjectType,
    Team,
    User,
    WorkingModel,
)
from app.schemas.timesheet import TimesheetProjectLookup

LOGGABLE_PROJECT_STATUSES = (
    ExecutionStatus.planning,
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
    ExecutionStatus.completed,
)

DesignerUser = aliased(User)
SurfacerUser = aliased(User)
DesignLeaderUser = aliased(User)


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _remaining_hours(project: Project) -> Decimal:
    quoted = Decimal(str(project.quoted_hours or 0))
    actual = Decimal(str(project.actual_hours or 0))
    return max(quoted - actual, Decimal("0"))


def _search_clause(term: str):
    pattern = f"%{term.strip().lower()}%"
    return or_(
        func.lower(Project.tool_number).like(pattern),
        func.lower(Project.part_description).like(pattern),
        func.lower(Customer.name).like(pattern),
        func.lower(DesignerUser.first_name).like(pattern),
        func.lower(DesignerUser.last_name).like(pattern),
        func.lower(SurfacerUser.first_name).like(pattern),
        func.lower(SurfacerUser.last_name).like(pattern),
        func.lower(func.concat(DesignerUser.first_name, " ", DesignerUser.last_name)).like(
            pattern
        ),
        func.lower(func.concat(SurfacerUser.first_name, " ", SurfacerUser.last_name)).like(
            pattern
        ),
    )


def list_timesheet_projects(
    db: Session,
    *,
    user_id: UUID | None = None,
    q: str | None = None,
    limit: int | None = None,
) -> list[TimesheetProjectLookup]:
    stmt = (
        select(
            Project,
            Customer.name,
            Team.name,
            ProjectType.name,
            WorkingModel.name,
            WorkingModel.code,
            DesignLeaderUser,
            DesignerUser,
            SurfacerUser,
        )
        .join(Customer, Project.customer_id == Customer.id)
        .outerjoin(Team, Project.team_id == Team.id)
        .outerjoin(ProjectType, Project.project_type_id == ProjectType.id)
        .outerjoin(WorkingModel, Project.working_model_id == WorkingModel.id)
        .outerjoin(DesignLeaderUser, Project.design_leader_id == DesignLeaderUser.id)
        .outerjoin(DesignerUser, Project.designer_id == DesignerUser.id)
        .outerjoin(SurfacerUser, Project.surfacer_id == SurfacerUser.id)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(LOGGABLE_PROJECT_STATUSES),
        )
        .order_by(Project.tool_number)
    )

    if q and q.strip():
        stmt = stmt.where(_search_clause(q))
        if limit is None:
            limit = 50

    if limit is not None:
        stmt = stmt.limit(limit)

    rows = db.execute(stmt).all()
    from app.services.post_completion_work import post_completion_hours_allowed

    return [
        TimesheetProjectLookup(
            id=project.id,
            tool_number=project.tool_number,
            part_description=project.part_description,
            customer_name=customer_name,
            designer_id=project.designer_id,
            surfacer_id=project.surfacer_id,
            designer_name=_full_name(designer_user),
            surfacer_name=_full_name(surfacer_user),
            project_stage=project.project_stage,
            execution_status=project.execution_status,
            stream_id=project.stream_id,
            team_id=project.team_id,
            team_name=team_name,
            design_leader_name=_full_name(design_leader_user),
            project_type_name=project_type_name,
            working_model_name=working_model_name,
            working_model_code=(
                working_model_code.value
                if hasattr(working_model_code, "value")
                else str(working_model_code)
                if working_model_code is not None
                else None
            ),
            health=project.health,
            quoted_hours=Decimal(str(project.quoted_hours or 0)),
            actual_hours=Decimal(str(project.actual_hours or 0)),
            remaining_hours=_remaining_hours(project),
            is_assigned_to_user=user_id is not None
            and user_id in {project.designer_id, project.surfacer_id},
            post_completion_hours_allowed=post_completion_hours_allowed(db, project),
        )
        for (
            project,
            customer_name,
            team_name,
            project_type_name,
            working_model_name,
            working_model_code,
            design_leader_user,
            designer_user,
            surfacer_user,
        ) in rows
    ]


def get_timesheet_project_context(
    db: Session,
    project_id: UUID,
    *,
    user_id: UUID | None = None,
) -> "TimesheetProjectContext | None":
    from app.schemas.timesheet import TimesheetProjectContext, TimesheetProjectMilestoneDue
    from app.services.project_contributor_service import get_project_contributors

    project = db.get(Project, project_id)
    if project is None or project.is_deleted or project.is_archived:
        return None
    if project.execution_status not in LOGGABLE_PROJECT_STATUSES:
        return None

    customer_name = db.scalar(
        select(Customer.name).where(Customer.id == project.customer_id)
    )
    working_model_name = db.scalar(
        select(WorkingModel.name).where(WorkingModel.id == project.working_model_id)
    )

    milestones = db.scalars(
        select(Milestone)
        .where(
            Milestone.project_id == project_id,
            Milestone.status != MilestoneStatus.completed,
        )
        .order_by(Milestone.due_date.nulls_last(), Milestone.sort_order)
        .limit(5)
    ).all()

    contributors = get_project_contributors(db, project_id)
    from app.services.project_calculation_service import calculate_hours
    from app.services.post_completion_work import post_completion_hours_allowed

    hours = calculate_hours(db, project)
    remaining = hours.remaining

    return TimesheetProjectContext(
        project_id=project.id,
        tool_number=project.tool_number,
        part_description=project.part_description,
        customer_name=customer_name,
        project_stage=project.project_stage,
        execution_status=project.execution_status,
        health=project.health,
        working_model_name=working_model_name,
        quoted_hours=Decimal(str(project.quoted_hours or 0)),
        actual_hours=hours.actual,
        remaining_hours=remaining,
        original_hours=hours.original,
        additional_work_hours=hours.additional_work,
        rework_hours=hours.rework,
        customer_change_hours=hours.customer_change,
        internal_correction_hours=hours.internal_correction,
        has_post_completion_activity=hours.post_completion_total > 0,
        post_completion_hours_allowed=post_completion_hours_allowed(db, project),
        milestones_due=[
            TimesheetProjectMilestoneDue(
                id=milestone.id,
                name=milestone.name,
                due_date=milestone.due_date,
                status=milestone.status,
            )
            for milestone in milestones
        ],
        contributor_count=len(contributors),
        is_assigned_to_user=user_id is not None
        and user_id in {project.designer_id, project.surfacer_id},
    )
