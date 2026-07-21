from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.core.system_roles import SYSTEM_ROLE_NAMES
from app.crud import role as role_crud
from app.models.models import OrgDepartment, Role, User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.identity import (
    RoleCreate,
    RoleHierarchyDepartment,
    RoleHierarchyNode,
    RoleHierarchyRead,
    RoleRead,
    RoleUpdate,
)
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/roles",
    tags=["roles"],
    dependencies=[Depends(require_roles("Admin"))],
)

write_access = Depends(require_roles("Admin"))
admin_access = Depends(require_roles("Admin"))


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


@router.get("", response_model=list[RoleRead])
def list_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return role_crud.get_multi(db, skip=skip, limit=limit)


@router.get("/hierarchy", response_model=RoleHierarchyRead)
def role_hierarchy(db: Session = Depends(get_db)):
    """Roles grouped by org department, ordered top→bottom by rank."""
    counts = dict(
        db.execute(
            select(User.role_id, func.count(User.id))
            .where(User.is_deleted.is_(False))
            .group_by(User.role_id)
        ).all()
    )
    departments = db.scalars(
        select(OrgDepartment)
        .where(OrgDepartment.is_active.is_(True))
        .order_by(OrgDepartment.sort_order, OrgDepartment.name)
    ).all()
    roles = db.scalars(select(Role)).all()
    role_name_by_id = {role.id: role.name for role in roles}

    grouped: dict[UUID | None, list[Role]] = {}
    for role in roles:
        grouped.setdefault(role.org_department_id, []).append(role)

    def _node(role: Role) -> RoleHierarchyNode:
        return RoleHierarchyNode(
            id=role.id,
            name=role.name,
            description=role.description,
            rank=role.rank if role.rank is not None else 100,
            parent_role_id=role.parent_role_id,
            parent_role_name=role_name_by_id.get(role.parent_role_id),
            is_active=bool(role.is_active),
            is_system=role.name in SYSTEM_ROLE_NAMES,
            user_count=int(counts.get(role.id, 0)),
        )

    def _sorted(items: list[Role]) -> list[RoleHierarchyNode]:
        return [
            _node(role)
            for role in sorted(
                items, key=lambda r: (r.rank if r.rank is not None else 100, r.name.lower())
            )
        ]

    out: list[RoleHierarchyDepartment] = [
        RoleHierarchyDepartment(
            department_id=dept.id,
            department_code=dept.code,
            department_name=dept.name,
            colour=dept.colour,
            sort_order=dept.sort_order,
            roles=_sorted(grouped.get(dept.id, [])),
        )
        for dept in departments
    ]

    unassigned = grouped.get(None, [])
    if unassigned:
        out.append(
            RoleHierarchyDepartment(
                department_id=None,
                department_code=None,
                department_name="System / Unassigned",
                colour="#607d8b",
                sort_order=999,
                roles=_sorted(unassigned),
            )
        )
    return RoleHierarchyRead(departments=out)


@router.get("/{record_id}", response_model=RoleRead)
def get_role(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(role_crud, db, record_id)


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_access],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "role", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_access],
)
def create_role(obj_in: RoleCreate, db: Session = Depends(get_db)):
    return role_crud.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=RoleRead,
    dependencies=[write_access],
)
def update_role(
    record_id: UUID,
    obj_in: RoleUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(role_crud, db, record_id)
    return role_crud.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[admin_access])
def delete_role(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(role_crud, db, record_id)
    if db_obj.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"System role '{db_obj.name}' cannot be deleted.",
        )
    try:
        ensure_can_delete(db, "role", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    deleted = role_crud.delete(db, record_id=record_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    log_record_deleted(
        db,
        user=current_user,
        entity_key="role",
        record_id=record_id,
        record_name=db_obj.name,
    )
