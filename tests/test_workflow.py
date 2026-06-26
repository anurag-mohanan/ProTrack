"""Tests for Phase 5.1 workflow and permissions."""

from decimal import Decimal

from tests.conftest import IDS, login


def _create_draft_timesheet(client, auth_headers, user_id: str, week_start: str = "2026-06-16"):
    response = client.post(
        "/api/v1/timesheets",
        json={"user_id": user_id, "week_start": week_start},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def _add_entry(client, auth_headers, timesheet_id: str, project_id: str, hours: int = 8):
    response = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet_id,
            "project_id": project_id,
            "entry_date": "2026-06-17",
            "hours": hours,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def test_designer_cannot_approve_timesheet(client):
    designer_headers = login(client, "binil@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    response = client.post(
        f"/api/v1/timesheets/{timesheet['id']}/approve",
        json={"comments": "Self approve"},
        headers=designer_headers,
    )
    assert response.status_code == 403


def test_design_leader_can_approve_team_timesheet(client):
    designer_headers = login(client, "binil@prosohm.com")
    leader_headers = login(client, "anurag@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    response = client.post(
        f"/api/v1/timesheets/{timesheet['id']}/approve",
        json={"comments": "Looks good"},
        headers=leader_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approval_comments"] == "Looks good"


def test_admin_can_approve_all_timesheets(client, auth_headers):
    designer_headers = login(client, "binil@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    response = client.post(
        f"/api/v1/timesheets/{timesheet['id']}/approve",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_approved_timesheet_cannot_be_edited(client, auth_headers):
    designer_headers = login(client, "binil@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    entry = _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/approve",
        json={},
        headers=auth_headers,
    )
    response = client.patch(
        f"/api/v1/timesheet-entries/{entry['id']}",
        json={"hours": 10},
        headers=designer_headers,
    )
    assert response.status_code == 403


def test_reject_requires_comments(client, auth_headers):
    designer_headers = login(client, "binil@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    response = client.post(
        f"/api/v1/timesheets/{timesheet['id']}/reject",
        json={"comments": "Please split tooling review and detailing into separate entries."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_workflow_creates_notifications_and_activity(client, auth_headers):
    designer_headers = login(client, "binil@prosohm.com")
    timesheet = _create_draft_timesheet(client, designer_headers, str(IDS["user_binil"]))
    _add_entry(client, designer_headers, timesheet["id"], str(IDS["project"]))
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/submit",
        headers=designer_headers,
    )
    client.post(
        f"/api/v1/timesheets/{timesheet['id']}/approve",
        json={"comments": "Approved"},
        headers=auth_headers,
    )

    notifications = client.get("/api/v1/notifications", headers=designer_headers).json()
    assert any(item["notification_type"] == "timesheet_approved" for item in notifications)

    activities = client.get(
        f"/api/v1/activities/project/{IDS['project']}",
        headers=auth_headers,
    ).json()
    actions = {item["action"] for item in activities}
    assert "timesheet_submitted" in actions
    assert "timesheet_approved" in actions


def test_milestone_complete_logs_activity(client, auth_headers):
    response = client.patch(
        f"/api/v1/milestones/{client.milestone_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    activities = client.get(
        f"/api/v1/activities/project/{IDS['project']}",
        headers=auth_headers,
    ).json()
    assert any(item["action"] == "milestone_completed" for item in activities)


def test_dashboard_workflow_endpoint(client, auth_headers):
    response = client.get("/api/v1/dashboard/workflow", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "my_tasks" in body
    assert "pending_timesheet_approvals" in body
    assert "recent_activity" in body
