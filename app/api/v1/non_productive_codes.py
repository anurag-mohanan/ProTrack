from uuid import UUID

from fastapi import HTTPException, status

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.exceptions import ProTrackValidationError
from app.crud.non_productive_code import non_productive_code
from app.models.models import User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.organization import (
    NonProductiveCodeCreate,
    NonProductiveCodeRead,
    NonProductiveCodeUpdate,
)
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/non-productive-codes",
    tags=["non-productive-codes"],
    dependencies=[Depends(get_current_user)],
)

write_dependency = Depends(require_roles("Admin", "Engineering Manager"))
admin_dependency = Depends(require_roles("Admin"))


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


@router.get("", response_model=list[NonProductiveCodeRead])
def list_non_productive_codes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_archived: bool = True,
    db: Session = Depends(get_db),
):
    rows = non_productive_code.get_multi(db, skip=0, limit=1000)
    if not include_archived:
        rows = [row for row in rows if not row.is_archived]
    rows.sort(key=lambda row: (row.sort_order, row.code))
    return rows[skip : skip + limit]


@router.get("/{record_id}", response_model=NonProductiveCodeRead)
def get_non_productive_code(record_id: UUID, db: Session = Depends(get_db)):
    row = non_productive_code.get(db, record_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return row


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_dependency],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "np_code", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "",
    response_model=NonProductiveCodeRead,
    dependencies=[write_dependency],
)
def create_non_productive_code(
    obj_in: NonProductiveCodeCreate,
    db: Session = Depends(get_db),
):
    return non_productive_code.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=NonProductiveCodeRead,
    dependencies=[write_dependency],
)
def update_non_productive_code(
    record_id: UUID,
    obj_in: NonProductiveCodeUpdate,
    db: Session = Depends(get_db),
):
    db_obj = non_productive_code.get(db, record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return non_productive_code.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[admin_dependency],
)
def delete_non_productive_code(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = non_productive_code.get(db, record_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        ensure_can_delete(db, "np_code", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    record_name = row.name or row.code
    non_productive_code.delete(db, record_id=record_id)
    log_record_deleted(
        db,
        user=current_user,
        entity_key="np_code",
        record_id=record_id,
        record_name=record_name,
    )
