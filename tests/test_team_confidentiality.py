"""Team confidentiality: portfolio + assignment visibility."""

from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import delete

from app.core.permissions import can_read_project
from app.core.team_access import (
    get_accessible_team_ids,
    project_visibility_clause,
    resolve_team_scope,
)
from app.models.enums import ExecutionStatus, TeamRelationshipType
from app.models.models import Project, Team, TeamMember, User
from tests.conftest import DEFAULT_PASSWORD, IDS


def _auth(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_two_team_portfolio(session):
    team_a = Team(id=uuid.uuid4(), name="Client A Team", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Client B Team", is_active=True)
    session.add_all([team_a, team_b])
    session.flush()

    dl = session.get(User, IDS["user_anurag"])
    designer = session.get(User, IDS["user_binil"])
    assert dl is not None and designer is not None

    dl.team_id = team_a.id
    designer.team_id = team_a.id
    session.add_all(
        [
            TeamMember(
                team_id=team_a.id,
                user_id=dl.id,
                relationship_type=TeamRelationshipType.team_leader,
                is_primary=True,
            ),
            TeamMember(
                team_id=team_a.id,
                user_id=designer.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            ),
        ]
    )

    due = date.today() + timedelta(days=30)
    own_project = Project(
        id=uuid.uuid4(),
        tool_number="SCOPE-A",
        part_description="Team A work",
        customer_id=IDS["customer"],
        team_id=team_a.id,
        design_leader_id=dl.id,
        designer_id=designer.id,
        quoted_hours=Decimal("10"),
        actual_hours=Decimal("2"),
        due_date=due,
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    other_team_project = Project(
        id=uuid.uuid4(),
        tool_number="SCOPE-B",
        part_description="Confidential Client B",
        customer_id=IDS["customer"],
        team_id=team_b.id,
        quoted_hours=Decimal("20"),
        actual_hours=Decimal("4"),
        due_date=due,
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    cross_util = Project(
        id=uuid.uuid4(),
        tool_number="SCOPE-X",
        part_description="Cross util on Team B",
        customer_id=IDS["customer"],
        team_id=team_b.id,
        designer_id=designer.id,
        quoted_hours=Decimal("8"),
        actual_hours=Decimal("1"),
        due_date=due,
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    session.add_all([own_project, other_team_project, cross_util])
    session.commit()
    return {
        "team_a": team_a,
        "team_b": team_b,
        "own": own_project,
        "other": other_team_project,
        "cross": cross_util,
        "dl": dl,
        "designer": designer,
    }


def test_design_leader_cannot_read_other_team_project(session):
    data = _seed_two_team_portfolio(session)
    assert can_read_project(session, data["dl"], data["own"]) is True
    assert can_read_project(session, data["dl"], data["other"]) is False
    assert can_read_project(session, data["dl"], data["cross"]) is False


def test_designer_sees_team_and_cross_util_only(session):
    data = _seed_two_team_portfolio(session)
    assert can_read_project(session, data["designer"], data["own"]) is True
    assert can_read_project(session, data["designer"], data["cross"]) is True
    assert can_read_project(session, data["designer"], data["other"]) is False


def test_project_list_hides_other_team_work(client, test_session_factory):
    with test_session_factory() as session:
        data = _seed_two_team_portfolio(session)
        other_id = str(data["other"].id)

    headers = _auth(client, "anurag@prosohm.com")
    response = client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200
    tools = {item["tool_number"] for item in response.json()["items"]}
    assert "SCOPE-A" in tools
    assert "SCOPE-B" not in tools
    assert "SCOPE-X" not in tools

    designer_headers = _auth(client, "binil@prosohm.com")
    designer_response = client.get("/api/v1/projects", headers=designer_headers)
    assert designer_response.status_code == 200
    designer_tools = {item["tool_number"] for item in designer_response.json()["items"]}
    assert "SCOPE-A" in designer_tools
    assert "SCOPE-X" in designer_tools
    assert "SCOPE-B" not in designer_tools

    forbidden = client.get(f"/api/v1/projects/{other_id}", headers=headers)
    assert forbidden.status_code in {403, 404}


def test_workload_scoped_to_accessible_teams(client, test_session_factory):
    with test_session_factory() as session:
        data = _seed_two_team_portfolio(session)
        outsider = session.get(User, IDS["user_senior_designer"])
        assert outsider is not None
        outsider.team_id = data["team_b"].id
        session.add(
            TeamMember(
                team_id=data["team_b"].id,
                user_id=outsider.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            )
        )
        session.commit()

    headers = _auth(client, "anurag@prosohm.com")
    response = client.get("/api/v1/dashboard/workload", headers=headers)
    assert response.status_code == 200
    user_ids = {str(row["user_id"]) for row in response.json()}
    assert str(IDS["user_binil"]) in user_ids
    assert str(IDS["user_senior_designer"]) not in user_ids


def test_lookup_teams_scoped(client, test_session_factory):
    with test_session_factory() as session:
        data = _seed_two_team_portfolio(session)
        team_a_id = str(data["team_a"].id)
        team_b_id = str(data["team_b"].id)

    headers = _auth(client, "anurag@prosohm.com")
    response = client.get("/api/v1/lookups/teams", headers=headers)
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert team_a_id in ids
    assert team_b_id not in ids


def test_empty_accessible_teams_is_deny_all_not_org_wide(session):
    dl = session.get(User, IDS["user_anurag"])
    assert dl is not None
    dl.team_id = None
    session.execute(delete(TeamMember).where(TeamMember.user_id == dl.id))
    session.commit()

    accessible = get_accessible_team_ids(session, dl)
    assert accessible == set()
    scoped = resolve_team_scope(session, dl)
    assert scoped == set()
    clause = project_visibility_clause(session, dl)
    assert clause is not None
