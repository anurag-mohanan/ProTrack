"""Timesheet entries must use task types from the project's stream."""

import uuid
from decimal import Decimal

from app.models.models import Stream, TaskType
from tests.conftest import IDS


def test_productive_entry_rejects_task_type_from_other_stream(client, session):
    other_stream = Stream(id=uuid.uuid4(), name="Fixture Stream", is_active=True)
    session.add(other_stream)
    wrong_task = TaskType(
        id=uuid.uuid4(),
        stream_id=other_stream.id,
        name="Design",
        description="Wrong stream",
        is_billable=True,
        is_active=True,
    )
    session.add(wrong_task)
    session.commit()

    timesheet = client.post(
        "/api/v1/timesheets",
        headers=client.auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "week_start": "2026-06-09",
        },
    )
    assert timesheet.status_code == 201
    timesheet_id = timesheet.json()["id"]

    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": str(wrong_task.id),
            "entry_date": "2026-06-10",
            "hours": "3",
            "description": "Assisting designer",
            "contribution_reason": "assisting_designer",
        },
    )
    assert response.status_code == 422
    assert "stream" in response.json()["detail"].lower()


def test_productive_entry_allows_assisting_designer_contribution_reason(client):
    task_types = client.get("/api/v1/lookups/task-types", headers=client.auth_headers).json()
    project = client.get(f"/api/v1/projects/{client.project_id}", headers=client.auth_headers).json()
    stream_id = project.get("stream_id")
    design = next(
        row
        for row in task_types
        if row["name"] == "Design" and row["stream_id"] == stream_id
    )

    timesheet = client.post(
        "/api/v1/timesheets",
        headers=client.auth_headers,
        json={
            "user_id": str(IDS["user_anurag"]),
            "week_start": "2026-06-09",
        },
    )
    assert timesheet.status_code == 201

    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet.json()["id"],
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": design["id"],
            "entry_date": "2026-06-10",
            "hours": "3",
            "description": "For block out assembly work",
            "contribution_reason": "assisting_designer",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["contribution_reason"] == "assisting_designer"
    assert body["task_type_id"] == design["id"]
