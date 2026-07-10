"""Dashboard KPI counts and hours must match live-project semantics."""

from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import select

from app.models.enums import ExecutionStatus
from app.models.models import Project
from tests.conftest import IDS, list_items


def _create_project(
    session,
    *,
    tool_number: str,
    quoted_hours: Decimal,
    actual_hours: Decimal,
    execution_status: ExecutionStatus,
    due_date: date | None = None,
) -> Project:
    project = Project(
        id=uuid.uuid4(),
        tool_number=tool_number,
        part_description=f"Part {tool_number}",
        customer_id=IDS["customer"],
        customer_contact_id=IDS["contact"],
        design_leader_id=IDS["user_anurag"],
        designer_id=IDS["user_binil"],
        stream_id=IDS["stream"],
        code=f"KPI-{tool_number}",
        quoted_hours=quoted_hours,
        actual_hours=actual_hours,
        due_date=due_date,
        execution_status=execution_status,
    )
    session.add(project)
    session.commit()
    return project


def test_dashboard_active_projects_include_planning(client, auth_headers, test_session_factory):
    session = test_session_factory()
    _create_project(
        session,
        tool_number="PLAN-1",
        quoted_hours=Decimal("50.00"),
        actual_hours=Decimal("10.00"),
        execution_status=ExecutionStatus.planning,
    )
    session.close()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    projects = list_items(client.get("/api/v1/projects", headers=auth_headers))

    live_projects = [
        project
        for project in projects
        if not project["is_deleted"]
        and not project["is_archived"]
        and project["execution_status"] not in ("completed", "cancelled")
    ]

    assert summary["active_projects"] == len(live_projects)
    assert summary["active_projects"] >= 2


def test_dashboard_hours_sum_live_projects_only(client, auth_headers, test_session_factory):
    session = test_session_factory()
    _create_project(
        session,
        tool_number="LIVE-1",
        quoted_hours=Decimal("100.00"),
        actual_hours=Decimal("40.00"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    _create_project(
        session,
        tool_number="CANC-1",
        quoted_hours=Decimal("500.00"),
        actual_hours=Decimal("200.00"),
        execution_status=ExecutionStatus.cancelled,
    )
    session.close()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    projects = list_items(client.get("/api/v1/projects", headers=auth_headers))

    live_projects = [
        project
        for project in projects
        if not project["is_deleted"]
        and not project["is_archived"]
        and project["execution_status"] not in ("completed", "cancelled")
    ]
    expected_quoted = sum(Decimal(str(project["quoted_hours"] or 0)) for project in live_projects)
    expected_actual = sum(Decimal(str(project["actual_hours"] or 0)) for project in live_projects)

    assert Decimal(str(summary["total_quoted_hours_active"])) == expected_quoted
    assert Decimal(str(summary["total_actual_hours_productive"])) == expected_actual


def test_dashboard_due_this_week_uses_calendar_week(client, auth_headers, test_session_factory):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    session = test_session_factory()
    _create_project(
        session,
        tool_number="WEEK-1",
        quoted_hours=Decimal("25.00"),
        actual_hours=Decimal("5.00"),
        execution_status=ExecutionStatus.currently_being_worked_on,
        due_date=week_start,
    )
    _create_project(
        session,
        tool_number="NEXT-1",
        quoted_hours=Decimal("25.00"),
        actual_hours=Decimal("5.00"),
        execution_status=ExecutionStatus.currently_being_worked_on,
        due_date=week_end + timedelta(days=3),
    )
    session.close()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    projects = list_items(client.get("/api/v1/projects", headers=auth_headers))

    expected = sum(
        1
        for project in projects
        if not project["is_deleted"]
        and not project["is_archived"]
        and project["execution_status"] not in ("completed", "cancelled")
        and project["due_date"]
        and week_start <= date.fromisoformat(project["due_date"]) <= week_end
    )

    assert summary["projects_due_this_week"] == expected
    assert summary["projects_due_this_week"] >= 1
