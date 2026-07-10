from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.permissions import can_write_timesheet_entry
from app.crud.timesheet_projects import get_timesheet_project_context, list_timesheet_projects
from app.crud.base import select
from app.models.models import Contact, Customer, NonProductiveCode, OperationalRoleType, ProjectType, Role, Stream, TaskType, Team, User, WorkingModel
from app.schemas.identity import OperationalRoleTypeRead, RoleRead
from app.schemas.organization import ContactRead, CustomerRead, NonProductiveCodeRead, StreamRead, TaskTypeRead, WorkingModelRead
from app.schemas.team import TeamRead
from app.schemas.templates import ProjectTypeRead
from app.schemas.timesheet import TimesheetProjectContext, TimesheetProjectLookup

router = APIRouter(prefix="/lookups", tags=["lookups"])


@router.get("/operational-roles", response_model=list[OperationalRoleTypeRead])
def list_operational_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(OperationalRoleType)
        .where(OperationalRoleType.is_active.is_(True))
        .order_by(OperationalRoleType.name)
    ).all()


@router.get("/users")
def list_lookup_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    users = db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.is_archived.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(User.last_name, User.first_name)
    ).all()
    return [
        {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role_id": user.role_id,
            "is_active": user.is_active,
            "team_id": user.team_id,
        }
        for user in users
    ]


@router.get("/customers", response_model=list[CustomerRead])
def list_lookup_customers(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Customer).where(Customer.is_active.is_(True)).order_by(Customer.name)
    ).all()


@router.get("/contacts", response_model=list[ContactRead])
def list_lookup_contacts(
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = select(Contact).where(Contact.is_active.is_(True))
    if customer_id is not None:
        query = query.where(Contact.customer_id == customer_id)
    return db.scalars(query.order_by(Contact.last_name, Contact.first_name)).all()


@router.get("/streams", response_model=list[StreamRead])
def list_lookup_streams(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Stream).where(Stream.is_active.is_(True)).order_by(Stream.name)
    ).all()


@router.get("/task-types", response_model=list[TaskTypeRead])
def list_lookup_task_types(
    stream_id: UUID | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = select(TaskType).where(TaskType.is_active.is_(True))
    if stream_id is not None:
        query = query.where(TaskType.stream_id == stream_id)
    return db.scalars(query.order_by(TaskType.name)).all()


@router.get("/non-productive-codes", response_model=list[NonProductiveCodeRead])
def list_lookup_non_productive_codes(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(NonProductiveCode)
        .where(
            NonProductiveCode.is_active.is_(True),
            NonProductiveCode.is_archived.is_(False),
        )
        .order_by(NonProductiveCode.sort_order, NonProductiveCode.code)
    ).all()


@router.get("/roles", response_model=list[RoleRead])
def list_lookup_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(select(Role).order_by(Role.name)).all()


@router.get("/project-types", response_model=list[ProjectTypeRead])
def list_lookup_project_types(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(ProjectType)
        .where(ProjectType.is_active.is_(True))
        .order_by(ProjectType.name)
    ).all()


@router.get("/working-models", response_model=list[WorkingModelRead])
def list_lookup_working_models(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(WorkingModel)
        .where(WorkingModel.is_active.is_(True), WorkingModel.is_archived.is_(False))
        .order_by(WorkingModel.sort_order, WorkingModel.name)
    ).all()


@router.get("/timesheet-projects", response_model=list[TimesheetProjectLookup])
def list_lookup_timesheet_projects(
    q: str | None = Query(None, min_length=1, max_length=100),
    limit: int | None = Query(None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_write_timesheet_entry(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return list_timesheet_projects(
        db,
        user_id=current_user.id,
        q=q,
        limit=limit,
    )


@router.get("/timesheet-projects/{project_id}/context", response_model=TimesheetProjectContext)
def get_lookup_timesheet_project_context(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_write_timesheet_entry(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    context = get_timesheet_project_context(db, project_id, user_id=current_user.id)
    if context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return context


@router.get("/teams", response_model=list[TeamRead])
def list_lookup_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.team_access import get_accessible_team_ids
    from app.crud.team import build_team_read

    query = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    accessible = get_accessible_team_ids(db, current_user)
    if accessible is not None:
        if not accessible:
            return []
        query = query.where(Team.id.in_(accessible))
    teams = db.scalars(query).all()
    return [build_team_read(db, team) for team in teams]
