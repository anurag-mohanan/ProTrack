"""Planning Board monitor role — read-only wall display access."""

from tests.conftest import IDS, login


def test_planning_board_can_view_executive_wall(client):
    headers = login(client, "planning-board@prosohm.com")
    assert client.get("/api/v1/ai/executive-wall", headers=headers).status_code == 200


def test_planning_board_wall_includes_team_live_and_deliveries(client):
    headers = login(client, "planning-board@prosohm.com")
    response = client.get("/api/v1/ai/executive-wall", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "teams_live" in body
    assert "upcoming_deliveries" in body
    assert "late_deliveries" in body
    assert isinstance(body["teams_live"], list)
    assert isinstance(body["upcoming_deliveries"], list)
    assert isinstance(body["late_deliveries"], list)


def test_planning_board_team_cards_include_progress_and_contributors(client):
    headers = login(client, "planning-board@prosohm.com")
    body = client.get("/api/v1/ai/executive-wall", headers=headers).json()
    projects = [
        project
        for team in body.get("teams_live", [])
        for project in team.get("projects", [])
    ]
    if not projects:
        return
    card = projects[0]
    assert "progress_percent" in card
    assert isinstance(card["progress_percent"], (int, float))
    assert "contributor_names" in card
    assert isinstance(card["contributor_names"], list)


def test_planning_board_can_view_resource_planning_grid(client):
    headers = login(client, "planning-board@prosohm.com")
    response = client.get("/api/v1/dashboard/resource-planning/grid", headers=headers)
    assert response.status_code == 200


def test_planning_board_can_view_workload(client):
    headers = login(client, "planning-board@prosohm.com")
    assert client.get("/api/v1/dashboard/workload", headers=headers).status_code == 200


def test_planning_board_can_view_attention_projects(client):
    headers = login(client, "planning-board@prosohm.com")
    assert client.get("/api/v1/dashboard/attention-projects", headers=headers).status_code == 200


def test_planning_board_forbidden_from_admin_users(client):
    headers = login(client, "planning-board@prosohm.com")
    assert client.get("/api/v1/users", headers=headers).status_code == 403


def test_planning_board_cannot_assign_resource_planning(client):
    headers = login(client, "planning-board@prosohm.com")
    response = client.post(
        "/api/v1/dashboard/resource-planning/assign",
        headers=headers,
        json={"project_id": str(IDS["project"]), "designer_id": str(IDS["user_binil"])},
    )
    assert response.status_code == 403


def test_planning_board_cannot_create_timesheet(client):
    headers = login(client, "planning-board@prosohm.com")
    response = client.post(
        "/api/v1/timesheets",
        headers=headers,
        json={"user_id": str(IDS["user_planning_board"]), "week_start": "2026-06-16"},
    )
    assert response.status_code == 403


def test_planning_board_defaults_have_no_write_specials():
    from app.core.access_control import (
        PLANNING_BOARD,
        default_modules_for_role,
        default_special_permissions_for_role,
    )

    assert default_modules_for_role(PLANNING_BOARD) == ["planning_board"]
    assert default_special_permissions_for_role(PLANNING_BOARD) == []
