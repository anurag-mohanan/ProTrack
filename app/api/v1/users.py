import secrets
import string

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.security import hash_password
from app.crud import user as user_crud
from app.schemas.identity import (
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)


def _generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(length))


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


@router.post("/{record_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    record_id: UUID,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    if body.generate_temporary or not body.password:
        temporary_password = _generate_temporary_password()
    else:
        temporary_password = body.password

    user_crud.update(
        db,
        db_obj=db_obj,
        obj_in={
            "password_hash": hash_password(temporary_password),
            "must_change_password": True,
        },
    )
    return ResetPasswordResponse(
        temporary_password=temporary_password,
        message="Password reset successfully. User must change password on next login.",
    )


@router.delete("/{record_id}", status_code=status.HTTP_403_FORBIDDEN)
def delete_user(record_id: UUID):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User deletion is disabled. Deactivate the user instead.",
    )
