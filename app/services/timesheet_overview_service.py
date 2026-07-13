"""Team-scoped timesheet overview for leaders and managers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import (
    DESIGN_LEADER,
    ENGINEERING_MANAGER,
    TIMESHEET_COMPLIANCE_VIEWER_ROLES,
    get_role_name,
    is_admin,
    normalize_role_name,
)
from app.core.timesheet_eligibility import user_requires_timesheet
from app.models.enums import TeamRelationshipType
from app.models.models import Project, Team, TeamMember, User
from app.services.user_team_service import get_user_team_ids


def get_timesheet_leader_team_ids(db: Session, user: User) -> set[UUID] | None:
    """Teams a leader/manager may oversee. None means all teams (admin / compliance / unscoped EM)."""
    if is_admin(db, user):
        return None

    role_name = normalize_role_name(get_role_name(db, user))
    if role_name in TIMESHEET_COMPLIANCE_VIEWER_ROLES:
        # Office Administrator / HR chase completion across every team.
        return None

    team_ids: set[UUID] = set(get_user_team_ids(db, user.id))

    team_ids.update(
        db.scalars(
            select(Team.id).where(
                Team.team_lead_id == user.id,
                Team.is_active.is_(True),
            )
        ).all()
    )

    team_ids.update(
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

    if role_name == ENGINEERING_MANAGER and not team_ids:
        return None

    return team_ids


def _users_for_team(db: Session, team_id: UUID) -> set[UUID]:
    member_ids = set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )
    member_ids.update(
        db.scalars(
            select(User.id).where(
                User.team_id == team_id,
                User.is_active.is_(True),
                User.is_archived.is_(False),
                User.is_deleted.is_(False),
            )
        ).all()
    )
    return member_ids


def _design_leader_project_user_ids(db: Session, user: User) -> set[UUID]:
    rows = db.execute(
        select(Project.designer_id, Project.surfacer_id, Project.design_leader_id).where(
            Project.design_leader_id == user.id,
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
        )
    ).all()
    user_ids: set[UUID] = {user.id}
    for designer_id, surfacer_id, design_leader_id in rows:
        if designer_id is not None:
            user_ids.add(designer_id)
        if surfacer_id is not None:
            user_ids.add(surfacer_id)
        if design_leader_id is not None:
            user_ids.add(design_leader_id)
    return user_ids


def _required_timesheet_user_ids(db: Session) -> set[UUID]:
    """Active users flagged Requires timesheet (completion-chase population)."""
    return set(
        db.scalars(
            select(User.id).where(
                User.requires_timesheet.is_(True),
                User.is_active.is_(True),
                User.is_archived.is_(False),
                User.is_deleted.is_(False),
            )
        ).all()
    )


def get_timesheet_visible_user_ids(db: Session, actor: User) -> set[UUID] | None:
    """User IDs whose timesheet entries the actor may view in overview mode.

    All-teams / compliance scopes are limited to users with Requires timesheet
    so managers and monitor-only accounts are not listed.
    """
    if is_admin(db, actor):
        return _required_timesheet_user_ids(db)

    role_name = normalize_role_name(get_role_name(db, actor))
    if role_name in TIMESHEET_COMPLIANCE_VIEWER_ROLES:
        return _required_timesheet_user_ids(db)

    team_scope = get_timesheet_leader_team_ids(db, actor)
    if team_scope is None:
        return _required_timesheet_user_ids(db)

    required = _required_timesheet_user_ids(db)
    visible: set[UUID] = set()
    for team_id in team_scope:
        visible.update(_users_for_team(db, team_id) & required)

    if role_name == DESIGN_LEADER:
        visible.update(_design_leader_project_user_ids(db, actor) & required)
        if actor.id in required:
            visible.add(actor.id)

    return visible


def build_timesheet_overview(db: Session, actor: User) -> dict:
    """Return team groupings and user metadata for the timesheet overview UI.

    Only users with Requires timesheet appear in team sections — managers,
    Office Admin, Planning Board, System Admin, and other monitor-only accounts
    are omitted so completion chasing stays focused.
    """
    team_scope = get_timesheet_leader_team_ids(db, actor)
    visible_user_ids = get_timesheet_visible_user_ids(db, actor)

    team_query = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    if team_scope is not None:
        if not team_scope:
            teams: list[Team] = []
        else:
            team_query = team_query.where(Team.id.in_(team_scope))
            teams = list(db.scalars(team_query).all())
    else:
        teams = list(db.scalars(team_query).all())

    user_query = select(User).where(
        User.is_active.is_(True),
        User.is_archived.is_(False),
        User.is_deleted.is_(False),
        User.requires_timesheet.is_(True),
    )
    if visible_user_ids is not None:
        if not visible_user_ids:
            users = []
        else:
            user_query = user_query.where(User.id.in_(visible_user_ids))
            users = list(db.scalars(user_query.order_by(User.last_name, User.first_name)).all())
    else:
        users = list(db.scalars(user_query.order_by(User.last_name, User.first_name)).all())

    users = [user for user in users if user_requires_timesheet(user)]
    required_ids = {user.id for user in users}

    team_name_by_id = {team.id: team.name for team in teams}
    user_team_ids: dict[UUID, set[UUID]] = {user.id: set() for user in users}
    for user in users:
        if user.team_id is not None:
            user_team_ids[user.id].add(user.team_id)
    if users:
        for row in db.scalars(
            select(TeamMember).where(TeamMember.user_id.in_([user.id for user in users]))
        ).all():
            user_team_ids[row.user_id].add(row.team_id)

    overview_teams = []
    assigned_user_ids: set[UUID] = set()
    for team in teams:
        member_ids = sorted(
            user_id
            for user_id in _users_for_team(db, team.id)
            if user_id in required_ids
            and (visible_user_ids is None or user_id in visible_user_ids)
        )
        if not member_ids:
            continue
        assigned_user_ids.update(member_ids)
        overview_teams.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "user_ids": member_ids,
            }
        )

    unassigned_users = [user.id for user in users if user.id not in assigned_user_ids]
    if unassigned_users:
        overview_teams.append(
            {
                "team_id": None,
                "team_name": "Unassigned",
                "user_ids": unassigned_users,
            }
        )

    overview_users = []
    for user in users:
        primary_team_name = team_name_by_id.get(user.team_id) if user.team_id else None
        overview_users.append(
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "team_id": user.team_id,
                "team_name": primary_team_name,
                "team_ids": sorted(user_team_ids.get(user.id, set()), key=str),
                "working_hours_per_day": float(user.working_hours_per_day or 8),
                "requires_timesheet": True,
            }
        )

    return {
        "teams": overview_teams,
        "users": overview_users,
        "scope_all_teams": team_scope is None,
    }
