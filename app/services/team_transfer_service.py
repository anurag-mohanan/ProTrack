"""Dated team transfer — primary-home periods for finance proration."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.fixed_resource_eligibility import default_is_billable_headcount_for_user
from app.models.enums import TeamRelationshipType
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


def _maybe_update_reporting_manager(
    db: Session,
    *,
    user: User,
    target_team: Team,
    update_reporting_manager: bool,
) -> None:
    """Align reporting manager with the target team lead when requested."""
    if not update_reporting_manager:
        return
    lead_id = target_team.team_lead_id
    if lead_id is None or lead_id == user.id:
        return
    user.manager_id = lead_id
    db.add(user)


def assign_primary_membership(
    db: Session,
    *,
    user: User,
    target_team_id: UUID,
    effective_from: date,
    update_reporting_manager: bool = True,
) -> TeamMember:
    """Place an unassigned (or non-primary) user onto a primary team home with dating."""
    target_team = db.get(Team, target_team_id)
    if target_team is None or not target_team.is_active:
        raise ProTrackValidationError("Target team not found or inactive")

    existing_primary = db.scalar(
        select(TeamMember).where(
            TeamMember.user_id == user.id,
            TeamMember.is_primary.is_(True),
        )
    )
    if existing_primary is not None:
        raise ProTrackValidationError(
            "User already has a primary team. Use transfer instead of assign."
        )

    last_day_before = effective_from - timedelta(days=1)
    if last_day_before < date(2000, 1, 1):
        raise ProTrackValidationError("effective_from is too far in the past")

    _close_all_open_primary_periods_for_user(
        db, user_id=user.id, effective_to=last_day_before
    )

    billable = default_is_billable_headcount_for_user(db, team=target_team, user=user)
    target_member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == target_team_id,
            TeamMember.user_id == user.id,
        )
    )
    if target_member is None:
        target_member = TeamMember(
            team_id=target_team_id,
            user_id=user.id,
            role_within_team="Member",
            relationship_type=TeamRelationshipType.member,
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
            role_within_team=target_member.role_within_team,
            relationship_type=target_member.relationship_type,
            notes="Primary assign from organization chart",
        )
    )

    today = date.today()
    if effective_from <= today:
        for m in db.scalars(
            select(TeamMember).where(TeamMember.user_id == user.id)
        ).all():
            m.is_primary = m.id == target_member.id
        target_member.is_primary = True
        user.team_id = target_team_id
    else:
        target_member.is_primary = False

    _maybe_update_reporting_manager(
        db,
        user=user,
        target_team=target_team,
        update_reporting_manager=update_reporting_manager,
    )
    db.add(user)
    db.add(target_member)
    db.flush()
    return target_member


def transfer_primary_membership(
    db: Session,
    *,
    user: User,
    source_team_id: UUID,
    target_team_id: UUID,
    effective_from: date,
    member: TeamMember,
    update_reporting_manager: bool = True,
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

    _maybe_update_reporting_manager(
        db,
        user=user,
        target_team=target_team,
        update_reporting_manager=update_reporting_manager,
    )
    db.add(user)
    db.add(member)
    db.add(target_member)
    db.flush()
    return target_member
