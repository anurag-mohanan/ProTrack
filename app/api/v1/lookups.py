from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.permissions import can_write_timesheet_entry
from app.crud.timesheet_projects import get_timesheet_project_context, list_timesheet_projects
from app.crud.base import select
from app.models.models import Contact, Customer, NonProductiveCode, OperationalRoleType, OrgDepartment, ProjectType, Role, Stream, TaskType, Team, User, WorkingModel
from app.schemas.identity import OperationalRoleTypeRead, OrgDepartmentRead, RoleRead
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
    for_reports: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.data_scope import scoped_user_ids_for_actor
    from app.services.reporting.report_authorization import resolve_report_subject_user_ids

    query = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.is_archived.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(User.last_name, User.first_name)
    )
    visible = (
        resolve_report_subject_user_ids(db, current_user)
        if for_reports
        else scoped_user_ids_for_actor(db, current_user)
    )
    if visible is not None:
        if not visible:
            return []
        query = query.where(User.id.in_(visible))
    users = db.scalars(query).all()
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
    current_user: User = Depends(get_current_user),
):
    from app.core.data_scope import scoped_customer_ids

    query = select(Customer).where(Customer.is_active.is_(True)).order_by(Customer.name)
    allowed = scoped_customer_ids(db, current_user)
    if allowed is not None:
        if not allowed:
            return []
        query = query.where(Customer.id.in_(allowed))
    return list(db.scalars(query).all())


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


@router.get("/org-departments", response_model=list[OrgDepartmentRead])
def list_lookup_org_departments(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Active org-chart departments for placement pickers (onboarding, etc.)."""
    rows = db.scalars(
        select(OrgDepartment)
        .where(OrgDepartment.is_active.is_(True))
        .order_by(OrgDepartment.sort_order, OrgDepartment.name)
    ).all()
    return [
        OrgDepartmentRead(
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            code=row.code,
            name=row.name,
            description=row.description,
            colour=row.colour or "#1976d2",
            sort_order=row.sort_order or 100,
            head_user_id=row.head_user_id,
            is_active=row.is_active,
            head_name=None,
            member_count=0,
        )
        for row in rows
    ]


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
    for_reports: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.data_scope import resolve_data_scope
    from app.crud.team import build_team_read
    from app.services.reporting.report_authorization import resolve_report_team_ids

    query = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    if for_reports:
        team_ids = resolve_report_team_ids(db, current_user)
        if team_ids is not None:
            if not team_ids:
                return []
            query = query.where(Team.id.in_(team_ids))
    else:
        scope = resolve_data_scope(db, current_user)
        if not scope.unrestricted:
            if not scope.team_ids:
                return []
            query = query.where(Team.id.in_(scope.team_ids))
    teams = db.scalars(query).all()
    return [build_team_read(db, team) for team in teams]
