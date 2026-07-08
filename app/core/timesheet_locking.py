"""Calendar-month rules for timesheet edit locking.

Business rule: a timesheet is editable while its month is the current month or
within the previous two calendar months. Anything older than two months is
locked (archived). Workflow status (draft/submitted/approved/rejected) does NOT
affect editability.
"""

from __future__ import annotations

from datetime import date

# Months that remain editable, counting back from the current month.
# 0 = current, 1 = previous, 2 = two months ago. 3+ is locked.
EDITABLE_MONTHS_BACK = 2


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def months_before_current(value: date, *, today: date | None = None) -> int:
    """How many full calendar months before the current month (0 = current)."""
    today = today or date.today()
    current = month_start(today)
    target = month_start(value)
    return (current.year - target.year) * 12 + (current.month - target.month)


def can_edit_timesheet_month(
    year: int,
    month: int,
    *,
    today: date | None = None,
    admin_override: bool = False,
) -> bool:
    """Central editability rule based purely on calendar position.

    Returns True when the month is the current month or within the previous two
    calendar months (i.e. months_before_current <= 2). Admins always edit.
    """
    if admin_override:
        return True
    return months_before_current(date(year, month, 1), today=today) <= EDITABLE_MONTHS_BACK


def is_timesheet_month_calendar_locked(
    value: date,
    *,
    today: date | None = None,
    admin_override: bool = False,
) -> bool:
    """
    Lock timesheets older than two calendar months.

    Example (current month = July):
    - July, June, May → editable
    - April and older → locked (unless admin_override)
    """
    if admin_override:
        return False
    return not can_edit_timesheet_month(value.year, value.month, today=today)


TIMESHEET_CALENDAR_LOCKED_MESSAGE = (
    "This timesheet is archived because it is older than two months."
)
