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
    assert "surfacer_name" in card
    assert "designer_name" in card
    assert "quoted_hours" in card
    assert "actual_hours" in card
    assert "variance_hours" in card
    assert "variance_percent" in card
    quoted = float(card["quoted_hours"] or 0)
    actual = float(card["actual_hours"] or 0)
    variance_hours = float(card["variance_hours"] or 0)
    assert abs(variance_hours - (actual - quoted)) < 0.05
    if quoted > 0:
        assert card["variance_percent"] is not None
        expected_pct = ((actual - quoted) / quoted) * 100
        assert abs(float(card["variance_percent"]) - expected_pct) < 0.6
    else:
        assert card["variance_percent"] is None


def test_planning_board_team_blocks_include_leadership(client):
    headers = login(client, "planning-board@prosohm.com")
    body = client.get("/api/v1/ai/executive-wall", headers=headers).json()
    teams = body.get("teams_live", [])
    if not teams:
        return
    team = teams[0]
    assert "engineering_manager_name" in team
    assert "design_leader_name" in team
    assert "on_hold_count" in team
    # Live tools = active (working/planning) + on hold.
    assert len(team.get("projects", [])) == int(team.get("active_count", 0)) + int(
        team.get("on_hold_count", 0)
    )
    # Active tools appear before on-hold tools in the list.
    statuses = [p.get("execution_status") for p in team.get("projects", [])]
    if "on_hold" in statuses and any(s != "on_hold" for s in statuses):
        first_hold = statuses.index("on_hold")
        assert all(s == "on_hold" for s in statuses[first_hold:])


def test_planning_board_includes_empty_team_placeholders(client):
    """Wall returns company active teams even when some have zero live projects."""
    headers = login(client, "planning-board@prosohm.com")
    teams = client.get("/api/v1/lookups/teams", headers=headers).json()
    wall = client.get("/api/v1/ai/executive-wall", headers=headers).json()
    active_team_names = {row["name"] for row in teams if row.get("is_active", True)}
    wall_names = {row["team_name"] for row in wall.get("teams_live", []) if row.get("team_id")}
    # Every active company team should have a column (placeholder allowed).
    assert active_team_names.issubset(wall_names)


def test_planning_board_room_team_filter(client):
    headers = login(client, "planning-board@prosohm.com")
    teams = client.get("/api/v1/lookups/teams", headers=headers).json()
    if not teams:
        return
    team_id = teams[0]["id"]
    wall = client.get(
        f"/api/v1/ai/executive-wall?team_ids={team_id}",
        headers=headers,
    ).json()
    live = wall.get("teams_live", [])
    assert len(live) == 1
    assert live[0]["team_id"] == team_id
    assert "projects" in live[0]


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


def test_planning_board_excluded_from_dashboard_resources(client, auth_headers):
    """Virtual Planning Board user must never appear as capacity / utilization."""
    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    availability = summary.get("designer_availability") or []
    names = [row.get("designer_name", "") for row in availability]
    assert not any("Planning Board" in name for name in names)

    workload = client.get("/api/v1/dashboard/workload", headers=auth_headers).json()
    for row in workload:
        assert "Planning Board" not in (row.get("designer_name") or "")

    grid = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "week"},
    )
    assert grid.status_code == 200
    designers = grid.json().get("designers") or []
    assert not any("Planning Board" in (row.get("designer_name") or "") for row in designers)


def test_planning_board_not_in_utilization_users(test_session_factory, seeded_db):
    from app.services.kpi_participation import (
        capacity_planning_users,
        utilization_users,
        workload_planning_users,
    )

    with test_session_factory() as session:
        for pool in (
            utilization_users(session),
            capacity_planning_users(session),
            workload_planning_users(session),
        ):
            assert all((u.role.name if u.role else "") != "Planning Board" for u in pool)
            assert all(
                f"{u.first_name} {u.last_name}".strip() != "Planning Board" for u in pool
            )
