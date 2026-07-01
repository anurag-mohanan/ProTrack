from decimal import Decimal
import uuid

from sqlalchemy import select

from app.models.enums import MilestoneStatus
from app.models.models import Milestone
from app.services.project_calculation_service import recalculate_project


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
            "work_category": "productive",
            "project_id": project_id,
            "task_type_id": client.task_type_id,
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
            "work_category": "productive",
            "project_id": project_id,
            "task_type_id": client.task_type_id,
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
    assert project["status"] == "in_progress"
    assert project["health"] in {"green", "yellow", "red"}


def test_completed_project_health_is_green(client, auth_headers, session):
    project_id = client.project_id
    _complete_all_milestones(session, project_id)
    recalculate_project(session, project_id)

    response = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["health"] == "green"


def _complete_all_milestones(session, project_id):
    project_uuid = (
        project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    )
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_uuid)
    ).all()
    for milestone in milestones:
        milestone.status = MilestoneStatus.completed
    session.commit()
