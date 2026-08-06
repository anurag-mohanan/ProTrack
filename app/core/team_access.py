"""Team visibility and scoping for multi-team users.

Ops rule (client confidentiality):
- Admin / unscoped Engineering Manager: org-wide.
- Everyone else: projects on accessible teams OR personally assigned
  (cross-utilization), never other teams' unassigned client work.

Prefer ``app.core.data_scope.resolve_data_scope`` for new call sites — it is the
Layer-2 authorization facade. This module remains the SQL/team resolution engine
used underneath that facade.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session

from app.core.access_control import EXECUTIVE_ROLES
from app.core.permissions import (
    ENGINEERING_MANAGER,
    PLANNING_BOARD,
    get_role_name,
    is_admin,
    is_assigned_to_project,
    project_assignment_filter,
)
from app.models.enums import TeamRelationshipType
from app.models.models import Project, Team, TeamMember, User
from app.services.user_team_service import get_user_team_ids


def get_accessible_team_ids(db: Session, user: User) -> set[UUID] | None:
    """Return assigned/led team IDs, or None when the user can access all teams."""
    role_name = get_role_name(db, user)
    assigned = set(get_user_team_ids(db, user.id))
    assigned.update(
        db.scalars(
            select(Team.id).where(
                Team.team_lead_id == user.id,
                Team.is_active.is_(True),
            )
        ).all()
    )
    assigned.update(
        db.scalars(
            select(TeamMember.team_id).where(
                TeamMember.user_id == user.id,
                TeamMember.relationship_type.in_(
                    (
                        TeamRelationshipType.team_leader,
                        TeamRelationshipType.engineering_manager,
                    )
                ),
            )
        ).all()
    )
    if is_admin(db, user):
        return None
    if role_name == PLANNING_BOARD:
        return None
    # Executive tier (MD / Directors) sees the whole company.
    if role_name in EXECUTIVE_ROLES:
        return None
    if role_name == ENGINEERING_MANAGER and not assigned:
        return None
    return assigned


def get_led_team_ids(db: Session, user: User) -> set[UUID]:
    """Teams where the user is team lead or has a leadership membership row."""
    led = set(
        db.scalars(
            select(Team.id).where(
                Team.team_lead_id == user.id,
                Team.is_active.is_(True),
            )
        ).all()
    )
    led.update(
        db.scalars(
            select(TeamMember.team_id).where(
                TeamMember.user_id == user.id,
                TeamMember.relationship_type.in_(
                    (
                        TeamRelationshipType.team_leader,
                        TeamRelationshipType.engineering_manager,
                    )
                ),
            )
        ).all()
    )
    return led


def get_organization_chart_team_ids(db: Session, user: User) -> set[UUID] | None:
    """Teams visible on the organization chart.

    Returns:
      None — full org chart (Admin, or unscoped Engineering Manager)
      set — division / led teams only (empty = no columns for this viewer)
    """
    if is_admin(db, user):
        return None

    role_name = get_role_name(db, user)
    # Executive tier (MD / Directors) sees the full organization chart.
    if role_name in EXECUTIVE_ROLES:
        return None
    if role_name == ENGINEERING_MANAGER:
        # Division portfolio (membership ∪ leadership). Unscoped EM → org-wide.
        return get_accessible_team_ids(db, user)

    # Team leaders only see teams they manage — not mere membership.
    return get_led_team_ids(db, user)


def user_can_view_organization_chart(db: Session, user: User) -> bool:
    """Admin, executive tier (MD / Directors), EM, or a team leader."""
    from app.core.permissions import DESIGN_LEADER

    if is_admin(db, user):
        return True
    role_name = get_role_name(db, user)
    # The MD heads the chart and Directors head their departments.
    if role_name in EXECUTIVE_ROLES:
        return True
    if role_name == ENGINEERING_MANAGER:
        return True
    if role_name == DESIGN_LEADER and get_led_team_ids(db, user):
        return True
    # Non-DL users who are still designated team leads
    if get_led_team_ids(db, user):
        return True
    return False


def resolve_team_scope(
    db: Session,
    user: User,
    *,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = None,
) -> set[UUID] | None:
    """Resolve requested team filters against the user's accessible teams.

    Returns:
      None — org-wide (no team restriction)
      set  — allowed team IDs (may be empty = deny-all for team portfolio)
    """
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

    return requested & accessible


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
        return (false(),)
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


def project_visibility_clause(db: Session, user: User):
    """SQLAlchemy clause for projects the user may see, or None for org-wide."""
    accessible = get_accessible_team_ids(db, user)
    if accessible is None:
        return None

    role_name = get_role_name(db, user)
    assignment = project_assignment_filter(user, role_name)
    # Staff and leaders always keep personally assigned / DL-owned work (cross-util).
    personal = or_(
        Project.design_leader_id == user.id,
        Project.designer_id == user.id,
        Project.surfacer_id == user.id,
    )
    if assignment is not None:
        personal = or_(personal, assignment)

    if not accessible:
        return personal

    team_parts = team_project_clause(db, list(accessible))
    return or_(personal, *team_parts)


def can_access_project_by_team(db: Session, user: User, project: Project) -> bool:
    """True when project is on an accessible team (including inherited null team_id)."""
    accessible = get_accessible_team_ids(db, user)
    if accessible is None:
        return True
    if not accessible:
        return False
    if project.team_id is not None:
        return project.team_id in accessible
    if project.team_id is None:
        assignee_ids = {
            uid
            for uid in (
                project.designer_id,
                project.design_leader_id,
                project.surfacer_id,
            )
            if uid is not None
        }
        if not assignee_ids:
            return False
        team_users = team_member_user_ids(db, list(accessible))
        return bool(assignee_ids & team_users)
    return False


def user_can_read_scoped_project(db: Session, user: User, project: Project) -> bool:
    """Team portfolio OR personal assignment. Org-wide users always True (non-deleted)."""
    accessible = get_accessible_team_ids(db, user)
    if accessible is None:
        return True
    if is_assigned_to_project(project, user.id):
        return True
    return can_access_project_by_team(db, user, project)
