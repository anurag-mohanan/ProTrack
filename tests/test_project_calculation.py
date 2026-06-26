import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import MilestoneStatus, ProjectHealth, ProjectStatus
from app.models.models import Milestone, Project
from app.services.project_calculation_service import (
    calculate_hours,
    calculate_progress,
    calculate_project_status,
    recalculate_project,
)
from tests.conftest import IDS


def _complete_n_milestones(session, project_id, count: int) -> None:
    project_uuid = (
        project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    )
    milestones = session.scalars(
        select(Milestone)
        .where(Milestone.project_id == project_uuid)
        .order_by(Milestone.sort_order)
    ).all()
    for milestone in milestones[:count]:
        milestone.status = MilestoneStatus.completed
    session.commit()


def test_scenario_1_create_project_defaults(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=30)
    session.commit()
    recalculate_project(session, project.id)

    progress = calculate_progress(session, project)
    assert progress.progress_percent == Decimal("0.00")
    assert project.status == ProjectStatus.not_started
    assert project.health == ProjectHealth.green


def test_scenario_2_complete_one_milestone(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 1)
    recalculate_project(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.progress_percent == Decimal("14.29")
    assert project is not None
    assert project.status == ProjectStatus.in_progress


def test_scenario_3_complete_all_milestones(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 7)
    recalculate_project(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.progress_percent == Decimal("100.00")
    assert project is not None
    assert project.status == ProjectStatus.completed
    assert project.health == ProjectHealth.green


def test_scenario_4_due_date_in_past_health_red(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() - timedelta(days=1)
    project.status = ProjectStatus.in_progress
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.red


def test_scenario_5_due_date_within_five_days_health_yellow(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=3)
    project.status = ProjectStatus.in_progress
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.yellow


def test_scenario_6_due_date_far_future_health_green(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=10)
    project.status = ProjectStatus.in_progress
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.green


def test_calculate_project_status_rules():
    assert calculate_project_status(Decimal("0.00")) == ProjectStatus.not_started
    assert calculate_project_status(Decimal("14.29")) == ProjectStatus.in_progress
    assert calculate_project_status(Decimal("100.00")) == ProjectStatus.completed


def test_calculate_hours_formulas(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.quoted_hours = Decimal("120.00")
    project.actual_hours = Decimal("30.00")
    session.commit()

    hours = calculate_hours(session, project)
    assert hours.quoted == Decimal("120.00")
    assert hours.actual == Decimal("0.00")
    assert hours.remaining == Decimal("120.00")
    assert hours.variance == Decimal("-120.00")


def test_milestone_patch_recalculates_project_status(client, auth_headers, session):
    project_id = IDS["project"]
    milestone_id = client.milestone_id

    response = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    project = session.get(Project, project_id)
    assert project is not None
    assert project.status == ProjectStatus.in_progress

    detail = client.get(
        f"/api/v1/projects/{project_id}/detail",
        headers=auth_headers,
    ).json()
    assert detail["milestone_summary"]["progress_percent"] == "14.29"
    assert detail["health"] in {"green", "yellow", "red"}


def test_scenario_2_dashboard_and_reports_update(client, auth_headers):
    milestone_id = client.milestone_id
    before = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()

    client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert summary["in_progress_projects"] >= before["in_progress_projects"]

    reports = client.get("/api/v1/reports/project-hours", headers=auth_headers).json()
    assert len(reports) >= 1


def test_scenario_4_dashboard_red_projects_increase(client, auth_headers, session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    before = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()

    project.due_date = date.today() - timedelta(days=1)
    session.commit()
    recalculate_project(session, project.id)

    after = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert after["red_projects"] >= before["red_projects"]


def test_scenario_6_timesheet_updates_hours(client, auth_headers):
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

    client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet["id"],
            "project_id": project_id,
            "entry_date": "2026-06-17",
            "hours": 10,
        },
        headers=auth_headers,
    )

    detail = client.get(
        f"/api/v1/projects/{project_id}/detail",
        headers=auth_headers,
    ).json()
    assert Decimal(str(detail["hours"]["actual"])) == Decimal("10")
    assert Decimal(str(detail["hours"]["remaining"])) == Decimal("110.00")
    assert Decimal(str(detail["hours"]["variance"])) == Decimal("-110.00")

    dashboard = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    assert Decimal(str(dashboard["total_actual_hours"])) >= Decimal("10")


def test_scenario_7_delete_milestone_recalculates_progress(client, auth_headers, session):
    project_id = IDS["project"]
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_id)
    ).all()
    extra = Milestone(
        project_id=project_id,
        name="Extra Milestone",
        status=MilestoneStatus.not_started,
        sort_order=99,
    )
    session.add(extra)
    session.commit()
    session.refresh(extra)

    recalculate_project(session, project_id)
    total_before = session.scalar(
        select(func.count()).select_from(Milestone).where(Milestone.project_id == project_id)
    )

    response = client.delete(f"/api/v1/milestones/{extra.id}", headers=auth_headers)
    assert response.status_code == 204

    total_after = session.scalar(
        select(func.count()).select_from(Milestone).where(Milestone.project_id == project_id)
    )
    assert total_after == total_before - 1

    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.total_milestones == total_after


def test_scenario_8_delete_timesheet_recalculates_hours(client, auth_headers):
    project_id = client.project_id

    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": str(client.user_id),
            "week_start": "2026-06-23",
            "status": "draft",
        },
        headers=auth_headers,
    ).json()

    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet["id"],
            "project_id": project_id,
            "entry_date": "2026-06-24",
            "hours": 5,
        },
        headers=auth_headers,
    ).json()

    client.delete(f"/api/v1/timesheet-entries/{entry['id']}", headers=auth_headers)

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert Decimal(str(project["actual_hours"])) == Decimal("0")


def test_dashboard_summary_includes_health_counts(client, auth_headers):
    response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "total_remaining_hours" in body
    assert body["green_projects"] >= 0
    assert body["yellow_projects"] >= 0
    assert body["red_projects"] >= 0
    assert (
        body["green_projects"] + body["yellow_projects"] + body["red_projects"]
        == body["total_projects"]
    )
