"""Tests for global project timesheet entry and contributor tracking."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.crud.timesheet_projects import list_timesheet_projects
from app.db.phase16_timesheet_contribution_schema_sync import ensure_phase16_timesheet_contribution_foundation
from app.models.enums import ExecutionStatus
from app.models.models import Project, TimesheetEntry
from app.services.project_contributor_service import get_project_contributors


@pytest.fixture()
def contribution_schema(test_engine):
    ensure_phase16_timesheet_contribution_foundation(test_engine)


def test_timesheet_projects_lists_all_active_loggable_projects(session, contribution_schema):
    expected_count = session.scalar(
        select(func.count())
        .select_from(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(
                (
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            ),
        )
    )
    projects = list_timesheet_projects(session)
    assert len(projects) == int(expected_count or 0)
    if projects:
        sample = projects[0]
        assert sample.tool_number
        assert sample.part_description is not None


def test_get_project_contributors_from_existing_entries(session, contribution_schema):
    row = session.execute(
        select(TimesheetEntry.project_id, func.sum(TimesheetEntry.hours))
        .where(
            TimesheetEntry.project_id.is_not(None),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.project_id)
        .order_by(func.sum(TimesheetEntry.hours).desc())
        .limit(1)
    ).first()
    if row is None:
        pytest.skip("No productive timesheet entries in seed data")

    project_id, total_hours = row
    contributors = get_project_contributors(session, project_id)
    assert contributors
    assert sum((item.total_hours for item in contributors), Decimal("0")) == Decimal(str(total_hours))
