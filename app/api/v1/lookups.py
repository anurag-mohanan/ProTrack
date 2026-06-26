from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.crud.base import select
from app.models.models import Contact, Customer, Role, Stream, TaskType, User
from app.schemas.identity import RoleRead
from app.schemas.organization import ContactRead, CustomerRead, StreamRead, TaskTypeRead

router = APIRouter(prefix="/lookups", tags=["lookups"])


@router.get("/users")
def list_lookup_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    users = db.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.last_name, User.first_name)
    ).all()
    return [
        {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role_id": user.role_id,
            "is_active": user.is_active,
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


@router.get("/roles", response_model=list[RoleRead])
def list_lookup_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.scalars(select(Role).order_by(Role.name)).all()
