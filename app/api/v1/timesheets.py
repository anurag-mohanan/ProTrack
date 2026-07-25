from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Query, Session, get_db, status
from app.core.exceptions import ProTrackValidationError
from app.crud.timesheet import timesheet
from app.models.models import Timesheet, User
from app.models.enums import TimesheetStatus
from app.schemas.timesheet import (
    TimesheetApprovalRequest,
    TimesheetCreate,
    TimesheetEntryCreate,
    TimesheetEntryRead,
    TimesheetEntryUpdate,
    TimesheetOverviewContext,
    TimesheetRead,
    TimesheetRejectRequest,
    TimesheetUpdate,
)
from app.services.timesheet_overview_service import build_timesheet_overview
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
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {
        key: value
        for key, value in {"user_id": user_id, "status": status}.items()
        if value is not None
    }
    rows = timesheet.get_multi_for_user(
        db,
        actor=current_user,
        skip=skip,
        limit=limit,
        filters=filters or None,
    )
    if month is None:
        return rows
    year, month_num = map(int, month.split("-"))
    month_start = date(year, month_num, 1)
    if month_num == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month_num + 1, 1)
    month_end = month_end - timedelta(days=1)
    return [
        row
        for row in rows
        if row.week_start <= month_end and (row.week_start + timedelta(days=6)) >= month_start
    ]


@router.get("/overview", response_model=TimesheetOverviewContext)
def get_timesheet_overview(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TimesheetOverviewContext(
        **build_timesheet_overview(db, current_user, month=month)
    )


@router.post("/ensure-week", response_model=TimesheetRead)
def ensure_week_timesheet(
    obj_in: TimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.scalar(
        select(Timesheet).where(
            Timesheet.user_id == obj_in.user_id,
            Timesheet.week_start == obj_in.week_start,
        )
    )
    if existing is not None:
        visible = timesheet.get_for_user(db, actor=current_user, record_id=existing.id)
        if visible is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return visible
    return timesheet.create_for_user(db, actor=current_user, obj_in=obj_in)


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
