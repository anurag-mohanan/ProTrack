"""Designer utilization capacity — working days from team assignment windows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.services.reporting.periods import count_working_days


def _decimal(value: Decimal | int | float) -> Decimal:
    return Decimal(str(value))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def applicable_membership_windows(
    intervals: list[tuple[date, date]],
    *,
    period_start: date,
    period_end: date,
) -> list[tuple[date, date]]:
    """Clip membership intervals to the reporting period."""
    clipped: list[tuple[date, date]] = []
    for start, end in intervals:
        clipped_start = max(start, period_start)
        clipped_end = min(end, period_end)
        if clipped_start <= clipped_end:
            clipped.append((clipped_start, clipped_end))
    return clipped


def count_applicable_working_days(
    intervals: list[tuple[date, date]],
    *,
    period_start: date,
    period_end: date,
    holidays: set[date],
) -> tuple[date | None, date | None, int]:
    """Sum working days across membership windows within the report period."""
    windows = applicable_membership_windows(
        intervals, period_start=period_start, period_end=period_end
    )
    if not windows:
        return None, None, 0

    total_days = 0
    applicable_start: date | None = None
    applicable_end: date | None = None
    for start, end in windows:
        total_days += count_working_days(start, end, holidays)
        if applicable_start is None or start < applicable_start:
            applicable_start = start
        if applicable_end is None or end > applicable_end:
            applicable_end = end
    return applicable_start, applicable_end, total_days


def designer_available_hours(
    intervals: list[tuple[date, date]],
    *,
    period_start: date,
    period_end: date,
    holidays: set[date],
    daily_hours: Decimal,
) -> tuple[date | None, date | None, int, Decimal]:
    start, end, working_days = count_applicable_working_days(
        intervals,
        period_start=period_start,
        period_end=period_end,
        holidays=holidays,
    )
    available = _decimal(working_days) * daily_hours
    return start, end, working_days, available


def calculate_utilization_percent(
    productive_hours: Decimal,
    available_hours: Decimal,
) -> Decimal | None:
    """Return utilization % or None when there is no applicable capacity."""
    if available_hours <= 0:
        return None
    return _pct(productive_hours, available_hours)


def membership_windows_by_team_user(
    membership_map: dict[UUID, list[tuple[date, date]]],
    *,
    user_id: UUID,
    team_id: UUID | None,
    team_ids_filter: frozenset[UUID] | set[UUID] | None,
) -> list[tuple[date, date]]:
    """Resolve membership intervals for a designer row on a specific team."""
    if team_id is None:
        return membership_map.get(user_id, [])
    if team_ids_filter is not None and team_id not in team_ids_filter:
        return []
    return membership_map.get(user_id, [])
