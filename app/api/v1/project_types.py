from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.crud import project_type as project_type_crud
from app.models.models import User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.templates import (
    ProjectTypeCreate,
    ProjectTypeRead,
    ProjectTypeUpdate,
)
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/project-types",
    tags=["project-types"],
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)

write_access = Depends(require_roles("Admin", "Engineering Manager"))
admin_access = Depends(require_roles("Admin"))


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


@router.get("", response_model=list[ProjectTypeRead])
def list_project_types(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return project_type_crud.get_multi(db, skip=skip, limit=limit)


@router.get("/{record_id}", response_model=ProjectTypeRead)
def get_project_type(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(project_type_crud, db, record_id)


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_access],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "project_type", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "",
    response_model=ProjectTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_access],
)
def create_project_type(obj_in: ProjectTypeCreate, db: Session = Depends(get_db)):
    return project_type_crud.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=ProjectTypeRead,
    dependencies=[write_access],
)
def update_project_type(
    record_id: UUID,
    obj_in: ProjectTypeUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(project_type_crud, db, record_id)
    return project_type_crud.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[admin_access])
def delete_project_type(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(project_type_crud, db, record_id)
    try:
        ensure_can_delete(db, "project_type", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    deleted = project_type_crud.delete(db, record_id=db_obj.id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    log_record_deleted(
        db,
        user=current_user,
        entity_key="project_type",
        record_id=record_id,
        record_name=db_obj.name,
    )
