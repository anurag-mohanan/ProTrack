from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.core.system_roles import SYSTEM_ROLE_NAMES
from app.crud import role as role_crud
from app.models.models import User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.identity import RoleCreate, RoleRead, RoleUpdate
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/roles",
    tags=["roles"],
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)

write_access = Depends(require_roles("Admin", "Engineering Manager"))
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
