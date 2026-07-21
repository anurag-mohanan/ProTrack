"""Organization chart read model — department hierarchy + primary-team moves."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import (
    DESIGN_LEADER,
    ENGINEERING_MANAGER,
    get_role_name,
    is_admin,
)
from app.core.team_access import get_organization_chart_team_ids
from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME
from app.models.enums import TeamRelationshipType
from app.models.models import OrgDepartment, Role, Team, TeamMember, User

MANAGING_DIRECTOR_ROLE = "Managing Director"
from app.services.performance_review_service import format_tenure

LEADERSHIP_ROLES = frozenset(
    {
        ENGINEERING_MANAGER,
        DESIGN_LEADER,
        "Managing Director",
        "Director of Engineering",
        "Director of Sales",
        "Director of HR",
        "Director of Accounts",
        "Director of IT",
        "Team Leader",
    }
)


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
    org_department_id: UUID | None = None
    is_department_head: bool = False
    is_leadership: bool = False


class OrgChartTeamColumn(BaseModel):
    team_id: UUID
    team_name: str
    colour: str
    team_lead_id: UUID | None = None
    team_lead_name: str | None = None
    member_count: int = 0
    org_department_id: UUID | None = None
    is_delivery_team: bool = True
    people: list[OrgChartPerson] = Field(default_factory=list)


class OrgChartDepartment(BaseModel):
    department_id: UUID
    code: str
    name: str
    description: str | None = None
    colour: str
    sort_order: int = 100
    head_user_id: UUID | None = None
    head_name: str | None = None
    head_title: str | None = None
    member_count: int = 0
    leaders: list[OrgChartPerson] = Field(default_factory=list)
    staff: list[OrgChartPerson] = Field(default_factory=list)
    teams: list[OrgChartTeamColumn] = Field(default_factory=list)


class OrganizationChartRead(BaseModel):
    company_root: OrgChartPerson | None = None
    departments: list[OrgChartDepartment] = Field(default_factory=list)
    teams: list[OrgChartTeamColumn] = Field(default_factory=list)
    unassigned: list[OrgChartPerson] = Field(default_factory=list)
    scope: str = "full"
    note: str = (
        "Departments group the company for growth. Delivery teams sit under Engineering; "
        "Admins can still drag people between teams with dated P&L transfers."
    )


def _person_from_user(
    user: User,
    *,
    member: TeamMember | None = None,
    allow_assign: bool = False,
    can_edit: bool = False,
    org_department_id: UUID | None = None,
    is_department_head: bool = False,
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
    is_leadership = bool(
        is_department_head
        or (role_name in LEADERSHIP_ROLES)
        or (user.designation and "director" in user.designation.lower())
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
        org_department_id=org_department_id or user.org_department_id,
        is_department_head=is_department_head,
        is_leadership=is_leadership,
    )


def _is_delivery_team(team: Team) -> bool:
    return team.name != CORPORATE_TEAM_NAME


def _resolve_managing_director(db: Session) -> User | None:
    """Active user holding the Managing Director role (chart company root)."""
    return db.scalars(
        select(User)
        .join(Role, Role.id == User.role_id)
        .options(selectinload(User.role), selectinload(User.manager))
        .where(
            Role.name == MANAGING_DIRECTOR_ROLE,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
        .order_by(User.first_name, User.last_name)
    ).first()


def _resolve_person_department_id(
    user: User,
    *,
    member: TeamMember | None,
    team_by_id: dict[UUID, Team],
    fallback_engineering_id: UUID | None,
) -> UUID | None:
    if user.org_department_id is not None:
        return user.org_department_id
    if member is not None:
        team = team_by_id.get(member.team_id)
        if team is not None and team.org_department_id is not None:
            return team.org_department_id
    return fallback_engineering_id


def build_organization_chart(db: Session, *, viewer: User) -> OrganizationChartRead:
    scope = get_organization_chart_team_ids(db, viewer)
    can_edit = is_admin(db, viewer)
    role_name = get_role_name(db, viewer)
    include_unassigned = can_edit or (
        role_name == ENGINEERING_MANAGER and scope is None
    )

    org_departments = db.scalars(
        select(OrgDepartment)
        .options(selectinload(OrgDepartment.head_user).selectinload(User.role))
        .where(OrgDepartment.is_active.is_(True))
        .order_by(OrgDepartment.sort_order, OrgDepartment.name)
    ).all()
    engineering_id = next(
        (row.id for row in org_departments if row.code == "engineering"), None
    )

    team_query = (
        select(Team)
        .options(selectinload(Team.team_lead), selectinload(Team.org_department))
        .where(Team.is_active.is_(True))
        .order_by(Team.name)
    )
    if scope is not None:
        if not scope:
            return OrganizationChartRead(
                departments=[],
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
    team_by_id = {team.id: team for team in teams}

    primary_members = db.scalars(
        select(TeamMember)
        .options(
            selectinload(TeamMember.user).selectinload(User.role),
            selectinload(TeamMember.user).selectinload(User.stream),
            selectinload(TeamMember.user).selectinload(User.manager),
            selectinload(TeamMember.user).selectinload(User.org_department),
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

    flat_columns: list[OrgChartTeamColumn] = []
    for team in teams:
        lead_name = None
        if team.team_lead is not None:
            lead_name = f"{team.team_lead.first_name} {team.team_lead.last_name}".strip()
        people = sorted(
            (
                _person_from_user(
                    row.user,
                    member=row,
                    can_edit=can_edit,
                    org_department_id=_resolve_person_department_id(
                        row.user,
                        member=row,
                        team_by_id=team_by_id,
                        fallback_engineering_id=engineering_id,
                    ),
                )
                for row in members_by_team.get(team.id, [])
                if row.user is not None
            ),
            key=lambda row: row.name.lower(),
        )
        flat_columns.append(
            OrgChartTeamColumn(
                team_id=team.id,
                team_name=team.name,
                colour=team.colour or "#1976d2",
                team_lead_id=team.team_lead_id,
                team_lead_name=lead_name,
                member_count=len(people),
                org_department_id=team.org_department_id,
                is_delivery_team=_is_delivery_team(team),
                people=people,
            )
        )

    people_by_dept: dict[UUID, list[OrgChartPerson]] = {row.id: [] for row in org_departments}
    teams_by_dept: dict[UUID, list[OrgChartTeamColumn]] = {row.id: [] for row in org_departments}
    placed_user_ids: set[UUID] = set()

    for column in flat_columns:
        if column.is_delivery_team:
            dept_id = column.org_department_id or engineering_id
            if dept_id is None or dept_id not in teams_by_dept:
                continue
            keep: list[OrgChartPerson] = []
            for person in column.people:
                target_dept = person.org_department_id or dept_id
                if target_dept == dept_id:
                    keep.append(person)
                    placed_user_ids.add(person.user_id)
                elif target_dept in people_by_dept:
                    people_by_dept[target_dept].append(person)
                    placed_user_ids.add(person.user_id)
            teams_by_dept[dept_id].append(
                column.model_copy(update={"people": keep, "member_count": len(keep)})
            )
        else:
            for person in column.people:
                target_dept = person.org_department_id or engineering_id
                if target_dept is None or target_dept not in people_by_dept:
                    continue
                people_by_dept[target_dept].append(person)
                placed_user_ids.add(person.user_id)

    for column in flat_columns:
        for person in column.people:
            if person.user_id in placed_user_ids:
                continue
            target_dept = person.org_department_id or engineering_id
            if target_dept is None or target_dept not in people_by_dept:
                continue
            people_by_dept[target_dept].append(person)
            placed_user_ids.add(person.user_id)

    departments_out: list[OrgChartDepartment] = []
    for dept in org_departments:
        head_name = None
        head_title = None
        if dept.head_user is not None:
            head_name = f"{dept.head_user.first_name} {dept.head_user.last_name}".strip()
            head_title = dept.head_user.designation or (
                dept.head_user.role.name if dept.head_user.role is not None else None
            )

        leaders: list[OrgChartPerson] = []
        staff: list[OrgChartPerson] = []
        for person in sorted(people_by_dept.get(dept.id, []), key=lambda row: row.name.lower()):
            marked = person.model_copy(
                update={
                    "is_department_head": bool(
                        dept.head_user_id and person.user_id == dept.head_user_id
                    ),
                    "is_leadership": bool(
                        person.is_leadership
                        or (dept.head_user_id and person.user_id == dept.head_user_id)
                    ),
                }
            )
            if marked.is_leadership:
                leaders.append(marked)
            else:
                staff.append(marked)

        if dept.head_user_id:
            leaders.sort(
                key=lambda row: (
                    0 if row.user_id == dept.head_user_id else 1,
                    row.name.lower(),
                )
            )

        dept_teams = sorted(
            teams_by_dept.get(dept.id, []),
            key=lambda row: row.team_name.lower(),
        )
        member_count = (
            len(leaders) + len(staff) + sum(team.member_count for team in dept_teams)
        )

        if scope is not None and member_count == 0 and not dept_teams:
            continue

        departments_out.append(
            OrgChartDepartment(
                department_id=dept.id,
                code=dept.code,
                name=dept.name,
                description=dept.description,
                colour=dept.colour or "#1976d2",
                sort_order=dept.sort_order,
                head_user_id=dept.head_user_id,
                head_name=head_name,
                head_title=head_title,
                member_count=member_count,
                leaders=leaders,
                staff=staff,
                teams=dept_teams,
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
                selectinload(User.org_department),
            )
            .where(User.is_active.is_(True), User.is_deleted.is_(False))
            .order_by(User.first_name, User.last_name)
        ).all()
        unassigned = [
            _person_from_user(
                user,
                allow_assign=True,
                can_edit=can_edit,
                org_department_id=user.org_department_id or engineering_id,
            )
            for user in active_users
            if user.id not in assigned_user_ids
        ]

    if scope is None:
        scope_label = "full"
        note = (
            "Departments plan for growth (Management, Engineering, Sales, Accounts, Human Resource, IT). "
            "Engineering holds delivery teams under EM / Design Leadership. "
            + (
                "Drag a card onto a delivery team to transfer primary home (dated for P&L), "
                "or onto a department header to reassign that person's department."
                if can_edit
                else "Resource moves require an Admin."
            )
        )
    else:
        scope_label = "division" if role_name == ENGINEERING_MANAGER else "team"
        note = (
            "Showing departments and teams in your management scope. "
            "Engineering Managers see their division; team leaders see teams they lead."
        )

    company_root: OrgChartPerson | None = None
    if scope is None:
        management = next(
            (row for row in org_departments if row.code == "management"), None
        )
        head_user = management.head_user if management is not None else None
        # Guarantee the Managing Director heads the chart: fall back to the
        # active user holding the "Managing Director" role when no explicit
        # Management head is set.
        if head_user is None or head_user.is_deleted or not head_user.is_active:
            head_user = _resolve_managing_director(db)
        if head_user is not None and head_user.is_active and not head_user.is_deleted:
            company_root = _person_from_user(
                head_user,
                can_edit=can_edit,
                org_department_id=management.id if management is not None else None,
                is_department_head=True,
            )

    return OrganizationChartRead(
        company_root=company_root,
        departments=departments_out,
        teams=flat_columns,
        unassigned=unassigned,
        scope=scope_label,
        note=note,
    )
