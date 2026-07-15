"""Employee cost roster helpers for Financial Planning."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import EmployeeCostProfile
from app.models.models import TeamMember, User


def get_employee_cost_roster(db: Session) -> list[dict]:
    users = db.scalars(
        select(User)
        .where(User.is_active.is_(True))
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
        roster.append(
            {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "team_names": team_names,
                "has_profile": profile is not None,
                "profile_id": profile.id if profile else None,
                "currency_code": profile.currency_code if profile else None,
                "monthly_salary": profile.monthly_salary if profile else None,
                "hourly_cost": profile.hourly_cost if profile else None,
                "base_monthly_salary_inr": profile.base_monthly_salary_inr if profile else None,
                "effective_from": profile.effective_from if profile else None,
                "notes": profile.notes if profile else None,
            }
        )
    return roster
