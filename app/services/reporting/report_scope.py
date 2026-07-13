"""Resolve customer/team scope for engineering report filters."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.team_access import get_accessible_team_ids
from app.models.models import TeamMember, User
from app.services.user_team_service import get_user_team_ids


@dataclass(frozen=True)
class ReportScope:
    """None team/user sets mean unrestricted (org-wide). Empty set means deny-all."""

    customer_id: UUID | None = None
    team_ids: frozenset[UUID] | None = None
    user_ids: frozenset[UUID] | None = None


class ReportScopeForbidden(Exception):
    """Requested team is outside the caller's accessible teams."""


def resolve_report_scope(
    db: Session,
    user: User,
    *,
    customer_id: UUID | None = None,
    team_id: UUID | None = None,
) -> ReportScope:
    accessible = get_accessible_team_ids(db, user)

    if accessible is not None:
        if team_id is not None and team_id not in accessible:
            raise ReportScopeForbidden("Team is outside your accessible scope")
        team_ids: frozenset[UUID] | None = frozenset({team_id}) if team_id else frozenset(accessible)
    else:
        team_ids = frozenset({team_id}) if team_id is not None else None

    user_ids: frozenset[UUID] | None = None
    if team_ids is not None:
        user_ids = frozenset(_users_on_teams(db, team_ids))

    return ReportScope(
        customer_id=customer_id,
        team_ids=team_ids,
        user_ids=user_ids,
    )


def _users_on_teams(db: Session, team_ids: frozenset[UUID]) -> set[UUID]:
    if not team_ids:
        return set()
    member_ids = set(
        db.scalars(
            select(TeamMember.user_id).where(TeamMember.team_id.in_(tuple(team_ids)))
        ).all()
    )
    primary_ids = set(
        db.scalars(select(User.id).where(User.team_id.in_(tuple(team_ids)))).all()
    )
    return member_ids | primary_ids


def user_matches_scope(db: Session, user: User, scope: ReportScope) -> bool:
    if scope.user_ids is None:
        return True
    if user.id in scope.user_ids:
        return True
    # Fallback: primary team or membership may lag user_ids snapshot
    if scope.team_ids is None:
        return True
    return bool(get_user_team_ids(db, user.id) & set(scope.team_ids))
