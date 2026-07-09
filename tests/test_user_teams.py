"""Tests for multi-team user assignments."""

from sqlalchemy import select

from tests.conftest import IDS, login


def test_user_create_with_multiple_teams(client):
    headers = login(client, "admin@prosohm.com")
    team_a = client.post(
        "/api/v1/teams",
        json={"name": "Multi Team A", "colour": "#111111", "is_active": True},
        headers=headers,
    ).json()["id"]
    team_b = client.post(
        "/api/v1/teams",
        json={"name": "Multi Team B", "colour": "#222222", "is_active": True},
        headers=headers,
    ).json()["id"]
    roles = client.get("/api/v1/roles", headers=headers).json()
    role_items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    designer_role = next(role for role in role_items if role["name"] == "Designer")

    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer_role["id"],
            "email": "multi.team.user@prosohm.com",
            "password": "TempPass@123",
            "first_name": "Multi",
            "last_name": "Team",
            "is_active": True,
            "team_assignments": [
                {
                    "team_id": team_a,
                    "relationship_type": "member",
                    "is_primary": True,
                },
                {
                    "team_id": team_b,
                    "relationship_type": "reviewer",
                    "is_primary": False,
                },
            ],
        },
    )
    assert create.status_code == 201
    payload = create.json()
    assert payload["team_id"] == team_a
    assert len(payload["team_assignments"]) == 2
    assert payload["team_names"] == ["Multi Team A", "Multi Team B"]


def test_user_team_assignment_sync_from_legacy_team_id(client, session):
    from app.models.models import TeamMember, User

    headers = login(client, "admin@prosohm.com")
    team = client.post(
        "/api/v1/teams",
        json={"name": "Legacy Sync Team", "colour": "#333333", "is_active": True},
        headers=headers,
    ).json()
    roles = client.get("/api/v1/roles", headers=headers).json()
    role_items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    designer_role = next(role for role in role_items if role["name"] == "Designer")

    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer_role["id"],
            "email": "legacy.team.user@prosohm.com",
            "password": "TempPass@123",
            "first_name": "Legacy",
            "last_name": "Team",
            "is_active": True,
            "team_id": team["id"],
        },
    )
    assert create.status_code == 201
    user_id = create.json()["id"]
    from uuid import UUID

    user = session.get(User, UUID(user_id))
    assert user is not None
    assert str(user.team_id) == team["id"]
    memberships = list(
        session.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all()
    )
    assert len(memberships) == 1
    assert memberships[0].is_primary is True
