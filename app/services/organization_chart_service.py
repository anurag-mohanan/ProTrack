"""Organization chart read model — primary-team cards for drag-and-drop moves."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import ENGINEERING_MANAGER, get_role_name, is_admin
from app.core.team_access import get_organization_chart_team_ids
from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember, User
from app.services.performance_review_service import format_tenure


class OrgChartPerson(BaseModel):
    user_id: UUID
    member_id: UUID | None = None
    source_team_id: UUID | None = None
    name: str
    email: str
    designation: str | None = None
    role_name: str | None = None
    relationship_type: str = TeamRelationshipType.member.value
    is_primary: bool = True
    can_move: bool = False
    is_billable_headcount: bool = True
    manager_id: UUID | None = None
    manager_name: str | None = None
    stream_name: str | None = None
    company_experience: str | None = None
    joining_date: date | None = None
    membership_effective_from: date | None = None


class OrgChartTeamColumn(BaseModel):
    team_id: UUID
    team_name: str
    colour: str
    team_lead_id: UUID | None = None
    team_lead_name: str | None = None
    member_count: int = 0
    people: list[OrgChartPerson] = Field(default_factory=list)


class OrganizationChartRead(BaseModel):
    teams: list[OrgChartTeamColumn] = Field(default_factory=list)
    unassigned: list[OrgChartPerson] = Field(default_factory=list)
    scope: str = "full"
    note: str = (
        "Drag a person card onto another team. Moves use dated primary-team transfers "
        "so salary is prorated for P&L by calendar days."
    )


def _person_from_user(
    user: User,
    *,
    member: TeamMember | None = None,
    allow_assign: bool = False,
    can_edit: bool = False,
) -> OrgChartPerson:
    manager_name = None
    if user.manager is not None:
        manager_name = f"{user.manager.first_name} {user.manager.last_name}".strip()
    role_name = user.role.name if user.role is not None else None
    stream_name = user.stream.name if user.stream is not None else None
    relationship_value = TeamRelationshipType.member.value
    if member is not None:
        relationship = member.relationship_type
        relationship_value = (
            relationship.value if hasattr(relationship, "value") else str(relationship)
        )
    movable = can_edit and (
        bool(member is not None and member.is_primary) or allow_assign
    )
    return OrgChartPerson(
        user_id=user.id,
        member_id=member.id if member is not None else None,
        source_team_id=member.team_id if member is not None else None,
        name=f"{user.first_name} {user.last_name}".strip(),
        email=user.email,
        designation=user.designation or role_name,
        role_name=role_name,
        relationship_type=relationship_value,
        is_primary=bool(member.is_primary) if member is not None else False,
        can_move=movable,
        is_billable_headcount=(
            bool(member.is_billable_headcount) if member is not None else False
        ),
        manager_id=user.manager_id,
        manager_name=manager_name,
        stream_name=stream_name,
        company_experience=format_tenure(user.joining_date),
        joining_date=user.joining_date,
        membership_effective_from=member.effective_from if member is not None else None,
    )


def build_organization_chart(db: Session, *, viewer: User) -> OrganizationChartRead:
    scope = get_organization_chart_team_ids(db, viewer)
    can_edit = is_admin(db, viewer)
    role_name = get_role_name(db, viewer)
    include_unassigned = can_edit or (
        role_name == ENGINEERING_MANAGER and scope is None
    )

    team_query = (
        select(Team)
        .options(selectinload(Team.team_lead))
        .where(Team.is_active.is_(True))
        .order_by(Team.name)
    )
    if scope is not None:
        if not scope:
            return OrganizationChartRead(
                teams=[],
                unassigned=[],
                scope="none",
                note=(
                    "No teams are in your organization-chart scope. "
                    "Engineering Managers see their division; team leaders see only teams they lead."
                ),
            )
        team_query = team_query.where(Team.id.in_(scope))

    teams = db.scalars(team_query).all()
    team_ids = {team.id for team in teams}

    primary_members = db.scalars(
        select(TeamMember)
        .options(
            selectinload(TeamMember.user).selectinload(User.role),
            selectinload(TeamMember.user).selectinload(User.stream),
            selectinload(TeamMember.user).selectinload(User.manager),
        )
        .where(
            TeamMember.is_primary.is_(True),
            TeamMember.team_id.in_(team_ids) if team_ids else False,
        )
    ).all()

    members_by_team: dict[UUID, list[TeamMember]] = {}
    assigned_user_ids: set[UUID] = set()
    for member in primary_members:
        user = member.user
        if user is None or user.is_deleted or not user.is_active:
            continue
        members_by_team.setdefault(member.team_id, []).append(member)
        assigned_user_ids.add(member.user_id)

    columns: list[OrgChartTeamColumn] = []
    for team in teams:
        lead_name = None
        if team.team_lead is not None:
            lead_name = f"{team.team_lead.first_name} {team.team_lead.last_name}".strip()
        people = sorted(
            (
                _person_from_user(row.user, member=row, can_edit=can_edit)
                for row in members_by_team.get(team.id, [])
                if row.user is not None
            ),
            key=lambda row: row.name.lower(),
        )
        columns.append(
            OrgChartTeamColumn(
                team_id=team.id,
                team_name=team.name,
                colour=team.colour or "#1976d2",
                team_lead_id=team.team_lead_id,
                team_lead_name=lead_name,
                member_count=len(people),
                people=people,
            )
        )

    unassigned: list[OrgChartPerson] = []
    if include_unassigned:
        active_users = db.scalars(
            select(User)
            .options(
                selectinload(User.role),
                selectinload(User.stream),
                selectinload(User.manager),
            )
            .where(User.is_active.is_(True), User.is_deleted.is_(False))
            .order_by(User.first_name, User.last_name)
        ).all()
        unassigned = [
            _person_from_user(user, allow_assign=True, can_edit=can_edit)
            for user in active_users
            if user.id not in assigned_user_ids
        ]

    if scope is None:
        scope_label = "full"
        note = (
            "Drag a person card onto another team. Moves use dated primary-team transfers "
            "so salary is prorated for P&L by calendar days."
            if can_edit
            else "Organization-wide view. Resource moves require an Admin."
        )
    else:
        scope_label = "division" if role_name == ENGINEERING_MANAGER else "team"
        note = (
            "Showing teams in your management scope only. "
            "Engineering Managers see their division; team leaders see teams they lead."
        )

    return OrganizationChartRead(
        teams=columns,
        unassigned=unassigned,
        scope=scope_label,
        note=note,
    )
