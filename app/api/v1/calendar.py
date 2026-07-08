from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from app.api.auth_deps import get_current_user
from app.api.deps import Session, get_db
from app.schemas.calendar import CalendarEvent
from app.services.calendar_service import get_engineering_calendar

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/engineering", response_model=list[CalendarEvent])
def engineering_calendar(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    anchor = date.today()
    start = start_date or anchor.replace(day=1)
    if end_date is None:
        next_month = (anchor.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month + timedelta(days=32)
        end = end.replace(day=1) - timedelta(days=1)
    else:
        end = end_date
    if end < start:
        end = start
    return get_engineering_calendar(db, start_date=start, end_date=end)
