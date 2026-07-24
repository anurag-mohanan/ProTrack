"""Calendar-month rules for timesheet edit locking.

Business rule: a timesheet is editable while its month is the current month or
within the previous N calendar months (org policy pack). Anything older is
hard-locked (archived). Workflow status (draft/submitted/approved/rejected)
does NOT affect editability.

Soft-lock: the oldest still-editable month can show a warning banner before
hard archive (R2 operational control).
"""

from __future__ import annotations

from datetime import date

from app.core import config as app_config

# Fallback when config is unavailable (tests importing this module early).
_DEFAULT_EDITABLE_MONTHS_BACK = 2


def editable_months_back() -> int:
    value = getattr(app_config, "TIMESHEET_EDITABLE_MONTHS_BACK", _DEFAULT_EDITABLE_MONTHS_BACK)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return _DEFAULT_EDITABLE_MONTHS_BACK


def soft_lock_enabled() -> bool:
    return bool(getattr(app_config, "TIMESHEET_SOFT_LOCK_ENABLED", True))


# Back-compat alias used by older imports/tests.
EDITABLE_MONTHS_BACK = _DEFAULT_EDITABLE_MONTHS_BACK


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
    months_back: int | None = None,
) -> bool:
    """Central editability rule based purely on calendar position.

    Returns True when the month is the current month or within the previous
    N calendar months. Admins always edit.
    """
    if admin_override:
        return True
    window = editable_months_back() if months_back is None else months_back
    return months_before_current(date(year, month, 1), today=today) <= window


def is_timesheet_month_calendar_locked(
    value: date,
    *,
    today: date | None = None,
    admin_override: bool = False,
    months_back: int | None = None,
) -> bool:
    """
    Hard-lock timesheets older than the org editable window.

    Example (current month = July, months_back = 2):
    - July, June, May → editable
    - April and older → locked (unless admin_override)
    """
    if admin_override:
        return False
    return not can_edit_timesheet_month(
        value.year,
        value.month,
        today=today,
        months_back=months_back,
    )


def is_timesheet_month_soft_locked(
    value: date,
    *,
    today: date | None = None,
    admin_override: bool = False,
    months_back: int | None = None,
) -> bool:
    """True when the month is the last editable month (about to hard-lock)."""
    if admin_override or not soft_lock_enabled():
        return False
    window = editable_months_back() if months_back is None else months_back
    if window <= 0:
        return False
    age = months_before_current(month_start(value), today=today)
    return age == window


TIMESHEET_CALENDAR_LOCKED_MESSAGE = (
    "This timesheet is archived because it is older than the org editable window."
)

TIMESHEET_SOFT_LOCK_MESSAGE = (
    "This month is in the soft-lock window — it will archive at the next month rollover. "
    "Finish outstanding entries soon."
)


def timesheet_policy_dict() -> dict[str, object]:
    return {
        "editable_months_back": editable_months_back(),
        "soft_lock_enabled": soft_lock_enabled(),
        "hard_lock_message": TIMESHEET_CALENDAR_LOCKED_MESSAGE,
        "soft_lock_message": TIMESHEET_SOFT_LOCK_MESSAGE,
    }
