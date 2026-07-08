"""Unit tests for the calendar-month timesheet locking policy."""

from datetime import date

from app.core.timesheet_locking import (
    is_timesheet_month_calendar_locked,
    months_before_current,
)

TODAY = date(2026, 7, 15)  # Current month = July 2026


def test_current_month_is_editable():
    assert months_before_current(date(2026, 7, 1), today=TODAY) == 0
    assert is_timesheet_month_calendar_locked(date(2026, 7, 31), today=TODAY) is False


def test_previous_month_is_editable():
    assert months_before_current(date(2026, 6, 10), today=TODAY) == 1
    assert is_timesheet_month_calendar_locked(date(2026, 6, 30), today=TODAY) is False


def test_two_months_back_is_locked():
    assert months_before_current(date(2026, 5, 20), today=TODAY) == 2
    assert is_timesheet_month_calendar_locked(date(2026, 5, 1), today=TODAY) is True


def test_older_months_are_locked():
    assert is_timesheet_month_calendar_locked(date(2026, 4, 1), today=TODAY) is True
    assert is_timesheet_month_calendar_locked(date(2025, 12, 1), today=TODAY) is True


def test_year_boundary_editable():
    jan = date(2026, 1, 10)
    # Current month = January 2026 -> December 2025 must remain editable
    assert is_timesheet_month_calendar_locked(date(2025, 12, 5), today=jan) is False
    # November 2025 is two months back -> locked
    assert is_timesheet_month_calendar_locked(date(2025, 11, 5), today=jan) is True


def test_admin_override_unlocks_everything():
    assert (
        is_timesheet_month_calendar_locked(
            date(2020, 1, 1), today=TODAY, admin_override=True
        )
        is False
    )
