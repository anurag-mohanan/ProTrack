"""Calendar-month rules for timesheet edit locking."""

from __future__ import annotations

from datetime import date


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def months_before_current(value: date, *, today: date | None = None) -> int:
    """How many full calendar months before the current month (0 = current)."""
    today = today or date.today()
    current = month_start(today)
    target = month_start(value)
    return (current.year - target.year) * 12 + (current.month - target.month)


def is_timesheet_month_calendar_locked(
    value: date,
    *,
    today: date | None = None,
    admin_override: bool = False,
) -> bool:
    """
    Lock timesheets older than the previous calendar month.

    Example (current month = July):
    - July, June → editable
    - May and older → locked (unless admin_override)
    """
    if admin_override:
        return False
    return months_before_current(value, today=today) >= 2


TIMESHEET_CALENDAR_LOCKED_MESSAGE = (
    "Timesheets for this month are locked. Only the current and previous "
    "calendar months remain editable."
)
