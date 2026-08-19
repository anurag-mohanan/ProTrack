"""Completed projects remain timesheet-eligible with explicit post-completion types."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.enums import ExecutionStatus, PostCompletionWorkType, TimesheetStatus, WorkCategory
from app.models.models import Project, Stream, Team, Timesheet, TimesheetEntry
from app.services.post_completion_work import completed_post_completion_metrics
from app.services.project_calculation_service import calculate_hours
from tests.conftest import IDS, get_design_task_type_id


def _complete_seed_project(session, client) -> Project:
    project = session.get(Project, IDS["project"])
    assert project is not None
    completed_at = datetime(2026, 6, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    project.execution_status = ExecutionStatus.completed
    project.completed_at = completed_at
    session.commit()
    return project


def _timesheet(client) -> str:
    response = client.post(
        "/api/v1/timesheets",
        headers=client.auth_headers,
        json={"user_id": str(IDS["user_binil"]), "week_start": "2026-06-08"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_completed_project_is_listed_for_timesheets(client, session):
    _complete_seed_project(session, client)
    rows = client.get(
        "/api/v1/lookups/timesheet-projects",
        headers=client.auth_headers,
    )
    assert rows.status_code == 200, rows.text
    match = next((row for row in rows.json() if row["id"] == str(IDS["project"])), None)
    assert match is not None
    assert match["execution_status"] == "completed"


def test_completed_project_requires_post_completion_type(client, session):
    _complete_seed_project(session, client)
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "4",
        },
    )
    assert response.status_code in (400, 422), response.text


def test_additional_work_on_completed_project_does_not_reopen(client, session):
    project = _complete_seed_project(session, client)
    completed_at = project.completed_at
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "4",
            "post_completion_type": "additional_work",
            "description": "Late drawing pack request",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["post_completion_type"] == "additional_work"
    session.refresh(project)
    assert project.execution_status == ExecutionStatus.completed
    assert project.completed_at == completed_at


def test_rework_requires_comment(client, session):
    _complete_seed_project(session, client)
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "2",
            "post_completion_type": "rework",
            "description": "fix",
        },
    )
    assert response.status_code in (400, 422), response.text
    ok = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-11",
            "hours": "2",
            "post_completion_type": "rework",
            "description": "Customer requested revised lifter geometry after tool release.",
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["post_completion_type"] == "rework"


def test_quoted_vs_actual_uses_original_hours_not_post_completion(client, session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.quoted_hours = Decimal("10")
    session.commit()

    timesheet = Timesheet(
        user_id=IDS["user_binil"],
        week_start=date(2026, 6, 1),
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=date(2026, 6, 2),
            hours=Decimal("8"),
            work_category=WorkCategory.productive,
            is_billable=True,
            project_id=project.id,
            customer_id=project.customer_id,
            post_completion_type=None,
        )
    )
    project.execution_status = ExecutionStatus.completed
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=date(2026, 6, 3),
            hours=Decimal("5"),
            work_category=WorkCategory.productive,
            is_billable=True,
            project_id=project.id,
            customer_id=project.customer_id,
            post_completion_type=PostCompletionWorkType.additional_work,
        )
    )
    session.commit()

    hours = calculate_hours(session, project)
    assert hours.original == Decimal("8.00")
    assert hours.additional_work == Decimal("5.00")
    assert hours.actual == Decimal("13.00")
    assert hours.variance == Decimal("-2.00")
    assert hours.remaining == Decimal("2.00")


def test_team_can_block_post_completion_hours(client, session):
    project = _complete_seed_project(session, client)
    team = Team(name="No Post Completion Team", is_active=True)
    session.add(team)
    session.flush()
    team.allow_post_completion_timesheet = False
    project.team_id = team.id
    session.commit()

    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(project.id),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "3",
            "post_completion_type": "additional_work",
        },
    )
    assert response.status_code in (400, 422), response.text


def test_active_project_rejects_post_completion_type(client, session):
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "3",
            "post_completion_type": "additional_work",
        },
    )
    assert response.status_code in (400, 422), response.text
    assert "Post-completion work type applies only" in response.text


def test_customer_change_and_internal_correction_require_comment(client, session):
    _complete_seed_project(session, client)
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    missing = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "2",
            "post_completion_type": "customer_change",
        },
    )
    assert missing.status_code in (400, 422), missing.text
    change = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "2",
            "post_completion_type": "customer_change",
            "description": "Customer requested revised lifter geometry after tool release.",
        },
    )
    assert change.status_code == 201, change.text
    assert change.json()["post_completion_type"] == "customer_change"
    internal = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-11",
            "hours": "1",
            "post_completion_type": "internal_correction",
            "description": "Internal drawing error found after release.",
        },
    )
    assert internal.status_code == 201, internal.text
    assert internal.json()["post_completion_type"] == "internal_correction"


def test_stream_can_block_post_completion_hours(client, session):
    _complete_seed_project(session, client)
    stream = session.get(Stream, IDS["stream"])
    assert stream is not None
    stream.allow_post_completion_timesheet = False
    session.commit()

    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "3",
            "post_completion_type": "additional_work",
        },
    )
    assert response.status_code in (400, 422), response.text


def test_post_completion_entry_survives_timesheet_submit(client, session):
    _complete_seed_project(session, client)
    timesheet_id = _timesheet(client)
    task_id = str(get_design_task_type_id(session))
    created = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": str(IDS["project"]),
            "task_type_id": task_id,
            "entry_date": "2026-06-10",
            "hours": "3",
            "post_completion_type": "additional_work",
            "description": "Late drawing pack request",
        },
    )
    assert created.status_code == 201, created.text
    submitted = client.post(
        f"/api/v1/timesheets/{timesheet_id}/submit",
        headers=client.auth_headers,
    )
    assert submitted.status_code == 200, submitted.text
    listed = client.get(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        params={"timesheet_id": timesheet_id},
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    match = next((row for row in rows if row["id"] == created.json()["id"]), None)
    assert match is not None
    assert match["post_completion_type"] == "additional_work"
    assert match["description"] == "Late drawing pack request"


def test_dashboard_metrics_count_completed_rework(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.execution_status = ExecutionStatus.completed
    timesheet = Timesheet(
        user_id=IDS["user_binil"],
        week_start=date(2026, 6, 8),
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=date(2026, 6, 10),
            hours=Decimal("21"),
            work_category=WorkCategory.productive,
            is_billable=True,
            project_id=project.id,
            customer_id=project.customer_id,
            post_completion_type=PostCompletionWorkType.rework,
            description="Customer requested revised lifter geometry after tool release.",
        )
    )
    session.commit()
    metrics = completed_post_completion_metrics(
        session,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
    )
    assert metrics["completed_with_rework"] == 1
    assert metrics["customers_with_rework"] == 1
    assert metrics["post_completion_hours_this_month"] == Decimal("21")
    assert metrics["projects_high_post_completion_hours"] == 1
