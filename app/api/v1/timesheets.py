from uuid import UUID

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Query, Session, get_db, status
from app.core.exceptions import ProTrackValidationError
from app.crud.timesheet import timesheet
from app.crud.timesheet_entry import timesheet_entry
from app.models.models import User
from app.models.enums import TimesheetStatus
from app.schemas.timesheet import (
    TimesheetApprovalRequest,
    TimesheetCreate,
    TimesheetEntryCreate,
    TimesheetEntryRead,
    TimesheetEntryUpdate,
    TimesheetRead,
    TimesheetRejectRequest,
    TimesheetUpdate,
)
from app.services.timesheet_workflow_service import (
    approve_timesheet,
    reject_timesheet,
    return_timesheet_to_draft,
    submit_timesheet,
)

router = APIRouter(
    prefix="/timesheets",
    tags=["timesheets"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[TimesheetRead])
def list_timesheets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: UUID | None = None,
    status: TimesheetStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {
        key: value
        for key, value in {"user_id": user_id, "status": status}.items()
        if value is not None
    }
    return timesheet.get_multi_for_user(
        db,
        actor=current_user,
        skip=skip,
        limit=limit,
        filters=filters or None,
    )


@router.get("/{record_id}", response_model=TimesheetRead)
def get_timesheet(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return row


@router.post("", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED)
def create_timesheet(
    obj_in: TimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return timesheet.create_for_user(db, actor=current_user, obj_in=obj_in)


@router.patch("/{record_id}", response_model=TimesheetRead)
def update_timesheet(
    record_id: UUID,
    obj_in: TimesheetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return timesheet.update_for_user(db, actor=current_user, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timesheet(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = timesheet.delete_for_user(db, actor=current_user, record_id=record_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")


def _workflow_error_handler(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/{record_id}/submit", response_model=TimesheetRead)
def submit_timesheet_action(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        return submit_timesheet(db, timesheet=db_obj, actor=current_user)
    except ProTrackValidationError as exc:
        raise _workflow_error_handler(exc) from exc


@router.post("/{record_id}/approve", response_model=TimesheetRead)
def approve_timesheet_action(
    record_id: UUID,
    body: TimesheetApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        return approve_timesheet(
            db,
            timesheet=db_obj,
            actor=current_user,
            comments=body.comments,
        )
    except ProTrackValidationError as exc:
        raise _workflow_error_handler(exc) from exc


@router.post("/{record_id}/reject", response_model=TimesheetRead)
def reject_timesheet_action(
    record_id: UUID,
    body: TimesheetRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        return reject_timesheet(
            db,
            timesheet=db_obj,
            actor=current_user,
            comments=body.comments,
        )
    except ProTrackValidationError as exc:
        raise _workflow_error_handler(exc) from exc


@router.post("/{record_id}/return-to-draft", response_model=TimesheetRead)
def return_to_draft_action(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet.get_for_user(db, actor=current_user, record_id=record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    try:
        return return_timesheet_to_draft(db, timesheet=db_obj, actor=current_user)
    except ProTrackValidationError as exc:
        raise _workflow_error_handler(exc) from exc
