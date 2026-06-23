import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.enums import MilestoneStatus, ProjectHealth, ProjectStatus
from app.models.models import Milestone, Project
from app.services.project_calculation_service import (
    calculate_project_health,
    calculate_progress_percent,
    recalculate_project_progress,
)
from tests.conftest import IDS


def _complete_n_milestones(session, project_id, count: int) -> None:
    project_uuid = project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    milestones = session.scalars(
        select(Milestone)
        .where(Milestone.project_id == project_uuid)
        .order_by(Milestone.sort_order)
    ).all()
    for milestone in milestones[:count]:
        milestone.status = MilestoneStatus.completed
    session.commit()


def test_progress_zero_completed_status_not_started(session):
    project_id = IDS["project"]
    recalculate_project_progress(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress_percent(session, project_id)

    assert progress == Decimal("0.00")
    assert project is not None
    assert project.status == ProjectStatus.not_started


def test_progress_one_completed_status_in_progress(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 1)
    recalculate_project_progress(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress_percent(session, project_id)

    assert progress == Decimal("14.29")
    assert project is not None
    assert project.status == ProjectStatus.in_progress


def test_progress_all_completed_status_completed(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 7)
    recalculate_project_progress(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress_percent(session, project_id)

    assert progress == Decimal("100.00")
    assert project is not None
    assert project.status == ProjectStatus.completed


def test_health_red_when_due_date_in_past(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() - timedelta(days=1)
    project.status = ProjectStatus.in_progress
    session.commit()
    session.refresh(project)

    assert calculate_project_health(project) == ProjectHealth.red


def test_health_yellow_when_due_date_within_five_days(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=3)
    project.status = ProjectStatus.in_progress
    session.commit()
    session.refresh(project)

    assert calculate_project_health(project) == ProjectHealth.yellow


def test_health_green_when_due_date_more_than_five_days_away(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=10)
    project.status = ProjectStatus.in_progress
    session.commit()
    session.refresh(project)

    assert calculate_project_health(project) == ProjectHealth.green


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


def test_dashboard_summary_includes_health_counts(client, auth_headers):
    response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["green_projects"] >= 0
    assert body["yellow_projects"] >= 0
    assert body["red_projects"] >= 0
    assert (
        body["green_projects"] + body["yellow_projects"] + body["red_projects"]
        == body["total_projects"]
    )
