"""Employment-period cost factors for salary / OpEx (last working day)."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from app.models.finance import Expense
from app.models.models import User


def _month_bounds(as_of: date) -> tuple[date, date, int]:
    days = calendar.monthrange(as_of.year, as_of.month)[1]
    month_start = as_of.replace(day=1)
    month_end = as_of.replace(day=days)
    return month_start, month_end, days


def employment_salary_factor(user: User, *, as_of: date) -> Decimal:
    """Fraction of monthly salary recognized for the calendar month of ``as_of``.

    - Left in a prior month → 0
    - Joined / left mid-month → calendar-day proration
    - Employed entire month → 1
    """
    month_start, month_end, days_in_month = _month_bounds(as_of)
    leaving = getattr(user, "leaving_date", None)
    joining = getattr(user, "joining_date", None)

    if leaving is not None and leaving < month_start:
        return Decimal("0")

    start = month_start
    if joining is not None and joining > month_start:
        start = joining
    end = month_end
    if leaving is not None and leaving < month_end:
        end = leaving
    if end < start:
        return Decimal("0")

    employed_days = (end - start).days + 1
    if employed_days >= days_in_month:
        return Decimal("1")
    return (Decimal(employed_days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))


def user_counts_for_headcount(user: User, *, as_of: date) -> bool:
    """True if the person still counts as billable/overhead FTE on ``as_of``."""
    leaving = getattr(user, "leaving_date", None)
    if leaving is not None and leaving < as_of:
        return False
    joining = getattr(user, "joining_date", None)
    if joining is not None and joining > as_of:
        return False
    return True


def expense_counts_for_as_of(expense: Expense, *, as_of: date) -> bool:
    """Active expense contributes to monthly OpEx on ``as_of`` if not ended."""
    if not getattr(expense, "is_active", True):
        return False
    end = getattr(expense, "end_date", None)
    if end is not None and end < as_of:
        return False
    start = getattr(expense, "start_date", None) or getattr(expense, "purchase_date", None)
    if start is not None and start > as_of:
        return False
    return True


def expense_month_factor(expense: Expense, *, as_of: date) -> Decimal:
    """Prorate recurring/ended expenses within the as_of month; else 0 or 1."""
    if not expense_counts_for_as_of(expense, as_of=as_of):
        return Decimal("0")
    month_start, month_end, days_in_month = _month_bounds(as_of)
    end = getattr(expense, "end_date", None)
    if end is None or end >= month_end:
        return Decimal("1")
    if end < month_start:
        return Decimal("0")
    days = (end - month_start).days + 1
    return (Decimal(days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))
