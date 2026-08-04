"""Team-scoped timesheet overview for leaders and managers."""

from __future__ import annotations

import calendar
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.fixed_resource_eligibility import role_is_management_overhead_default
from app.core.permissions import (
    DESIGN_LEADER,
    ENGINEERING_MANAGER,
    TIMESHEET_COMPLIANCE_VIEWER_ROLES,
    get_role_name,
    is_admin,
    normalize_role_name,
)
from app.core.timesheet_eligibility import user_requires_timesheet
from app.db.phase33_management_team_schema_sync import is_overhead_home_team
from app.models.enums import TeamRelationshipType
from app.models.models import Project, Team, TeamMember, User
from app.services.reporting.team_membership_windows import membership_windows_for_teams
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


def get_timesheet_visible_user_ids(
    db: Session,
    actor: User,
    *,
    range_start: date | None = None,
    range_end: date | None = None,
) -> set[UUID] | None:
    """User IDs whose timesheet entries the actor may view in overview mode.

    All-teams / compliance scopes are limited to users with Requires timesheet
    so managers and monitor-only accounts are not listed.

    When a month range is provided, dated membership windows are included so
    people who transferred mid-month remain visible on teams they belonged to.
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

    if range_start is not None and range_end is not None and team_scope:
        from app.services.reporting.team_membership_windows import users_on_teams_during

        visible.update(
            users_on_teams_during(
                db, team_scope, range_start=range_start, range_end=range_end
            )
            & required
        )

    if role_name == DESIGN_LEADER:
        visible.update(_design_leader_project_user_ids(db, actor) & required)
        if actor.id in required:
            visible.add(actor.id)

    return visible


def month_bounds_from_value(month: str | None = None) -> tuple[date, date]:
    """Return inclusive (month_start, month_end) for YYYY-MM, or the current month."""
    if month:
        year, month_num = map(int, month.split("-"))
    else:
        today = date.today()
        year, month_num = today.year, today.month
    start = date(year, month_num, 1)
    end = date(year, month_num, calendar.monthrange(year, month_num)[1])
    return start, end


def resolve_overview_bounds(
    *,
    month: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[date, date]:
    """Resolve inclusive overview window from explicit dates or a YYYY-MM month."""
    if period_start is not None and period_end is not None:
        if period_end < period_start:
            raise ValueError("period_end must be on or after period_start")
        return period_start, period_end
    if period_start is not None:
        return period_start, period_start
    if period_end is not None:
        return period_end, period_end
    return month_bounds_from_value(month)


def _serialize_membership_windows(
    windows: dict[UUID, list[tuple[date, date]]],
    user_ids: list[UUID],
) -> dict[str, list[dict[str, date]]]:
    allowed = set(user_ids)
    serialized: dict[str, list[dict[str, date]]] = {}
    for user_id, intervals in windows.items():
        if user_id not in allowed:
            continue
        serialized[str(user_id)] = [
            {"start": start, "end": end} for start, end in intervals
        ]
    return serialized


def _is_management_timesheet_user(
    db: Session,
    user: User,
    *,
    teams_by_id: dict[UUID, Team],
) -> bool:
    """Leaders / Corporate home — hours must not be split across delivery teams."""
    home = teams_by_id.get(user.team_id) if user.team_id else None
    if is_overhead_home_team(home):
        return True
    role_name = get_role_name(db, user)
    return role_is_management_overhead_default(role_name)


def build_timesheet_overview(
    db: Session,
    actor: User,
    *,
    month: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """Return team groupings and user metadata for the timesheet overview UI.

    Only users with Requires timesheet appear in team sections — managers,
    Office Admin, Planning Board, System Admin, and other monitor-only accounts
    are omitted so completion chasing stays focused.

    Team sections use dated membership windows for the overview range so line
    items (and roster) only cover days the person belonged to that team.
    """
    month_start, month_end = resolve_overview_bounds(
        month=month,
        period_start=period_start,
        period_end=period_end,
    )
    team_scope = get_timesheet_leader_team_ids(db, actor)
    visible_user_ids = get_timesheet_visible_user_ids(
        db, actor, range_start=month_start, range_end=month_end
    )

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

    teams_by_id = {team.id: team for team in teams}
    # Need overhead-home classification even when the corporate team is out of scope.
    for user in users:
        if user.team_id and user.team_id not in teams_by_id:
            home = db.get(Team, user.team_id)
            if home is not None:
                teams_by_id[home.id] = home

    management_ids = sorted(
        user.id
        for user in users
        if _is_management_timesheet_user(db, user, teams_by_id=teams_by_id)
    )
    management_id_set = set(management_ids)

    team_name_by_id = {team.id: team.name for team in teams_by_id.values()}
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

    # Leaders / Corporate home: full period hours in one place — never split across
    # delivery teams they also manage or hold secondary membership on.
    if management_ids:
        assigned_user_ids.update(management_ids)
        overview_teams.append(
            {
                "team_id": None,
                "team_name": "Management / Leadership",
                "user_ids": management_ids,
                "membership_windows": {},
                "section_kind": "management",
            }
        )

    for team in teams:
        if is_overhead_home_team(team):
            # Corporate roster is covered by the Management / Leadership section.
            continue
        windows = membership_windows_for_teams(
            db,
            frozenset({team.id}),
            range_start=month_start,
            range_end=month_end,
            # Hour attribution must follow primary home only — secondary
            # multi-team memberships previously duplicated the same hours
            # under every team section.
            primary_only=True,
        )
        member_ids = sorted(
            user_id
            for user_id in windows
            if user_id in required_ids
            and user_id not in management_id_set
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
                "membership_windows": _serialize_membership_windows(windows, member_ids),
                "section_kind": "delivery",
            }
        )

    unassigned_users = [user.id for user in users if user.id not in assigned_user_ids]
    if unassigned_users:
        overview_teams.append(
            {
                "team_id": None,
                "team_name": "Unassigned",
                "user_ids": unassigned_users,
                "membership_windows": {},
                "section_kind": "unassigned",
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
        "month_start": month_start,
        "month_end": month_end,
    }
