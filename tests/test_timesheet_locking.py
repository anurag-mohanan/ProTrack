"""Unit tests for the calendar-month timesheet locking policy.

Business rule: editable while the month is the current month or within the
previous two calendar months. Older than two months is locked. Workflow status
(draft/submitted/approved/rejected) does NOT affect editability.
"""

from datetime import date

from app.core.timesheet_locking import (
    can_edit_timesheet_month,
    is_timesheet_month_calendar_locked,
    months_before_current,
)

TODAY = date(2026, 7, 15)  # Current month = July 2026


def test_current_month_is_editable():
    assert months_before_current(date(2026, 7, 1), today=TODAY) == 0
    assert is_timesheet_month_calendar_locked(date(2026, 7, 31), today=TODAY) is False
    assert can_edit_timesheet_month(2026, 7, today=TODAY) is True


def test_previous_month_is_editable():
    assert months_before_current(date(2026, 6, 10), today=TODAY) == 1
    assert is_timesheet_month_calendar_locked(date(2026, 6, 30), today=TODAY) is False
    assert can_edit_timesheet_month(2026, 6, today=TODAY) is True


def test_two_months_back_is_editable():
    assert months_before_current(date(2026, 5, 20), today=TODAY) == 2
    assert is_timesheet_month_calendar_locked(date(2026, 5, 1), today=TODAY) is False
    assert can_edit_timesheet_month(2026, 5, today=TODAY) is True


def test_three_months_back_is_locked():
    assert months_before_current(date(2026, 4, 20), today=TODAY) == 3
    assert is_timesheet_month_calendar_locked(date(2026, 4, 1), today=TODAY) is True
    assert can_edit_timesheet_month(2026, 4, today=TODAY) is False


def test_older_months_are_locked():
    assert is_timesheet_month_calendar_locked(date(2026, 3, 1), today=TODAY) is True
    assert is_timesheet_month_calendar_locked(date(2025, 12, 1), today=TODAY) is True


def test_year_boundary_editable():
    jan = date(2026, 1, 10)
    # Current month = January 2026 -> November 2025 (two months back) editable
    assert is_timesheet_month_calendar_locked(date(2025, 11, 5), today=jan) is False
    assert can_edit_timesheet_month(2025, 11, today=jan) is True
    # October 2025 is three months back -> locked
    assert is_timesheet_month_calendar_locked(date(2025, 10, 5), today=jan) is True
    assert can_edit_timesheet_month(2025, 10, today=jan) is False


def test_admin_override_unlocks_everything():
    assert (
        is_timesheet_month_calendar_locked(
            date(2020, 1, 1), today=TODAY, admin_override=True
        )
        is False
    )
    assert can_edit_timesheet_month(2020, 1, today=TODAY, admin_override=True) is True
