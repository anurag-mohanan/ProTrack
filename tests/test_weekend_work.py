"""Weekend work KPI derivation from timesheet entry dates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.services.reporting.weekend_work_service import (
    aggregate_weekend_kpi,
    is_weekend_date,
    weekend_hours_for_entry,
)


def test_is_weekend_date_sat_sun_only():
    assert is_weekend_date(date(2026, 4, 3)) is False  # Friday
    assert is_weekend_date(date(2026, 4, 4)) is True  # Saturday
    assert is_weekend_date(date(2026, 4, 5)) is True  # Sunday
    assert is_weekend_date(date(2026, 4, 6)) is False  # Monday
    assert is_weekend_date(None) is False


def test_weekend_hours_for_entry():
    assert weekend_hours_for_entry(date(2026, 4, 3), Decimal("8")) == Decimal("0")
    assert weekend_hours_for_entry(date(2026, 4, 4), Decimal("4")) == Decimal("4")
    assert weekend_hours_for_entry(date(2026, 4, 5), Decimal("6")) == Decimal("6")
    assert weekend_hours_for_entry(date(2026, 4, 4), Decimal("0")) == Decimal("0")


def test_aggregate_weekend_kpi_employee_period():
    user_a = uuid4()
    user_b = uuid4()
    kpi = aggregate_weekend_kpi(
        [
            (date(2026, 4, 3), Decimal("8"), user_a),  # Fri
            (date(2026, 4, 4), Decimal("4"), user_a),  # Sat
            (date(2026, 4, 5), Decimal("6"), user_a),  # Sun
            (date(2026, 4, 6), Decimal("8"), user_a),  # Mon
            (date(2026, 4, 5), Decimal("8"), user_b),  # Sun
        ]
    )
    assert kpi.weekday_hours == Decimal("16")
    assert kpi.saturday_hours == Decimal("4")
    assert kpi.sunday_hours == Decimal("14")
    assert kpi.weekend_hours == Decimal("18")
    assert kpi.total_hours == Decimal("34")
    assert kpi.weekend_working_days == 2
    assert kpi.employees_worked_weekend == 2
    assert kpi.weekend_work_percent == Decimal("52.9")


def test_edit_saturday_hours_updates_kpi():
    user = uuid4()
    before = aggregate_weekend_kpi([(date(2026, 4, 4), Decimal("4"), user)])
    assert before.weekend_hours == Decimal("4")
    after = aggregate_weekend_kpi([(date(2026, 4, 4), Decimal("6"), user)])
    assert after.weekend_hours == Decimal("6")


def test_delete_saturday_clears_weekend():
    user = uuid4()
    after_delete = aggregate_weekend_kpi(
        [
            (date(2026, 4, 3), Decimal("8"), user),
        ]
    )
    assert after_delete.weekend_hours == Decimal("0")
    assert after_delete.employees_worked_weekend == 0
