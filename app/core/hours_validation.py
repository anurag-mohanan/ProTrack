"""Centralized timesheet hour validation rules."""

from __future__ import annotations

from decimal import Decimal

from app.core.exceptions import ProTrackValidationError

MAX_HOURS_PER_ENTRY = Decimal("24")
MIN_NON_PRODUCTIVE_HOURS = Decimal("0")
MIN_PRODUCTIVE_HOURS = Decimal("0")


def validate_timesheet_hours(
    hours: Decimal | int | float | str,
    *,
    allow_zero: bool,
) -> Decimal:
    value = Decimal(str(hours))
    if value < MIN_NON_PRODUCTIVE_HOURS:
        raise ProTrackValidationError("Hours cannot be negative")
    if value > MAX_HOURS_PER_ENTRY:
        raise ProTrackValidationError("Hours cannot exceed 24")
    if not allow_zero and value <= MIN_PRODUCTIVE_HOURS:
        raise ProTrackValidationError("Hours must be greater than 0 for productive work")
    if (value * 2) % 1 != 0:
        raise ProTrackValidationError("Hours must be in 0.5 increments")
    return value

