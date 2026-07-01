import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth
from app.models.models import Milestone, Project
from app.services.project_calculation_service import (
    calculate_hours,
    calculate_progress,
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
    assert project.execution_status == ExecutionStatus.currently_being_worked_on
    assert project.health == ProjectHealth.green


def test_scenario_2_complete_one_milestone(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 1)
    recalculate_project(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.progress_percent == Decimal("14.29")
    assert project is not None
    assert project.execution_status == ExecutionStatus.currently_being_worked_on


def test_scenario_3_complete_all_milestones(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 7)
    recalculate_project(session, project_id)

    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.progress_percent == Decimal("100.00")
    assert project is not None
    assert project.execution_status == ExecutionStatus.currently_being_worked_on


def test_scenario_4_due_date_in_past_health_red(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() - timedelta(days=1)
    project.execution_status = ExecutionStatus.currently_being_worked_on
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.red


def test_scenario_5_due_date_within_five_days_health_yellow(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() + timedelta(days=3)
    project.execution_status = ExecutionStatus.currently_being_worked_on
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.yellow


def test_scenario_6_completed_execution_status_health_green(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.due_date = date.today() - timedelta(days=10)
    project.execution_status = ExecutionStatus.completed
    recalculate_project(session, project.id)

    assert project.health == ProjectHealth.green


def test_recalculate_updates_actual_hours(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    recalculate_project(session, project.id)
    hours = calculate_hours(session, project)
    assert project.actual_hours == hours.actual


def test_milestone_progress_counts(session):
    project_id = IDS["project"]
    _complete_n_milestones(session, project_id, 2)
    project = session.get(Project, project_id)
    progress = calculate_progress(session, project)
    assert progress.completed_milestones == 2
    assert progress.remaining_milestones == 5
    assert progress.total_milestones == 7


def test_execution_status_not_auto_changed_by_recalculate(session):
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.execution_status = ExecutionStatus.on_hold
    session.commit()
    _complete_n_milestones(session, project.id, 7)
    recalculate_project(session, project.id)
    assert project.execution_status == ExecutionStatus.on_hold
