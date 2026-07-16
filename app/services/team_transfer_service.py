"""Dated team transfer — primary-home periods for finance proration."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.fixed_resource_eligibility import default_is_billable_headcount_for_user
from app.models.models import Team, TeamMember, TeamMembershipPeriod, User


def _close_open_primary_periods(
    db: Session,
    *,
    user_id: UUID,
    team_id: UUID,
    effective_to: date,
) -> None:
    rows = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.team_id == team_id,
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_to.is_(None),
        )
    ).all()
    for row in rows:
        if row.effective_from > effective_to:
            row.effective_to = row.effective_from
        else:
            row.effective_to = effective_to


def _close_all_open_primary_periods_for_user(
    db: Session, *, user_id: UUID, effective_to: date
) -> None:
    rows = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_to.is_(None),
        )
    ).all()
    for row in rows:
        if row.effective_from > effective_to:
            row.effective_to = row.effective_from
        else:
            row.effective_to = effective_to


def transfer_primary_membership(
    db: Session,
    *,
    user: User,
    source_team_id: UUID,
    target_team_id: UUID,
    effective_from: date,
    member: TeamMember,
) -> TeamMember:
    """Move primary home from source → target with finance-effective dating."""
    if source_team_id == target_team_id:
        raise ProTrackValidationError("Target team must differ from source team")
    target_team = db.get(Team, target_team_id)
    if target_team is None or not target_team.is_active:
        raise ProTrackValidationError("Target team not found or inactive")

    last_on_source = effective_from - timedelta(days=1)
    if last_on_source < date(2000, 1, 1):
        raise ProTrackValidationError("effective_from is too far in the past")

    _close_open_primary_periods(
        db,
        user_id=user.id,
        team_id=source_team_id,
        effective_to=last_on_source,
    )

    target_member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == target_team_id,
            TeamMember.user_id == user.id,
        )
    )
    billable = bool(getattr(member, "is_billable_headcount", True))
    if target_member is None:
        target_member = TeamMember(
            team_id=target_team_id,
            user_id=user.id,
            role_within_team=member.role_within_team,
            relationship_type=member.relationship_type,
            is_primary=False,
            is_billable_headcount=billable,
            effective_from=effective_from,
        )
        db.add(target_member)
        db.flush()
    else:
        target_member.is_billable_headcount = billable
        target_member.effective_from = effective_from

    db.add(
        TeamMembershipPeriod(
            user_id=user.id,
            team_id=target_team_id,
            is_primary=True,
            is_billable_headcount=billable,
            effective_from=effective_from,
            effective_to=None,
            role_within_team=member.role_within_team,
            relationship_type=member.relationship_type,
            notes=f"Transfer from team {source_team_id}",
        )
    )

    today = date.today()
    if effective_from <= today:
        for m in db.scalars(
            select(TeamMember).where(TeamMember.user_id == user.id)
        ).all():
            m.is_primary = m.id == target_member.id
        member.is_primary = False
        target_member.is_primary = True
        user.team_id = target_team_id
    else:
        member.is_primary = True
        target_member.is_primary = False

    db.add(user)
    db.add(member)
    db.add(target_member)
    db.flush()
    return target_member
