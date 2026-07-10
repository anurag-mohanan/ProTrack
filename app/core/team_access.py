"""Team visibility and scoping for multi-team users."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import ENGINEERING_MANAGER, FULL_ACCESS_ROLES, get_role_name, is_admin
from app.models.models import Project, TeamMember, User
from app.services.user_team_service import get_user_team_ids


def get_accessible_team_ids(db: Session, user: User) -> set[UUID] | None:
    """Return assigned team IDs, or None when the user can access all teams."""
    role_name = get_role_name(db, user)
    assigned = get_user_team_ids(db, user.id)
    if is_admin(db, user):
        return None
    if role_name == ENGINEERING_MANAGER and not assigned:
        return None
    return assigned


def resolve_team_scope(
    db: Session,
    user: User,
    *,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = None,
) -> set[UUID] | None:
    """Resolve requested team filters against the user's accessible teams."""
    accessible = get_accessible_team_ids(db, user)
    requested: set[UUID] | None = None
    if team_ids:
        requested = set(team_ids)
    elif team_id is not None:
        requested = {team_id}

    if accessible is None:
        return requested

    if requested is None:
        return accessible

    scoped = requested & accessible
    return scoped


def team_member_user_ids(db: Session, team_ids: list[UUID]) -> set[UUID]:
    """User IDs linked to the given teams via team_members or legacy User.team_id."""
    if not team_ids:
        return set()
    member_ids = set(
        db.scalars(
            select(TeamMember.user_id).where(TeamMember.team_id.in_(team_ids))
        ).all()
    )
    legacy_ids = set(
        db.scalars(
            select(User.id).where(
                User.team_id.in_(team_ids),
                User.is_active.is_(True),
            )
        ).all()
    )
    return member_ids | legacy_ids


def team_project_clause(db: Session, team_ids: list[UUID] | None) -> tuple:
    """Match projects on team_id or assignee membership when team_id is unset."""
    if not team_ids:
        return ()
    direct = Project.team_id.in_(team_ids)
    assignee_ids = team_member_user_ids(db, team_ids)
    if not assignee_ids:
        return (direct,)
    inherited = and_(
        Project.team_id.is_(None),
        or_(
            Project.designer_id.in_(assignee_ids),
            Project.design_leader_id.in_(assignee_ids),
            Project.surfacer_id.in_(assignee_ids),
        ),
    )
    return (or_(direct, inherited),)
