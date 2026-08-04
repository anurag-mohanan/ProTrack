from datetime import timedelta
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
    limit: int = Query(100, ge=1, le=10000),
    user_id: UUID | None = None,
    status: TimesheetStatus | None = None,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.timesheet_overview_service import (
        get_timesheet_visible_user_ids,
        month_bounds_from_value,
    )

    # Month-scoped list must filter in SQL before limit. Fetching a global page
    # then filtering in Python silently drops most designers' weeks.
    if month is not None:
        month_start, month_end = month_bounds_from_value(month)
        week_overlap_start = month_start - timedelta(days=6)
        stmt = select(Timesheet).where(
            Timesheet.week_start >= week_overlap_start,
            Timesheet.week_start <= month_end,
        )
        if status is not None:
            stmt = stmt.where(Timesheet.status == status)
        if user_id is not None:
            stmt = stmt.where(Timesheet.user_id == user_id)
        else:
            visible = get_timesheet_visible_user_ids(
                db,
                current_user,
                range_start=month_start,
                range_end=month_end,
            )
            if visible is not None:
                if not visible:
                    return []
                stmt = stmt.where(Timesheet.user_id.in_(tuple(visible)))
        stmt = stmt.order_by(Timesheet.week_start.desc(), Timesheet.user_id).offset(skip).limit(limit)
        candidates = list(db.scalars(stmt).all())
        # Keep weeks that actually overlap the calendar month.
        rows = [
            row
            for row in candidates
            if row.week_start <= month_end
            and (row.week_start + timedelta(days=6)) >= month_start
        ]
        return rows

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
