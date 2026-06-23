from decimal import Decimal


def test_actual_hours_recalculates_on_timesheet_entry_create(client, auth_headers):
    project_id = client.project_id

    before = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert Decimal(str(before["actual_hours"])) == Decimal("0")

    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": str(client.user_id),
            "week_start": "2026-06-16",
            "status": "draft",
        },
        headers=auth_headers,
    )
    assert timesheet.status_code == 201

    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet.json()["id"],
            "project_id": project_id,
            "entry_date": "2026-06-17",
            "hours": 8,
            "description": "Design work",
        },
        headers=auth_headers,
    )
    assert entry.status_code == 201

    after = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert Decimal(str(after["actual_hours"])) == Decimal("8")


def test_actual_hours_recalculates_on_entry_update_and_delete(client, auth_headers):
    project_id = client.project_id

    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": str(client.user_id),
            "week_start": "2026-06-16",
            "status": "draft",
        },
        headers=auth_headers,
    ).json()

    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet["id"],
            "project_id": project_id,
            "entry_date": "2026-06-17",
            "hours": 4,
        },
        headers=auth_headers,
    ).json()

    updated = client.patch(
        f"/api/v1/timesheet-entries/{entry['id']}",
        json={"hours": 6},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert Decimal(str(project["actual_hours"])) == Decimal("6")

    deleted = client.delete(
        f"/api/v1/timesheet-entries/{entry['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert Decimal(str(project["actual_hours"])) == Decimal("0")


def test_project_read_includes_progress_and_health(client, auth_headers):
    project_id = client.project_id
    milestone_id = client.milestone_id

    client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project["progress_percent"] == "14.29"
    assert project["health"] in {"green", "yellow", "red"}


def test_completed_project_health_is_green(client, auth_headers):
    project_id = client.project_id
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["health"] == "green"
