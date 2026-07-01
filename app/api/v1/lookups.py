from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.crud.base import select
from app.models.models import Contact, Customer, NonProductiveCode, ProjectType, Role, Stream, TaskType, Team, User
from app.schemas.identity import RoleRead
from app.schemas.organization import ContactRead, CustomerRead, NonProductiveCodeRead, StreamRead, TaskTypeRead
from app.schemas.team import TeamRead
from app.schemas.templates import ProjectTypeRead

router = APIRouter(prefix="/lookups", tags=["lookups"])


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


@router.get("/teams", response_model=list[TeamRead])
def list_lookup_teams(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    from app.crud.team import build_team_read

    teams = db.scalars(
        select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    ).all()
    return [build_team_read(db, team) for team in teams]
