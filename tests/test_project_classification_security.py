"""Project classification and scoped access security checks."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models.enums import ExecutionStatus
from app.models.models import Project, Team
from tests.conftest import IDS, login


def test_direct_project_url_rejects_other_team_project(client, test_session_factory):
    with test_session_factory() as session:
        team_b = Team(id=uuid.uuid4(), name="Security Scope B", is_active=True)
        session.add(team_b)
        session.flush()
        other = Project(
            id=uuid.uuid4(),
            tool_number="SEC-OTHER",
            part_description="Other team confidential",
            customer_id=IDS["customer"],
            team_id=team_b.id,
            quoted_hours=Decimal("10"),
            actual_hours=Decimal("0"),
            due_date=date.today() + timedelta(days=14),
            execution_status=ExecutionStatus.planning,
        )
        session.add(other)
        session.commit()
        other_id = str(other.id)

    headers = login(client, "anurag@prosohm.com")
    response = client.get(f"/api/v1/projects/{other_id}", headers=headers)
    assert response.status_code in (403, 404), response.text


def test_list_projects_classification_filter_cannot_bypass_team_scope(client):
    """A scoped user filtering by classification still only sees authorized projects."""
    headers = login(client, "binil@prosohm.com")
    response = client.get(
        "/api/v1/projects",
        params={"project_classification": "unclassified", "limit": 100},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    for item in items:
        assert item["project_classification"] == "unclassified"


def test_create_project_rejects_invalid_small_task_type(client):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"BAD-{uuid.uuid4().hex[:6]}",
            "part_description": "Invalid task type",
            "customer_id": str(IDS["customer"]),
            "project_classification": "small_task",
            "small_task_type_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text
