"""Organization department management — CRUD + audited member assignment.

Departments here are the *org-chart* units (Management, Engineering, Sales,
Accounts, Human Resource, IT), distinct from the legacy HR ``departments``.
Mirrors ``roles.py`` so the admin experience is consistent.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.crud import org_department as org_department_crud
from app.models.enums import ActivityAction, EntityType
from app.models.models import OrgDepartment, Team, User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.identity import (
    AssignDepartmentRequest,
    OrgDepartmentCreate,
    OrgDepartmentRead,
    OrgDepartmentUpdate,
)
from app.services.activity_service import log_activity

router = APIRouter(
    prefix="/org-departments",
    tags=["org-departments"],
    dependencies=[Depends(require_roles("Admin"))],
)

write_access = Depends(require_roles("Admin"))

MODULE = "organization"


def _member_counts(db: Session) -> dict[UUID, int]:
    rows = db.execute(
        select(User.org_department_id, func.count(User.id))
        .where(
            User.is_deleted.is_(False),
            User.is_active.is_(True),
            User.org_department_id.is_not(None),
        )
        .group_by(User.org_department_id)
    ).all()
    return {dept_id: int(count) for dept_id, count in rows if dept_id is not None}


def _to_read(dept: OrgDepartment, counts: dict[UUID, int]) -> OrgDepartmentRead:
    head_name = None
    if dept.head_user is not None:
        head_name = f"{dept.head_user.first_name} {dept.head_user.last_name}".strip()
    return OrgDepartmentRead(
        id=dept.id,
        code=dept.code,
        name=dept.name,
        description=dept.description,
        colour=dept.colour,
        sort_order=dept.sort_order,
        head_user_id=dept.head_user_id,
        is_active=bool(dept.is_active),
        created_at=dept.created_at,
        updated_at=dept.updated_at,
        head_name=head_name,
        member_count=counts.get(dept.id, 0),
    )


@router.get("", response_model=list[OrgDepartmentRead])
def list_org_departments(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = select(OrgDepartment).order_by(
        OrgDepartment.sort_order, OrgDepartment.name
    )
    if not include_inactive:
        query = query.where(OrgDepartment.is_active.is_(True))
    departments = db.scalars(query).all()
    counts = _member_counts(db)
    return [_to_read(dept, counts) for dept in departments]


@router.get("/{record_id}", response_model=OrgDepartmentRead)
def get_org_department(record_id: UUID, db: Session = Depends(get_db)):
    dept = get_object_or_404(org_department_crud, db, record_id)
    return _to_read(dept, _member_counts(db))


@router.post(
    "",
    response_model=OrgDepartmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_access],
)
def create_org_department(obj_in: OrgDepartmentCreate, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(OrgDepartment).where(
            (OrgDepartment.code == obj_in.code) | (OrgDepartment.name == obj_in.name)
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A department with this code or name already exists.",
        )
    dept = org_department_crud.create(db, obj_in=obj_in)
    return _to_read(dept, _member_counts(db))


@router.patch(
    "/{record_id}",
    response_model=OrgDepartmentRead,
    dependencies=[write_access],
)
def update_org_department(
    record_id: UUID,
    obj_in: OrgDepartmentUpdate,
    db: Session = Depends(get_db),
):
    dept = get_object_or_404(org_department_crud, db, record_id)
    updated = org_department_crud.update(db, db_obj=dept, obj_in=obj_in)
    return _to_read(updated, _member_counts(db))


def _department_blockers(db: Session, record_id: UUID) -> tuple[int, int]:
    user_count = db.scalar(
        select(func.count(User.id)).where(
            User.org_department_id == record_id, User.is_deleted.is_(False)
        )
    )
    team_count = db.scalar(
        select(func.count(Team.id)).where(Team.org_department_id == record_id)
    )
    return int(user_count or 0), int(team_count or 0)


@router.get("/{record_id}/delete-check", response_model=DeleteCheckResponse)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    dept = get_object_or_404(org_department_crud, db, record_id)
    users, teams = _department_blockers(db, record_id)
    blockers: list[str] = []
    if users > 0:
        blockers.append(f"{users} {'person' if users == 1 else 'people'} assigned")
    if teams > 0:
        blockers.append(f"{teams} {'team' if teams == 1 else 'teams'} linked")
    return DeleteCheckResponse(
        can_delete=not blockers,
        blockers=blockers,
        related_records=blockers,
        record_name=dept.name,
        record_type="Department",
    )


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[write_access],
)
def delete_org_department(record_id: UUID, db: Session = Depends(get_db)):
    get_object_or_404(org_department_crud, db, record_id)
    users, teams = _department_blockers(db, record_id)
    if users > 0 or teams > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Reassign the people and teams in this department before deleting it "
                f"({users} people, {teams} teams)."
            ),
        )
    org_department_crud.delete(db, record_id=record_id)


@router.post("/{record_id}/assign-user", response_model=OrgDepartmentRead)
def assign_user_to_department(
    record_id: UUID,
    payload: AssignDepartmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a user into this org department (audited)."""
    dept = get_object_or_404(org_department_crud, db, record_id)
    user = db.get(User, payload.user_id)
    if user is None or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    previous_dept_id = user.org_department_id
    if previous_dept_id == dept.id:
        return _to_read(dept, _member_counts(db))

    previous_name = None
    if previous_dept_id is not None:
        previous = db.get(OrgDepartment, previous_dept_id)
        previous_name = previous.name if previous is not None else None

    user.org_department_id = dept.id
    db.flush()

    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=user.id,
        action=ActivityAction.user_department_changed,
        old_value={"org_department": previous_name},
        new_value={"org_department": dept.name},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    return _to_read(dept, _member_counts(db))
