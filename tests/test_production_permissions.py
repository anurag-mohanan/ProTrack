"""Production readiness permission tests."""

from tests.conftest import IDS, login


def test_designer_forbidden_from_reports(client):
    headers = login(client, "binil@prosohm.com")
    assert client.get("/api/v1/reports/project-hours", headers=headers).status_code == 403


def test_designer_forbidden_from_workload(client):
    headers = login(client, "binil@prosohm.com")
    assert client.get("/api/v1/dashboard/workload", headers=headers).status_code == 403


def test_designer_forbidden_from_resource_planning_grid(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/dashboard/resource-planning/grid", headers=headers)
    assert response.status_code == 403


def test_design_leader_can_view_reports(client):
    headers = login(client, "anurag@prosohm.com")
    assert client.get("/api/v1/reports/project-hours", headers=headers).status_code == 200


def test_read_only_can_view_reports(client):
    headers = login(client, "readonly@prosohm.com")
    assert client.get("/api/v1/reports/project-hours", headers=headers).status_code == 200


def test_read_only_can_view_resource_planning(client):
    headers = login(client, "readonly@prosohm.com")
    response = client.get("/api/v1/dashboard/resource-planning/grid", headers=headers)
    assert response.status_code == 200


def test_read_only_forbidden_from_admin_users(client):
    headers = login(client, "readonly@prosohm.com")
    assert client.get("/api/v1/users", headers=headers).status_code == 403


def test_read_only_cannot_create_timesheet(client):
    headers = login(client, "readonly@prosohm.com")
    response = client.post(
        "/api/v1/timesheets",
        headers=headers,
        json={"user_id": str(IDS["user_readonly"]), "week_start": "2026-06-16"},
    )
    assert response.status_code == 403
