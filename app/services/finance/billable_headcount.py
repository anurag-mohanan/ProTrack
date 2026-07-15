"""Billable salary-required headcount for retainer commercial math."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.salary_eligibility import user_requires_salary
from app.models.models import TeamMember, User


def billable_salary_headcount(db: Session, team_id: UUID) -> int:
    """Count active users on the team who require salary AND are billable headcount.

    Membership rows with ``is_billable_headcount=False`` (management/overhead on a
    delivery team, or Corporate members) are excluded from retainer rate × N.
    Legacy ``User.team_id`` without a membership row counts as billable (compat).
    """
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

    if not billable_ids:
        return 0
    users = db.scalars(
        select(User).where(User.id.in_(billable_ids), User.is_active.is_(True))
    ).all()
    return sum(1 for user in users if user_requires_salary(user))
