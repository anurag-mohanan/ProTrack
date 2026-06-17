from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_object_or_404
from app.crud import user as user_crud
from app.schemas.identity import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    role_id: UUID | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    filters = {}
    if role_id is not None:
        filters["role_id"] = role_id
    if is_active is not None:
        filters["is_active"] = is_active
    return user_crud.get_multi(db, skip=skip, limit=limit, filters=filters)


@router.get("/{record_id}", response_model=UserRead)
def get_user(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(user_crud, db, record_id)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(obj_in: UserCreate, db: Session = Depends(get_db)):
    return user_crud.create(db, obj_in=obj_in)


@router.patch("/{record_id}", response_model=UserRead)
def update_user(
    record_id: UUID,
    obj_in: UserUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    return user_crud.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(record_id: UUID, db: Session = Depends(get_db)):
    deleted = user_crud.delete(db, record_id=record_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
