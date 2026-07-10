"""Portfolio metrics must match live project table totals."""

from app.models.enums import ExecutionStatus
from app.models.models import Project
from tests.conftest import IDS, list_items
import uuid
from decimal import Decimal


def _live_project(session, tool_number: str, quoted: str, actual: str, status):
    project = Project(
        id=uuid.uuid4(),
        tool_number=tool_number,
        part_description=f"Part {tool_number}",
        customer_id=IDS["customer"],
        customer_contact_id=IDS["contact"],
        design_leader_id=IDS["user_anurag"],
        designer_id=IDS["user_binil"],
        stream_id=IDS["stream"],
        code=f"MET-{tool_number}",
        quoted_hours=Decimal(quoted),
        actual_hours=Decimal(actual),
        execution_status=status,
    )
    session.add(project)
    return project


def test_dashboard_hours_match_live_projects(client, auth_headers, test_session_factory):
    session = test_session_factory()
    _live_project(session, "M1", "100.00", "40.00", ExecutionStatus.currently_being_worked_on)
    _live_project(session, "M2", "200.00", "60.00", ExecutionStatus.on_hold)
    _live_project(session, "M3", "50.00", "10.00", ExecutionStatus.planning)
    _live_project(
        session,
        "M4",
        "500.00",
        "200.00",
        ExecutionStatus.cancelled,
    )
    session.commit()
    session.close()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()
    projects = client.get("/api/v1/projects?lifecycle=active&limit=500", headers=auth_headers)
    items = list_items(projects)

    live = [
        project
        for project in items
        if not project["is_deleted"]
        and not project["is_archived"]
        and project["execution_status"] not in ("completed", "cancelled")
    ]
    expected_quoted = sum(float(project["quoted_hours"] or 0) for project in live)
    expected_actual = sum(float(project["actual_hours"] or 0) for project in live)

    assert summary["active_projects"] == len(live)
    assert float(summary["total_quoted_hours_active"]) == expected_quoted
    assert float(summary["total_actual_hours_productive"]) == expected_actual
