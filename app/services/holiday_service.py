"""Business-day and holiday helpers."""

from datetime import date, timedelta

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import Session

from app.models.foundation import Holiday


def is_holiday(db: Session, day: date, *, region: str | None = None) -> bool:
    stmt = select(Holiday).where(
        or_(
            Holiday.holiday_date == day,
            (
                Holiday.is_recurring.is_(True)
                & (extract("month", Holiday.holiday_date) == day.month)
                & (extract("day", Holiday.holiday_date) == day.day)
            ),
        )
    )
    if region:
        stmt = stmt.where(or_(Holiday.region.is_(None), Holiday.region == region))
    rows = db.scalars(stmt).all()
    if not rows:
        return False
    return not any(row.is_working_day for row in rows)


def is_designer_available_on(db: Session, day: date, *, region: str | None = None) -> bool:
    return not is_holiday(db, day, region=region)


def add_business_days(
    db: Session,
    start: date,
    days: int,
    *,
    region: str | None = None,
) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() >= 5:
            continue
        if is_holiday(db, current, region=region):
            continue
        added += 1
    return current
