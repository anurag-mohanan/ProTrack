"""Leadership scope KPIs for EM, Design Leader, and Team Leader dashboards."""

from uuid import uuid4

from sqlalchemy import select

from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember, User
from app.services.kpi_engine import get_leadership_scope
from tests.conftest import IDS, login


def _add_team(session, *, name: str, lead_id, member_ids: list) -> Team:
    team = Team(
        id=uuid4(),
        name=name,
        colour="#2563eb",
        is_active=True,
        team_lead_id=lead_id,
    )
    session.add(team)
    session.flush()
    for index, user_id in enumerate(member_ids):
        session.add(
            TeamMember(
                id=uuid4(),
                team_id=team.id,
                user_id=user_id,
                relationship_type=(
                    TeamRelationshipType.team_leader
                    if user_id == lead_id
                    else TeamRelationshipType.member
                ),
                is_primary=index == 0,
            )
        )
    session.commit()
    return team


def test_engineering_manager_leadership_scope_counts_teams_and_members(session):
    em = session.get(User, IDS["user_pm"])
    assert em is not None

    team_a = _add_team(
        session,
        name=f"EM Scope A {uuid4().hex[:6]}",
        lead_id=IDS["user_anurag"],
        member_ids=[IDS["user_pm"], IDS["user_binil"], IDS["user_anurag"]],
    )
    team_b = _add_team(
        session,
        name=f"EM Scope B {uuid4().hex[:6]}",
        lead_id=IDS["user_anurag"],
        member_ids=[IDS["user_pm"], IDS["user_ranjith"]],
    )

    for team in (team_a, team_b):
        membership = session.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == em.id,
            )
        )
        assert membership is not None
        membership.relationship_type = TeamRelationshipType.engineering_manager
    session.commit()

    scope = get_leadership_scope(session, em)
    assert scope.show_teams_managed is True
    assert scope.teams_managed >= 2
    assert scope.team_members_under >= 3


def test_design_leader_leadership_scope_counts_assigned_teams(session):
    leader = session.get(User, IDS["user_anurag"])
    assert leader is not None

    _add_team(
        session,
        name=f"DL Scope {uuid4().hex[:6]}",
        lead_id=IDS["user_anurag"],
        member_ids=[IDS["user_anurag"], IDS["user_binil"], IDS["user_ranjith"]],
    )

    scope = get_leadership_scope(session, leader)
    assert scope.show_teams_managed is True
    assert scope.teams_managed >= 1
    assert scope.team_members_under >= 2


def test_team_leader_shows_members_only(session):
    lead = session.get(User, IDS["user_senior_designer"])
    assert lead is not None

    _add_team(
        session,
        name=f"TL Scope {uuid4().hex[:6]}",
        lead_id=IDS["user_senior_designer"],
        member_ids=[IDS["user_senior_designer"], IDS["user_binil"], IDS["user_junior_designer"]],
    )

    scope = get_leadership_scope(session, lead)
    assert scope.show_teams_managed is False
    assert scope.is_team_leader is True
    assert scope.teams_managed >= 1
    assert scope.team_members_under == 2


def test_role_kpis_api_exposes_leadership_for_engineering_manager(client):
    headers = login(client, "pm@prosohm.com")
    response = client.get("/api/v1/dashboard/role-kpis", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "leadership" in payload
    assert "teams_managed" in payload["leadership"]
    assert "team_members_under" in payload["leadership"]
    assert payload["leadership"]["show_teams_managed"] is True
