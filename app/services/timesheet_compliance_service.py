"""Timesheet compliance helpers for manager dashboards."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Timesheet, TimesheetEntry, User
from app.schemas.dashboard import MissingTimesheetRow
from app.services.holiday_service import load_holiday_dates


def _is_working_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def _consecutive_missing_working_days(
    *,
    last_entry: date | None,
    today: date,
    holidays: set[date],
) -> int:
    if last_entry is None:
        cursor = today
        missing = 0
        while missing < 30:
            if _is_working_day(cursor, holidays):
                missing += 1
                if missing >= 3:
                    break
            cursor -= timedelta(days=1)
        return missing

    missing = 0
    cursor = today
    while cursor > last_entry and missing < 30:
        if _is_working_day(cursor, holidays):
            missing += 1
        cursor -= timedelta(days=1)
    return missing


def get_missing_timesheet_rows(
    db: Session,
    *,
    min_missing_days: int = 3,
    limit: int = 25,
) -> list[MissingTimesheetRow]:
    today = date.today()
    holidays = load_holiday_dates(db, today - timedelta(days=45), today)

    users = db.scalars(
        select(User)
        .where(
            User.requires_timesheet.is_(True),
            User.is_active.is_(True),
            User.is_archived.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(User.last_name, User.first_name)
    ).all()

    rows: list[MissingTimesheetRow] = []
    for person in users:
        last_entry = db.scalar(
            select(func.max(TimesheetEntry.entry_date))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == person.id,
                TimesheetEntry.is_deleted.is_(False),
            )
        )
        missing_days = _consecutive_missing_working_days(
            last_entry=last_entry,
            today=today,
            holidays=holidays,
        )
        if missing_days >= min_missing_days:
            rows.append(
                MissingTimesheetRow(
                    user_id=person.id,
                    employee_name=f"{person.first_name} {person.last_name}".strip(),
                    last_entry_date=last_entry,
                    missing_days=missing_days,
                )
            )

    rows.sort(key=lambda row: (-row.missing_days, row.employee_name))
    return rows[:limit]
