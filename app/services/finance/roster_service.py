"""Employee cost roster helpers for Financial Planning (team-scoped)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.salary_eligibility import user_requires_salary
from app.models.finance import EmployeeCostProfile
from app.models.models import TeamMember, User


def _user_matches_team(db: Session, user: User, team_id: UUID) -> bool:
    from datetime import date

    from app.services.finance.employment_cost import primary_team_salary_factor

    as_of = date.today()
    if primary_team_salary_factor(db, user_id=user.id, team_id=team_id, as_of=as_of) > 0:
        return True
    if user.team_id == team_id:
        return True
    memberships = user.team_memberships or []
    primary = next((m for m in memberships if m.is_primary and m.team_id == team_id), None)
    if primary is not None:
        return True
    if any(m.team_id == team_id for m in memberships):
        has_primary = any(m.is_primary for m in memberships)
        if has_primary:
            return any(m.is_primary and m.team_id == team_id for m in memberships)
        return True
    return False


def get_employee_cost_roster(
    db: Session,
    *,
    team_id: UUID | None = None,
    include_exempt: bool = False,
    include_inactive: bool = False,
) -> list[dict]:
    from datetime import date

    from app.services.finance.employment_cost import employment_salary_factor

    as_of = date.today()
    month_start = as_of.replace(day=1)
    users = db.scalars(
        select(User)
        .options(selectinload(User.team_memberships).selectinload(TeamMember.team))
        .order_by(User.last_name, User.first_name)
    ).all()
    profiles = {
        row.user_id: row
        for row in db.scalars(
            select(EmployeeCostProfile).where(EmployeeCostProfile.is_active.is_(True))
        ).all()
    }

    roster: list[dict] = []
    for user in users:
        leaving = getattr(user, "leaving_date", None)
        # Active, or left this month (still prorated in P&L).
        if not include_inactive and not user.is_active and (leaving is None or leaving < month_start):
            continue
        requires = user_requires_salary(user)
        if not include_exempt and not requires:
            continue
        if team_id is not None and not _user_matches_team(db, user, team_id):
            continue
        profile = profiles.get(user.id)
        team_names = sorted(
            {
                membership.team.name
                for membership in (user.team_memberships or [])
                if membership.team is not None and membership.team.is_active
            }
        )
        if getattr(user, "team", None) is not None and user.team.is_active:
            if user.team.name not in team_names:
                team_names.append(user.team.name)
                team_names.sort()
        factor = employment_salary_factor(user, as_of=as_of)
        roster.append(
            {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "is_active": bool(user.is_active),
                "team_names": team_names,
                "requires_salary": requires,
                "has_profile": profile is not None,
                "profile_id": profile.id if profile else None,
                "currency_code": profile.currency_code if profile else None,
                "monthly_salary": profile.monthly_salary if profile else None,
                "hourly_cost": profile.hourly_cost if profile else None,
                "base_monthly_salary_inr": profile.base_monthly_salary_inr if profile else None,
                "effective_from": profile.effective_from if profile else None,
                "notes": profile.notes if profile else None,
                "joining_date": getattr(user, "joining_date", None),
                "leaving_date": leaving,
                "salary_month_factor": str(factor),
            }
        )
    return roster
