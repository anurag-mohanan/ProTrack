from datetime import date, timedelta
from uuid import UUID

from fastapi.responses import Response
from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Query, Session, get_db, status
from app.core.exceptions import ProTrackValidationError
from app.crud.timesheet import timesheet
from app.models.enums import ActivityAction, EntityType, TimesheetStatus
from app.models.models import Timesheet, User
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
from app.services.activity_service import log_activity
from app.services.reporting.excel.designer_individual_timesheet import (
    generate_designer_individual_timesheet_excel,
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
    period_start: date | None = None,
    period_end: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.timesheet_overview_service import (
        get_timesheet_visible_user_ids,
        resolve_overview_bounds,
    )

    # Range-scoped list must filter in SQL before limit. Fetching a global page
    # then filtering in Python silently drops most designers' weeks.
    if month is not None or period_start is not None or period_end is not None:
        try:
            range_start, range_end = resolve_overview_bounds(
                month=month,
                period_start=period_start,
                period_end=period_end,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        week_overlap_start = range_start - timedelta(days=6)
        stmt = select(Timesheet).where(
            Timesheet.week_start >= week_overlap_start,
            Timesheet.week_start <= range_end,
        )
        if status is not None:
            stmt = stmt.where(Timesheet.status == status)
        if user_id is not None:
            stmt = stmt.where(Timesheet.user_id == user_id)
        else:
            visible = get_timesheet_visible_user_ids(
                db,
                current_user,
                range_start=range_start,
                range_end=range_end,
            )
            if visible is not None:
                if not visible:
                    return []
                stmt = stmt.where(Timesheet.user_id.in_(tuple(visible)))
        stmt = (
            stmt.order_by(Timesheet.week_start.desc(), Timesheet.user_id)
            .offset(skip)
            .limit(limit)
        )
        candidates = list(db.scalars(stmt).all())
        return [
            row
            for row in candidates
            if row.week_start <= range_end
            and (row.week_start + timedelta(days=6)) >= range_start
        ]

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
    period_start: date | None = None,
    period_end: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.timesheet_overview_service import resolve_overview_bounds

    try:
        resolve_overview_bounds(
            month=month,
            period_start=period_start,
            period_end=period_end,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return TimesheetOverviewContext(
        **build_timesheet_overview(
            db,
            current_user,
            month=month,
            period_start=period_start,
            period_end=period_end,
        )
    )


@router.get("/export/designer.xlsx")
def export_designer_timesheet_excel(
    user_id: UUID = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    period_label: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download one designer's timesheet entries for the selected period as Excel."""
    from app.services.timesheet_overview_service import get_timesheet_visible_user_ids

    if period_end < period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be on or after period_start",
        )

    visible = get_timesheet_visible_user_ids(
        db,
        current_user,
        range_start=period_start,
        range_end=period_end,
    )
    if user_id != current_user.id and visible is not None and user_id not in visible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to export this designer's timesheet",
        )

    try:
        content, filename = generate_designer_individual_timesheet_excel(
            db,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.user,
        entity_id=user_id,
        action=ActivityAction.data_exported,
        new_value={
            "report": "designer-timesheet",
            "filename": filename,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
        outcome="success",
        module="timesheets",
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
