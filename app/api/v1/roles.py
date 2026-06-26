from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.system_roles import SYSTEM_ROLE_NAMES
from app.crud import role as role_crud
from app.schemas.identity import RoleCreate, RoleRead, RoleUpdate

router = APIRouter(
    prefix="/roles",
    tags=["roles"],
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
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


@router.post(
    "",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)
def create_role(obj_in: RoleCreate, db: Session = Depends(get_db)):
    return role_crud.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=RoleRead,
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)
def update_role(
    record_id: UUID,
    obj_in: RoleUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(role_crud, db, record_id)
    return role_crud.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(record_id: UUID, db: Session = Depends(get_db)):
    db_obj = get_object_or_404(role_crud, db, record_id)
    if db_obj.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"System role '{db_obj.name}' cannot be deleted.",
        )
    deleted = role_crud.delete(db, record_id=record_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
