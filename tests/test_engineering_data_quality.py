"""Engineering data-quality checks flag unreliable records without changing them."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.models.enums import ExecutionStatus, ProjectClassification, UserType
from app.models.models import Customer, Project, User
from tests.conftest import IDS, login
from tests.test_engineering_performance_report import _project


def _codes(payload: dict, code: str) -> set[str]:
    check = next(item for item in payload["checks"] if item["code"] == code)
    assert check["count"] >= len(check["items"])
    return {item["label"] for item in check["items"]}


def test_data_quality_flags_each_problem(client, session):
    today = date.today()
    completed = _project(session, code="DQ-DONE", status=ExecutionStatus.completed, completed_at=None)
    live = _project(
        session, code="DQ-LIVE", status=ExecutionStatus.currently_being_worked_on, completed_at=None
    )
    live.project_classification = ProjectClassification.full_design
    live.team_id = None
    backwards = _project(
        session,
        code="DQ-BACK",
        status=ExecutionStatus.planning,
        completed_at=None,
        due=today,
    )
    backwards.start_date = today + timedelta(days=5)
    virtual = session.get(User, IDS["user_binil"])
    virtual.user_type = UserType.virtual
    session.add_all(
        [
            Customer(id=uuid.uuid4(), name="Acme Tooling Ltd", code="ACM1", is_active=True),
            Customer(id=uuid.uuid4(), name="ACME tooling ltd.", code="ACM2", is_active=True),
        ]
    )
    session.commit()

    response = client.get("/api/v1/reports/engineering-data-quality", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_issues"] >= 6

    assert "DQ-DONE" in _codes(payload, "completed_without_date")
    assert "DQ-LIVE" in _codes(payload, "live_without_start_date")
    assert "DQ-LIVE" in _codes(payload, "full_design_without_stage_estimates")
    assert "DQ-LIVE" in _codes(payload, "live_without_team")
    assert "DQ-BACK" in _codes(payload, "due_before_start")
    assert "DQ-LIVE" in _codes(payload, "virtual_user_assigned")
    assert "DQ-DONE" not in _codes(payload, "live_without_start_date")
    duplicates = _codes(payload, "possible_duplicate_customers")
    assert any("Acme Tooling Ltd" in label and "ACME tooling ltd." in label for label in duplicates)

    session.expire_all()
    unchanged = session.get(Project, completed.id)
    assert unchanged.completed_at is None
    assert unchanged.execution_status == ExecutionStatus.completed


def test_data_quality_requires_report_access(client):
    designer = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/reports/engineering-data-quality", headers=designer)
    assert response.status_code == 403
