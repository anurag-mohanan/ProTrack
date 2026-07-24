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
    """Fraction of the as_of calendar month this expense is recognized.

    Intersects the expense activity window with the month — independent of whether
    ``as_of`` is after ``end_date`` (mirrors salary leave-month proration).
    Mid-month start and end both prorate.
    """
    if not getattr(expense, "is_active", True):
        return Decimal("0")
    month_start, month_end, days_in_month = _month_bounds(as_of)
    start = getattr(expense, "start_date", None) or getattr(expense, "purchase_date", None)
    end = getattr(expense, "end_date", None)
    if start is None:
        return Decimal("1")
    window_end = end if end is not None else month_end
    days = _intersect_days(start, window_end, month_start, month_end)
    if days <= 0:
        return Decimal("0")
    if days >= days_in_month:
        return Decimal("1")
    return (Decimal(days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))


def _intersect_days(
    window_start: date, window_end: date, month_start: date, month_end: date
) -> int:
    start = max(window_start, month_start)
    end = min(window_end, month_end)
    if end < start:
        return 0
    return (end - start).days + 1


def primary_team_salary_factor(
    db,
    *,
    user_id,
    team_id,
    as_of: date,
) -> Decimal:
    """Fraction of monthly salary attributed to a team as primary home in the month of as_of."""
    from sqlalchemy import select

    from app.models.models import TeamMember, TeamMembershipPeriod, User

    month_start, month_end, days_in_month = _month_bounds(as_of)
    user = db.get(User, user_id)
    if user is None:
        return Decimal("0")

    employment_start = month_start
    if user.joining_date is not None and user.joining_date > employment_start:
        employment_start = user.joining_date
    employment_end = month_end
    leaving = getattr(user, "leaving_date", None)
    if leaving is not None and leaving < employment_end:
        employment_end = leaving
    if employment_end < employment_start:
        return Decimal("0")

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.team_id == team_id,
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_from <= month_end,
        )
    ).all()

    team_days = 0
    for period in periods:
        p_end = period.effective_to if period.effective_to is not None else month_end
        if p_end < month_start or period.effective_from > month_end:
            continue
        w_start = max(period.effective_from, employment_start)
        w_end = min(p_end, employment_end)
        team_days += _intersect_days(w_start, w_end, month_start, month_end)

    if team_days <= 0:
        member = db.scalar(
            select(TeamMember).where(
                TeamMember.user_id == user_id,
                TeamMember.team_id == team_id,
                TeamMember.is_primary.is_(True),
            )
        )
        if member is not None:
            m_start = getattr(member, "effective_from", None) or employment_start
            if m_start <= month_end:
                w_start = max(m_start, employment_start)
                team_days = _intersect_days(w_start, employment_end, month_start, month_end)

    if team_days <= 0:
        # Primary is optional: if the user has no primary home anywhere but works on
        # this team, attribute the employment window here ONLY when this membership is
        # the designated sole home (avoids charging full salary on every team).
        has_any_primary = db.scalar(
            select(TeamMember.id).where(
                TeamMember.user_id == user_id,
                TeamMember.is_primary.is_(True),
            ).limit(1)
        )
        if has_any_primary is None:
            sole = db.scalar(
                select(TeamMember)
                .where(TeamMember.user_id == user_id)
                .order_by(
                    TeamMember.effective_from.asc().nulls_first(),
                    TeamMember.team_id.asc(),
                )
                .limit(1)
            )
            if sole is not None and sole.team_id == team_id:
                m_start = getattr(sole, "effective_from", None) or employment_start
                if m_start <= month_end:
                    w_start = max(m_start, employment_start)
                    team_days = _intersect_days(
                        w_start, employment_end, month_start, month_end
                    )

    if team_days <= 0:
        return Decimal("0")
    if team_days >= days_in_month and employment_start <= month_start and employment_end >= month_end:
        return Decimal("1")
    factor = (Decimal(team_days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))
    if factor > Decimal("1"):
        return Decimal("1")
    return factor


def user_billable_on_team_at(
    db,
    *,
    user_id,
    team_id,
    as_of: date,
) -> bool:
    """True if user counts as billable on team at as_of (point-in-time)."""
    from sqlalchemy import select

    from app.models.models import TeamMember, TeamMembershipPeriod

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.team_id == team_id,
            TeamMembershipPeriod.effective_from <= as_of,
        )
    ).all()
    for period in periods:
        end = period.effective_to
        if end is not None and end < as_of:
            continue
        if period.effective_from <= as_of and bool(period.is_billable_headcount):
            return True

    member = db.scalar(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.team_id == team_id,
        )
    )
    if member is None:
        return False
    eff = getattr(member, "effective_from", None)
    if eff is not None and eff > as_of:
        return False
    return bool(getattr(member, "is_billable_headcount", True))
