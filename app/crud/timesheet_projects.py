"""Timesheet-eligible active projects (no assignment restriction)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus
from app.models.models import Customer, Project, User
from app.schemas.timesheet import TimesheetProjectLookup

LOGGABLE_PROJECT_STATUSES = (
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
)


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def list_timesheet_projects(db: Session) -> list[TimesheetProjectLookup]:
    rows = db.execute(
        select(Project, Customer.name)
        .join(Customer, Project.customer_id == Customer.id)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(LOGGABLE_PROJECT_STATUSES),
        )
        .order_by(Project.tool_number)
    ).all()

    user_ids: set[UUID] = set()
    for project, _customer_name in rows:
        if project.designer_id:
            user_ids.add(project.designer_id)
        if project.surfacer_id:
            user_ids.add(project.surfacer_id)

    users_by_id: dict[UUID, User] = {}
    if user_ids:
        users_by_id = {
            user.id: user
            for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()
        }

    return [
        TimesheetProjectLookup(
            id=project.id,
            tool_number=project.tool_number,
            part_description=project.part_description,
            customer_name=customer_name,
            designer_name=_full_name(users_by_id.get(project.designer_id))
            if project.designer_id
            else None,
            surfacer_name=_full_name(users_by_id.get(project.surfacer_id))
            if project.surfacer_id
            else None,
            project_stage=project.project_stage,
            execution_status=project.execution_status,
            stream_id=project.stream_id,
            team_id=project.team_id,
            team_name=None,
            design_leader_name=None,
            project_type_name=None,
        )
        for project, customer_name in rows
    ]
