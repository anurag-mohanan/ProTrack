"""Business-day and holiday helpers."""

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.foundation import Holiday


def is_holiday(db: Session, day: date, *, region: str | None = None) -> bool:
    return day in load_holiday_dates(db, day, day, region=region)


def load_holiday_dates(
    db: Session,
    start: date,
    end: date,
    *,
    region: str | None = None,
) -> set[date]:
    """Return non-working holiday dates within the inclusive range."""
    stmt = select(Holiday).where(
        or_(
            Holiday.holiday_date.between(start, end),
            Holiday.is_recurring.is_(True),
        )
    )
    if region:
        stmt = stmt.where(or_(Holiday.region.is_(None), Holiday.region == region))
    rows = db.scalars(stmt).all()

    holidays: set[date] = set()
    for row in rows:
        if row.is_working_day:
            continue
        if row.is_recurring:
            for year in range(start.year, end.year + 1):
                try:
                    candidate = date(year, row.holiday_date.month, row.holiday_date.day)
                except ValueError:
                    continue
                if start <= candidate <= end:
                    holidays.add(candidate)
        elif start <= row.holiday_date <= end:
            holidays.add(row.holiday_date)
    return holidays


def is_holiday_cached(holidays: set[date], day: date) -> bool:
    return day in holidays


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
