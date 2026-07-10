from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.core.exceptions import ProTrackValidationError
from app.crud.working_model import working_model
from app.models.enums import WorkingModelCode
from app.models.models import User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.organization import (
    WorkingModelCreate,
    WorkingModelRead,
    WorkingModelReorderRequest,
    WorkingModelUpdate,
)
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/working-models",
    tags=["working-models"],
    dependencies=[Depends(require_roles("Admin"))],
)

write_access = Depends(require_roles("Admin"))
admin_access = Depends(require_roles("Admin"))


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


@router.get("", response_model=list[WorkingModelRead])
def list_working_models(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_archived: bool = True,
    db: Session = Depends(get_db),
):
    rows = working_model.get_multi(db, skip=0, limit=1000)
    if not include_archived:
        rows = [row for row in rows if not row.is_archived]
    rows.sort(key=lambda row: (row.sort_order, row.name))
    return rows[skip : skip + limit]


@router.get("/strategies", response_model=list[str])
def list_strategy_keys():
    return [item.value for item in WorkingModelCode]


@router.get("/{record_id}", response_model=WorkingModelRead)
def get_working_model(record_id: UUID, db: Session = Depends(get_db)):
    row = working_model.get(db, record_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return row


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_access],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "working_model", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "",
    response_model=WorkingModelRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[write_access],
)
def create_working_model(obj_in: WorkingModelCreate, db: Session = Depends(get_db)):
    return working_model.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=WorkingModelRead,
    dependencies=[write_access],
)
def update_working_model(
    record_id: UUID,
    obj_in: WorkingModelUpdate,
    db: Session = Depends(get_db),
):
    db_obj = working_model.get(db, record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return working_model.update(db, db_obj=db_obj, obj_in=obj_in)


@router.post(
    "/reorder",
    response_model=list[WorkingModelRead],
    dependencies=[write_access],
)
def reorder_working_models(
    body: WorkingModelReorderRequest,
    db: Session = Depends(get_db),
):
    rows = working_model.reorder(db, body.ordered_ids)
    rows.sort(key=lambda row: (row.sort_order, row.name))
    return rows


@router.post(
    "/{record_id}/archive",
    response_model=WorkingModelRead,
    dependencies=[write_access],
)
def archive_working_model(record_id: UUID, db: Session = Depends(get_db)):
    return working_model.archive(db, record_id)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[admin_access],
)
def delete_working_model(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = working_model.get(db, record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        ensure_can_delete(db, "working_model", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    working_model.delete(db, record_id=record_id)
    log_record_deleted(
        db,
        user=current_user,
        entity_key="working_model",
        record_id=record_id,
        record_name=db_obj.name,
    )
