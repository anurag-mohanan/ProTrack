"""Teams can be excluded from project ownership without touching existing projects."""

from __future__ import annotations

from tests.conftest import login
from tests.test_engineering_management import _project_payload


def _team(client, headers, **extra) -> dict:
    created = client.post(
        "/api/v1/teams",
        headers=headers,
        json={"name": f"Team {extra.pop('suffix', 'x')}", "colour": "#1976d2", **extra},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_disabled_team_rejects_new_projects_but_keeps_existing(client, session):
    admin = login(client, "admin@prosohm.com")
    team = _team(client, admin, suffix="Ops")
    assert team["projects_enabled"] is True

    project = client.post(
        "/api/v1/projects",
        headers=admin,
        json=_project_payload(session, team_id=team["id"]),
    )
    assert project.status_code == 201, project.text

    disabled = client.patch(
        f"/api/v1/teams/{team['id']}", headers=admin, json={"projects_enabled": False}
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["projects_enabled"] is False

    rejected = client.post(
        "/api/v1/projects",
        headers=admin,
        json=_project_payload(session, team_id=team["id"]),
    )
    assert rejected.status_code == 422
    assert "not enabled for projects" in rejected.text

    still_there = client.get(f"/api/v1/projects/{project.json()['id']}", headers=admin)
    assert still_there.status_code == 200
    assert still_there.json()["team_id"] == team["id"]

    other = _team(client, admin, suffix="Design")
    moved_in = client.patch(
        f"/api/v1/projects/{project.json()['id']}", headers=admin, json={"team_id": other["id"]}
    )
    assert moved_in.status_code == 200, moved_in.text
    moved_back = client.patch(
        f"/api/v1/projects/{project.json()['id']}", headers=admin, json={"team_id": team["id"]}
    )
    assert moved_back.status_code == 422


def test_team_lookup_exposes_projects_enabled(client):
    headers = login(client, "pm@prosohm.com")
    teams = client.get("/api/v1/lookups/teams", headers=headers)
    assert teams.status_code == 200, teams.text
    assert teams.json(), "seeded teams expected"
    assert all("projects_enabled" in row for row in teams.json())


def test_non_admin_cannot_toggle_projects_enabled(client):
    admin = login(client, "admin@prosohm.com")
    team = _team(client, admin, suffix="Locked")
    designer = login(client, "binil@prosohm.com")
    response = client.patch(
        f"/api/v1/teams/{team['id']}", headers=designer, json={"projects_enabled": False}
    )
    assert response.status_code == 403
    unchanged = client.get(f"/api/v1/teams/{team['id']}", headers=admin).json()
    assert unchanged["projects_enabled"] is True
