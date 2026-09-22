"""Weekend work detection and KPI aggregation from timesheet entry dates.

Authoritative rules:
- Saturday (weekday 5) and Sunday (weekday 6) are weekend work.
- Classification uses the stored entry_date, not UI selection alone.
- weekend_hours = recorded hours when the date is a weekend; else 0.
- Does not change utilization available-hours (Mon–Fri − holidays).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from uuid import UUID


def _decimal(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def is_weekend_date(value: date | None) -> bool:
    """True when the calendar date is Saturday or Sunday."""
    if value is None:
        return False
    return value.weekday() >= 5


def is_saturday(value: date | None) -> bool:
    return value is not None and value.weekday() == 5


def is_sunday(value: date | None) -> bool:
    return value is not None and value.weekday() == 6


def weekend_hours_for_entry(entry_date: date | None, hours: Decimal | int | float | None) -> Decimal:
    """Hours that count as weekend work for a single entry."""
    amount = _decimal(hours)
    if amount <= 0 or not is_weekend_date(entry_date):
        return Decimal("0")
    return amount


@dataclass
class WeekendKpi:
    weekday_hours: Decimal = Decimal("0")
    saturday_hours: Decimal = Decimal("0")
    sunday_hours: Decimal = Decimal("0")
    weekend_hours: Decimal = Decimal("0")
    total_hours: Decimal = Decimal("0")
    weekend_working_days: int = 0
    weekend_entries: int = 0
    employees_worked_weekend: int = 0
    weekend_work_percent: Decimal = Decimal("0")
    weekend_dates: set[date] = field(default_factory=set)
    weekend_user_ids: set[UUID] = field(default_factory=set)

    def finalize(self) -> "WeekendKpi":
        self.weekend_hours = self.saturday_hours + self.sunday_hours
        self.weekend_working_days = len(self.weekend_dates)
        self.employees_worked_weekend = len(self.weekend_user_ids)
        self.weekend_work_percent = _pct(self.weekend_hours, self.total_hours)
        return self


def add_entry_to_weekend_kpi(
    kpi: WeekendKpi,
    *,
    entry_date: date | None,
    hours: Decimal | int | float | None,
    user_id: UUID | None = None,
) -> None:
    """Accumulate one timesheet entry into a weekend KPI bucket."""
    amount = _decimal(hours)
    if amount <= 0 or entry_date is None:
        return
    kpi.total_hours += amount
    if is_saturday(entry_date):
        kpi.saturday_hours += amount
        kpi.weekend_entries += 1
        kpi.weekend_dates.add(entry_date)
        if user_id is not None:
            kpi.weekend_user_ids.add(user_id)
    elif is_sunday(entry_date):
        kpi.sunday_hours += amount
        kpi.weekend_entries += 1
        kpi.weekend_dates.add(entry_date)
        if user_id is not None:
            kpi.weekend_user_ids.add(user_id)
    else:
        kpi.weekday_hours += amount


def aggregate_weekend_kpi(
    entries: Iterable[tuple[date | None, Decimal | int | float | None, UUID | None]],
) -> WeekendKpi:
    """Aggregate (entry_date, hours, user_id) triples into weekend KPI."""
    kpi = WeekendKpi()
    for entry_date, hours, user_id in entries:
        add_entry_to_weekend_kpi(kpi, entry_date=entry_date, hours=hours, user_id=user_id)
    return kpi.finalize()


def weekend_fields_dict(kpi: WeekendKpi) -> dict:
    """Serialize for DesignerProductivityRow / overview payloads."""
    return {
        "weekday_hours": kpi.weekday_hours,
        "saturday_hours": kpi.saturday_hours,
        "sunday_hours": kpi.sunday_hours,
        "weekend_hours": kpi.weekend_hours,
        "weekend_working_days": kpi.weekend_working_days,
        "weekend_entries": kpi.weekend_entries,
        "weekend_work_percent": kpi.weekend_work_percent,
        "employees_worked_weekend": kpi.employees_worked_weekend,
    }
