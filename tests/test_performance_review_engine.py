"""Phase 1 performance review engine — templates, workflow, dashboard, permissions."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.access_control import MODULE_PERFORMANCE
from app.core.module_actions import (
    MODULE_ACTION_MANAGE_TEMPLATES,
    MODULE_ACTION_OPEN_CYCLES,
    MODULE_ACTION_VIEW,
    default_module_actions_for_role,
)
from app.models.enums import TeamRelationshipType
from app.models.models import PerformanceReviewSheet, PerformanceReviewTemplate, Team, TeamMember
from app.services.review_engine_service import (
    STAGE_ACKNOWLEDGED,
    STAGE_FINAL,
    STAGE_MANAGER,
    STAGE_SELF,
    ensure_default_annual_template,
    ensure_default_quarterly_template,
)
from tests.conftest import IDS, login


def _seed_team(session, *, lead_id, member_id, name: str) -> Team:
    team = Team(
        id=uuid.uuid4(),
        name=name,
        is_active=True,
        team_lead_id=lead_id,
    )
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=member_id,
            is_primary=True,
            relationship_type=TeamRelationshipType.member,
        )
    )
    session.commit()
    return team


def test_phase45_seeds_annual_template(session):
    ensure_default_annual_template(session)
    ensure_default_quarterly_template(session)
    session.commit()
    annual = session.scalar(
        select(PerformanceReviewTemplate).where(
            PerformanceReviewTemplate.code == "PP-HRD-FO-20",
            PerformanceReviewTemplate.version == 1,
        )
    )
    quarterly = session.scalar(
        select(PerformanceReviewTemplate).where(
            PerformanceReviewTemplate.code == "PP-HRD-Q-01",
            PerformanceReviewTemplate.version == 1,
        )
    )
    assert annual is not None and annual.kind == "annual"
    assert quarterly is not None and quarterly.kind == "quarterly"


def test_review_create_attaches_template_and_stage(client, session):
    team = _seed_team(
        session,
        lead_id=IDS["user_anurag"],
        member_id=IDS["user_binil"],
        name="Engine Create Team",
    )
    headers = login(client, "anurag@prosohm.com")
    created = client.post(
        "/api/v1/hr/reviews",
        headers=headers,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "FY Engine 2026",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["template_id"] is not None
    assert body["stage"] == STAGE_SELF
    assert body["can_submit_self"] is False  # viewer is manager, not employee

    sheet = session.get(PerformanceReviewSheet, uuid.UUID(body["id"]))
    assert sheet is not None
    assert sheet.template_id is not None
    assert sheet.stage == STAGE_SELF


def test_review_workflow_self_manager_acknowledge(client, session):
    team = _seed_team(
        session,
        lead_id=IDS["user_anurag"],
        member_id=IDS["user_binil"],
        name="Workflow Team",
    )
    leader = login(client, "anurag@prosohm.com")
    employee = login(client, "binil@prosohm.com")

    created = client.post(
        "/api/v1/hr/reviews",
        headers=leader,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "Q Workflow",
        },
    )
    assert created.status_code == 200, created.text
    review_id = created.json()["id"]

    self_submit = client.post(
        f"/api/v1/hr/reviews/{review_id}/workflow",
        headers=employee,
        json={"action": "submit-self"},
    )
    assert self_submit.status_code == 200, self_submit.text
    assert self_submit.json()["stage"] == STAGE_MANAGER

    mgr_submit = client.post(
        f"/api/v1/hr/reviews/{review_id}/workflow",
        headers=leader,
        json={"action": "submit-manager", "skip_calibration": True},
    )
    assert mgr_submit.status_code == 200, mgr_submit.text
    assert mgr_submit.json()["stage"] == STAGE_FINAL

    ack = client.post(
        f"/api/v1/hr/reviews/{review_id}/workflow",
        headers=employee,
        json={"action": "acknowledge", "acknowledgement_signature": "Binil Designer"},
    )
    assert ack.status_code == 200, ack.text
    body = ack.json()
    assert body["stage"] == STAGE_ACKNOWLEDGED
    assert body["status"] == "acknowledged"
    assert body["acknowledgement_signature"] == "Binil Designer"


def test_quarterly_cycle_isolation(client, session):
    admin = login(client, "admin@prosohm.com")
    templates = client.get("/api/v1/hr/performance/templates", headers=admin)
    assert templates.status_code == 200, templates.text
    kinds = {row["kind"] for row in templates.json()}
    assert "annual" in kinds
    assert "quarterly" in kinds

    cycle = client.post(
        "/api/v1/hr/review-cycles",
        headers=admin,
        json={
            "title": "Q3 2026 Check-in",
            "review_year": 2026,
            "kind": "quarterly",
            "calibration_required": False,
            "status": "draft",
        },
    )
    assert cycle.status_code == 200, cycle.text
    assert cycle.json()["kind"] == "quarterly"
    cycle_id = cycle.json()["id"]

    opened = client.post(f"/api/v1/hr/review-cycles/{cycle_id}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "open"

    closed = client.post(f"/api/v1/hr/review-cycles/{cycle_id}/close", headers=admin)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"


def test_performance_dashboard_endpoint(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/hr/performance/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employee"]["id"] == str(IDS["user_binil"])
    assert "skills" in body
    assert "open_reviews" in body
    assert "utilization" in body


def test_performance_module_actions_defaults():
    designer = default_module_actions_for_role("Designer", [MODULE_PERFORMANCE])
    assert designer[MODULE_PERFORMANCE] == [MODULE_ACTION_VIEW]

    hr = default_module_actions_for_role("HR", [MODULE_PERFORMANCE])
    assert MODULE_ACTION_VIEW in hr[MODULE_PERFORMANCE]
    assert MODULE_ACTION_MANAGE_TEMPLATES in hr[MODULE_PERFORMANCE]
    assert MODULE_ACTION_OPEN_CYCLES in hr[MODULE_PERFORMANCE]

    em = default_module_actions_for_role("Engineering Manager", [MODULE_PERFORMANCE])
    assert MODULE_ACTION_OPEN_CYCLES in em[MODULE_PERFORMANCE]
    assert MODULE_ACTION_MANAGE_TEMPLATES not in em[MODULE_PERFORMANCE]
