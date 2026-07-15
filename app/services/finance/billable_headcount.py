"""Billable salary-required headcount for retainer commercial math."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.salary_eligibility import user_requires_salary
from app.models.models import Team, TeamMember, User
from app.services.finance.employment_cost import user_counts_for_headcount


def _billable_user_ids(db: Session, team_id: UUID) -> set[UUID]:
    members = db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)).all()
    billable_ids: set[UUID] = set()
    member_user_ids: set[UUID] = set()
    for member in members:
        member_user_ids.add(member.user_id)
        if bool(getattr(member, "is_billable_headcount", True)):
            billable_ids.add(member.user_id)

    legacy = db.scalars(
        select(User.id).where(User.team_id == team_id, User.is_active.is_(True))
    ).all()
    for user_id in legacy:
        if user_id not in member_user_ids:
            billable_ids.add(user_id)
    return billable_ids


def billable_salary_users(
    db: Session, team_id: UUID, *, as_of: date | None = None
) -> list[User]:
    ref = as_of or date.today()
    billable_ids = _billable_user_ids(db, team_id)
    if not billable_ids:
        return []
    users = db.scalars(
        select(User).where(User.id.in_(billable_ids), User.is_active.is_(True))
    ).all()
    return [
        user
        for user in users
        if user_requires_salary(user) and user_counts_for_headcount(user, as_of=ref)
    ]


def billable_salary_headcount(
    db: Session, team_id: UUID, *, as_of: date | None = None
) -> int:
    """Count active users on the team who require salary AND are billable headcount.

    Membership rows with ``is_billable_headcount=False`` (management/overhead on a
    delivery team, or Corporate/Management members) are excluded from retainer rate × N.
    Legacy ``User.team_id`` without a membership row counts as billable (compat).
    Users past ``leaving_date`` are excluded.
    """
    return len(billable_salary_users(db, team_id, as_of=as_of))


def company_delivery_billable_salary_users(
    db: Session, *, as_of: date | None = None
) -> list[User]:
    """Unique billable × salary-required users across delivery teams.

    Excludes Corporate / Management overhead homes.
    """
    from app.db.phase33_management_team_schema_sync import is_overhead_home_team

    seen: set[UUID] = set()
    users: list[User] = []
    teams = db.scalars(select(Team).where(Team.is_active.is_(True))).all()
    for team in teams:
        if is_overhead_home_team(team):
            continue
        for user in billable_salary_users(db, team.id, as_of=as_of):
            if user.id in seen:
                continue
            seen.add(user.id)
            users.append(user)
    return users


def company_delivery_billable_salary_headcount(
    db: Session, *, as_of: date | None = None
) -> int:
    return len(company_delivery_billable_salary_users(db, as_of=as_of))


def billable_salary_counts_by_skill(
    db: Session, team_id: UUID, *, as_of: date | None = None
) -> dict[str, int]:
    """Return skill_level -> count for billable salary-required users.

    Users with null skill are counted under empty string ``\"\"`` (default band).
    """
    counts: dict[str, int] = defaultdict(int)
    for user in billable_salary_users(db, team_id, as_of=as_of):
        skill = getattr(user, "skill_level", None)
        key = skill.value if skill is not None and hasattr(skill, "value") else (str(skill) if skill else "")
        counts[key] += 1
    return dict(counts)
