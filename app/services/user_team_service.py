"""User ↔ team assignment helpers (team_members junction table)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class UserTeamAssignmentInput:
    team_id: UUID
    relationship_type: TeamRelationshipType = TeamRelationshipType.member
    is_primary: bool = False
    include_in_timesheet_reports: bool = True


def get_user_team_ids(db: Session, user_id: UUID) -> set[UUID]:
    member_ids = set(
        db.scalars(select(TeamMember.team_id).where(TeamMember.user_id == user_id)).all()
    )
    user = db.get(User, user_id)
    if user is not None and user.team_id is not None:
        member_ids.add(user.team_id)
    return member_ids


def list_user_team_assignments(db: Session, user_id: UUID) -> list[TeamMember]:
    return list(
        db.scalars(
            select(TeamMember)
            .where(TeamMember.user_id == user_id)
            .order_by(TeamMember.is_primary.desc(), TeamMember.joined_at)
        ).all()
    )


def _validate_assignments(
    db: Session,
    assignments: list[UserTeamAssignmentInput],
) -> list[UserTeamAssignmentInput]:
    if not assignments:
        return []
    primary_count = sum(1 for row in assignments if row.is_primary)
    if primary_count > 1:
        raise ProTrackValidationError("At most one team may be marked as primary")
    seen: set[UUID] = set()
    normalized: list[UserTeamAssignmentInput] = []
    for row in assignments:
        if row.team_id in seen:
            raise ProTrackValidationError("Duplicate team assignment is not allowed")
        seen.add(row.team_id)
        team = db.get(Team, row.team_id)
        if team is None or not team.is_active:
            raise ProTrackValidationError("Each team assignment must reference an active team")
        normalized.append(row)
    return normalized


def sync_user_team_assignments(
    db: Session,
    user_id: UUID,
    *,
    assignments: list[UserTeamAssignmentInput] | None = None,
    legacy_team_id: UUID | None = None,
) -> None:
    """Replace all team memberships for a user and sync User.team_id to the primary team."""
    user = db.get(User, user_id)
    if user is None:
        raise ProTrackValidationError("User not found")

    resolved: list[UserTeamAssignmentInput]
    if assignments is not None:
        resolved = _validate_assignments(db, assignments)
    elif legacy_team_id is not None:
        team = db.get(Team, legacy_team_id)
        if team is None or not team.is_active:
            raise ProTrackValidationError("team_id must reference an active team")
        resolved = [
            UserTeamAssignmentInput(
                team_id=legacy_team_id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            )
        ]
    else:
        resolved = []

    db.execute(delete(TeamMember).where(TeamMember.user_id == user_id))
    primary_team_id: UUID | None = None
    for row in resolved:
        if row.is_primary:
            primary_team_id = row.team_id
        db.add(
            TeamMember(
                team_id=row.team_id,
                user_id=user_id,
                relationship_type=row.relationship_type,
                is_primary=row.is_primary,
                include_in_timesheet_reports=row.include_in_timesheet_reports,
                role_within_team=row.relationship_type.value.replace("_", " ").title(),
                joined_at=_utcnow(),
            )
        )
    user.team_id = primary_team_id
    db.add(user)
    db.flush()


def sync_user_team_membership(
    db: Session,
    user_id: UUID,
    team_id: UUID | None,
) -> None:
    """Backward-compatible single-team assignment."""
    if team_id is None:
        sync_user_team_assignments(db, user_id, assignments=[])
        return
    sync_user_team_assignments(
        db,
        user_id,
        assignments=[
            UserTeamAssignmentInput(
                team_id=team_id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            )
        ],
    )
