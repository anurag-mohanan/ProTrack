import secrets
import string

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import can_view_deleted_projects, is_admin
from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.release_mode import is_internal_release
from app.core.security import hash_password
from app.crud.auth import reset_login_lock
from app.crud import user as user_crud
from app.crud.user import build_user_read
from app.models.enums import ActivityAction, EntityType
from app.models.models import User
from app.schemas.identity import (
    MustChangePasswordRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserCreate,
    UserDeleteCheck,
    UserRead,
    UserUpdate,
)
from app.schemas.auth import UserProfileRead
from app.services.user_profile_service import get_user_profile
from app.services.activity_service import log_activity
from app.services.user_lifecycle_service import (
    archive_user,
    get_user_delete_dependencies,
    permanent_delete_user,
    restore_user_from_archive,
    restore_user_from_deleted,
    soft_delete_user,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles("Admin"))],
)


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
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
    include_archived: bool = False,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if include_deleted and not can_view_deleted_projects(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    users = user_crud.get_multi(db, skip=skip, limit=limit)
    filtered: list[User] = []
    for row in users:
        if row.is_deleted and not include_deleted:
            continue
        if row.is_archived and not include_archived and not row.is_deleted:
            continue
        if role_id is not None and row.role_id != role_id:
            continue
        if is_active is not None and row.is_active != is_active:
            continue
        filtered.append(row)
    return [build_user_read(db, row) for row in filtered]


@router.get("/deleted", response_model=list[UserRead])
def list_deleted_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    users = user_crud.get_multi(db, skip=0, limit=10000)
    deleted = [row for row in users if row.is_deleted]
    return [build_user_read(db, row) for row in deleted[skip : skip + limit]]


@router.get("/{record_id}", response_model=UserRead)
def get_user(record_id: UUID, db: Session = Depends(get_db)):
    db_user = user_crud.get(db, record_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return build_user_read(db, db_user)


@router.get("/{record_id}/profile", response_model=UserProfileRead)
def get_user_profile_detail(
    record_id: UUID,
    db: Session = Depends(get_db),
):
    db_user = user_crud.get(db, record_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_user_profile(db, db_user)


@router.get("/{record_id}/delete-check", response_model=UserDeleteCheck)
def check_user_delete(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_user = user_crud.get(db, record_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    deps = get_user_delete_dependencies(db, record_id)
    return UserDeleteCheck(
        can_permanently_delete=not deps.has_blockers,
        blockers=deps.blocker_messages(),
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(obj_in: UserCreate, db: Session = Depends(get_db)):
    try:
        created = user_crud.create(db, obj_in=obj_in)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return build_user_read(db, created)


@router.patch("/{record_id}", response_model=UserRead)
def update_user(
    record_id: UUID,
    obj_in: UserUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    try:
        updated = user_crud.update(db, db_obj=db_obj, obj_in=obj_in)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return build_user_read(db, updated)


@router.post("/{record_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    record_id: UUID,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=db_obj.id,
        action=ActivityAction.password_reset,
        new_value=db_obj.email,
    )
    return ResetPasswordResponse(
        temporary_password=temporary_password,
        message=(
            "Password reset successfully. User must change password on next login."
            if not is_internal_release()
            else "Password reset successfully. Forced password change is deferred while Internal Release mode is enabled."
        ),
    )


@router.post("/{record_id}/force-password-change", response_model=UserRead)
def force_password_change(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    updated = user_crud.update(
        db,
        db_obj=db_obj,
        obj_in={"must_change_password": True},
    )
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=updated.id,
        action=ActivityAction.password_reset,
        new_value=f"force_change:{updated.email}",
    )
    return build_user_read(db, updated)


@router.post("/{record_id}/must-change-password", response_model=UserRead)
def set_must_change_password(
    record_id: UUID,
    body: MustChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    updated = user_crud.update(
        db,
        db_obj=db_obj,
        obj_in={"must_change_password": body.required},
    )
    action_label = "require" if body.required else "clear"
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=updated.id,
        action=ActivityAction.password_reset,
        new_value=f"{action_label}_must_change:{updated.email}",
    )
    return build_user_read(db, updated)


@router.post("/{record_id}/unlock", response_model=UserRead)
def unlock_user(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    unlocked = reset_login_lock(db, db_obj)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=unlocked.id,
        action=ActivityAction.password_reset,
        new_value=f"unlock:{unlocked.email}",
    )
    return build_user_read(db, unlocked)


@router.post("/{record_id}/set-temporary-password", response_model=ResetPasswordResponse)
def set_temporary_password(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(user_crud, db, record_id)
    updated = user_crud.update(
        db,
        db_obj=db_obj,
        obj_in={
            "password_hash": hash_password(SOFT_LAUNCH_PASSWORD),
            "must_change_password": True,
        },
    )
    unlocked = reset_login_lock(db, updated)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=unlocked.id,
        action=ActivityAction.password_reset,
        new_value=f"soft_launch:{unlocked.email}",
    )
    return ResetPasswordResponse(
        temporary_password=SOFT_LAUNCH_PASSWORD,
        message=(
            "Temporary password set. User must change password on next login."
            if not is_internal_release()
            else f"Temporary password set to {SOFT_LAUNCH_PASSWORD}. Forced password change is deferred while Internal Release mode is enabled."
        ),
    )


@router.post("/{record_id}/archive", response_model=UserRead)
def archive_user_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        archived = archive_user(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.user,
            entity_id=archived.id,
            action=ActivityAction.user_archived,
            new_value=archived.email,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return archived


@router.post("/{record_id}/restore", response_model=UserRead)
def restore_user_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        restored = restore_user_from_archive(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.user,
            entity_id=restored.id,
            action=ActivityAction.user_restored,
            new_value=restored.email,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return restored


@router.post("/{record_id}/soft-delete", response_model=UserRead)
def soft_delete_user_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        deleted = soft_delete_user(db, record_id, current_user)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.user,
            entity_id=deleted.id,
            action=ActivityAction.user_deleted,
            new_value=deleted.email,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return deleted


@router.post("/{record_id}/restore-deleted", response_model=UserRead)
def restore_deleted_user_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        restored = restore_user_from_deleted(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.user,
            entity_id=restored.id,
            action=ActivityAction.user_restored_from_deleted,
            new_value=restored.email,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return restored


@router.delete("/{record_id}", status_code=status.HTTP_403_FORBIDDEN)
def delete_user_legacy(record_id: UUID):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User deletion is disabled. Deactivate or soft-delete the user instead.",
    )


@router.delete("/{record_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_user_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_user = user_crud.get(db, record_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        permanent_delete_user(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.user,
            entity_id=record_id,
            action=ActivityAction.record_deleted,
            new_value=db_user.email,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
