from uuid import UUID

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Query, Session, get_db, status
from app.crud.timesheet_entry import timesheet_entry
from app.models.models import TimesheetEntry, User
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetEntryRead, TimesheetEntryUpdate

router = APIRouter(
    prefix="/timesheet-entries",
    tags=["timesheet-entries"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[TimesheetEntryRead])
def list_timesheet_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    timesheet_id: UUID | None = None,
    project_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {
        key: value
        for key, value in {"timesheet_id": timesheet_id, "project_id": project_id}.items()
        if value is not None
    }
    return timesheet_entry.get_multi(
        db, skip=skip, limit=limit, filters=filters or None
    )


@router.get("/{record_id}", response_model=TimesheetEntryRead)
def get_timesheet_entry(record_id: UUID, db: Session = Depends(get_db)):
    row = timesheet_entry.get(db, record_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return row


@router.post("", response_model=TimesheetEntryRead, status_code=status.HTTP_201_CREATED)
def create_timesheet_entry(
    obj_in: TimesheetEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return timesheet_entry.create(db, obj_in=obj_in, actor=current_user)


@router.patch("/{record_id}", response_model=TimesheetEntryRead)
def update_timesheet_entry(
    record_id: UUID,
    obj_in: TimesheetEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = timesheet_entry.get(db, record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return timesheet_entry.update(db, db_obj=db_obj, obj_in=obj_in, actor=current_user)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timesheet_entry(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = timesheet_entry.delete(db, record_id=record_id, actor=current_user)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
