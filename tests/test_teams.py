"""Tests for teams, team members, project team assignment, and filters."""

from uuid import UUID

from tests.conftest import IDS, login


def test_team_crud_and_members(client, session):
    from app.models.models import Team, TeamMember

    create = client.post(
        "/api/v1/teams",
        json={
            "name": "Automotive Team",
            "description": "Automotive projects",
            "colour": "#2196f3",
            "team_lead_id": str(IDS["user_anurag"]),
            "is_active": True,
        },
        headers=client.auth_headers,
    )
    assert create.status_code == 201
    team = create.json()
    team_id = team["id"]
    assert team["name"] == "Automotive Team"
    assert team["member_count"] == 1

    add_member = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={
            "user_id": str(IDS["user_binil"]),
            "role_within_team": "Designer",
        },
        headers=client.auth_headers,
    )
    assert add_member.status_code == 201

    members = client.get(
        f"/api/v1/teams/{team_id}/members",
        headers=client.auth_headers,
    )
    assert members.status_code == 200
    assert len(members.json()) == 2

    transfer_team = client.post(
        "/api/v1/teams",
        json={"name": "Transfer Target", "colour": "#4caf50", "is_active": True},
        headers=client.auth_headers,
    )
    target_id = transfer_team.json()["id"]
    member_id = members.json()[0]["id"]

    transfer = client.post(
        f"/api/v1/teams/{team_id}/members/{member_id}/transfer",
        json={"target_team_id": target_id},
        headers=client.auth_headers,
    )
    assert transfer.status_code == 200
    assert transfer.json()["team_id"] == target_id

    db_team = session.get(Team, UUID(team_id))
    assert db_team is not None
    db_member = session.get(TeamMember, UUID(member_id))
    assert db_member is not None
    assert db_member.team_id == UUID(target_id)


def test_project_team_assignment_and_filters(client):
    team = client.post(
        "/api/v1/teams",
        json={"name": "Filter Team", "colour": "#ff9800", "is_active": True},
        headers=client.auth_headers,
    ).json()
    team_id = team["id"]

    project_id = client.project_id
    patch = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"team_id": team_id},
        headers=client.auth_headers,
    )
    assert patch.status_code == 200
    assert patch.json()["team_id"] == team_id

    by_team = client.get(
        f"/api/v1/projects?team_id={team_id}",
        headers=client.auth_headers,
    )
    assert by_team.status_code == 200
    assert len(by_team.json()) == 1

    by_customer = client.get(
        f"/api/v1/projects?customer_ids={IDS['customer']}",
        headers=client.auth_headers,
    )
    assert by_customer.status_code == 200
    assert len(by_customer.json()) >= 1


def test_dashboard_team_filter(client):
    team = client.post(
        "/api/v1/teams",
        json={"name": "Dashboard Team", "colour": "#9c27b0", "is_active": True},
        headers=client.auth_headers,
    ).json()

    client.patch(
        f"/api/v1/projects/{client.project_id}",
        json={"team_id": team["id"]},
        headers=client.auth_headers,
    )

    summary = client.get(
        f"/api/v1/dashboard/summary?team_id={team['id']}",
        headers=client.auth_headers,
    ).json()
    assert summary["active_projects"] >= 1


def test_team_reports_and_resource_planning(client):
    team = client.post(
        "/api/v1/teams",
        json={"name": "Reports Team", "colour": "#607d8b", "is_active": True},
        headers=client.auth_headers,
    ).json()

    client.patch(
        f"/api/v1/projects/{client.project_id}",
        json={"team_id": team["id"]},
        headers=client.auth_headers,
    )

    projects_by_team = client.get(
        "/api/v1/reports/projects-by-team",
        headers=client.auth_headers,
    )
    assert projects_by_team.status_code == 200
    assert any(row["team_name"] == "Reports Team" for row in projects_by_team.json())

    resource = client.get(
        "/api/v1/dashboard/resource-planning",
        headers=client.auth_headers,
    )
    assert resource.status_code == 200
    assert isinstance(resource.json(), list)


def test_team_delete(client):
    create = client.post(
        "/api/v1/teams",
        json={"name": "Delete Me Team", "colour": "#111111", "is_active": True},
        headers=client.auth_headers,
    )
    assert create.status_code == 201
    team_id = create.json()["id"]

    delete = client.delete(f"/api/v1/teams/{team_id}", headers=client.auth_headers)
    assert delete.status_code == 204

    get_team = client.get(f"/api/v1/teams/{team_id}", headers=client.auth_headers)
    assert get_team.status_code == 404


def test_user_team_assignment_syncs_membership(client, session):
    from app.models.models import TeamMember

    team = client.post(
        "/api/v1/teams",
        json={"name": "User Team", "colour": "#abcdef", "is_active": True},
        headers=client.auth_headers,
    ).json()

    create_user = client.post(
        "/api/v1/users",
        json={
            "first_name": "Team",
            "last_name": "Member",
            "email": "team.member@prosohm.com",
            "role_id": str(IDS["role_designer"]),
            "password": "Password@123",
            "team_id": team["id"],
            "is_active": True,
        },
        headers=client.auth_headers,
    )
    assert create_user.status_code == 201
    user = create_user.json()
    assert user["team_id"] == team["id"]
    assert user["team_name"] == "User Team"

    members = client.get(
        f"/api/v1/teams/{team['id']}/members",
        headers=client.auth_headers,
    ).json()
    assert len(members) == 1
    assert members[0]["user_id"] == user["id"]

    client.patch(
        f"/api/v1/users/{user['id']}",
        json={"team_id": None},
        headers=client.auth_headers,
    )
    members_after = client.get(
        f"/api/v1/teams/{team['id']}/members",
        headers=client.auth_headers,
    ).json()
    assert len(members_after) == 0


def test_lookups_teams_available_to_authenticated_users(client):
    client.post(
        "/api/v1/teams",
        json={"name": "Lookup Team", "colour": "#795548", "is_active": True},
        headers=client.auth_headers,
    )
    headers = login(client, "anurag@prosohm.com")
    response = client.get("/api/v1/lookups/teams", headers=headers)
    assert response.status_code == 200
    assert any(item["name"] == "Lookup Team" for item in response.json())
