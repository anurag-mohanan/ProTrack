"""Phase 2: Engineering Control Tower — rules, finding lifecycle, API, permissions, regression."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import event, func, select

from app.models.control_tower import (
    ProjectRiskEvaluationRun,
    ProjectRiskFinding,
    ProjectRiskFindingEvent,
)
from app.models.enums import (
    ExecutionStatus,
    MilestoneStatus,
    ProjectStage,
    WorkingModelCode,
)
from app.models.models import (
    Milestone,
    Project,
    ProjectBaselineRevision,
    ProjectStageEstimate,
    User,
    WorkingModel,
)
from app.services import control_tower_service as ct
from tests.conftest import IDS, login
from tests.test_engineering_metrics import _book, _project
from tests.test_stage_delivery_metrics import _estimate, _milestone, _staged

URL = "/api/v1/control-tower"
PRE = ProjectStage.preliminary
TODAY = date.today()


def _evaluate(session, today: date = TODAY) -> ProjectRiskEvaluationRun:
    session.expire_all()
    return ct.run_evaluation(session, trigger="manual", today=today)


def _findings(session, project_id, *, rule: str | None = None, status: str | None = None) -> list[ProjectRiskFinding]:
    session.expire_all()
    stmt = select(ProjectRiskFinding).where(ProjectRiskFinding.project_id == project_id)
    if rule:
        stmt = stmt.where(ProjectRiskFinding.rule_id == rule)
    if status:
        stmt = stmt.where(ProjectRiskFinding.status == status)
    return list(session.scalars(stmt.order_by(ProjectRiskFinding.first_detected_at)))


def _open_rules(session, project_id) -> set[str]:
    return {
        f.rule_id for f in _findings(session, project_id) if f.status in ("active", "not_assessable")
    }


def _evidence(finding: ProjectRiskFinding) -> dict[str, str]:
    return {line["label"]: line["value"] for line in json.loads(finding.evidence_json)}


def _get(client, headers=None, expect: int = 200, **params):
    response = client.get(URL, params={"page_size": 100, **params}, headers=headers or client.auth_headers)
    assert response.status_code == expect, response.text
    return response.json()


# ----------------------------------------------------------------- A: overdue milestones


def test_overdue_milestone_rules(session):
    project = _project(session, code="CT-MS")
    late = _milestone(session, project.id, "Late step", PRE, 1, due_date=TODAY - timedelta(days=3),
                      assigned_user_id=IDS["user_binil"])
    optional = _milestone(session, project.id, "Optional step", PRE, 2, due_date=TODAY - timedelta(days=1),
                          is_required=False)
    _milestone(session, project.id, "Due today", PRE, 3, due_date=TODAY)
    _milestone(session, project.id, "Future step", PRE, 4, due_date=TODAY + timedelta(days=5))
    _milestone(session, project.id, "Done late", PRE, 5, due_date=TODAY - timedelta(days=9),
               status=MilestoneStatus.completed, completed_date=TODAY - timedelta(days=2))
    _milestone(session, project.id, "Cancelled", PRE, 6, due_date=TODAY - timedelta(days=9),
               status=MilestoneStatus.cancelled)
    _milestone(session, project.id, "Not applicable", PRE, 7, due_date=TODAY - timedelta(days=9),
               status=MilestoneStatus.not_applicable)
    baseline_only = _milestone(session, project.id, "Baseline only", PRE, 8,
                               baseline_finish_date=TODAY - timedelta(days=4))
    _milestone(session, project.id, "Undated", PRE, 9)
    session.commit()

    _evaluate(session)
    overdue = {f.milestone_id: f for f in _findings(session, project.id, rule="milestone_overdue")}
    assert set(overdue) == {late.id, optional.id, baseline_only.id}
    finding = overdue[late.id]
    assert (finding.severity, finding.category, finding.status) == ("high", "schedule", "active")
    assert overdue[optional.id].severity == "medium"
    evidence = _evidence(finding)
    assert evidence["Days past target"] == "3"
    assert evidence["Current target"].startswith((TODAY - timedelta(days=3)).isoformat())
    assert evidence["Original baseline finish"] == "Not recorded"
    assert (finding.owner_user_id, finding.owner_basis) == (IDS["user_binil"], "milestone_assignee")
    assert overdue[optional.id].owner_basis == "design_leader"  # no assignee: project design leader
    assert "Baseline finish" in _evidence(overdue[baseline_only.id])["Current target"]
    assert finding.recommended_action and finding.explanation

    missing = _findings(session, project.id, rule="dq_milestone_target_missing")
    assert len(missing) == 1 and missing[0].severity == "info" and missing[0].category == "data_quality"
    assert "Undated" in _evidence(missing[0])["Milestones"]


def test_cancelled_and_completed_projects_are_not_evaluated(session):
    cancelled = _project(session, code="CT-CANCEL", status=ExecutionStatus.cancelled)
    completed = _project(session, code="CT-DONE", status=ExecutionStatus.completed,
                         completed_at=datetime(2025, 5, 1, 9))
    on_hold = _project(session, code="CT-HOLD", status=ExecutionStatus.on_hold)
    for project in (cancelled, completed, on_hold):
        project.due_date = TODAY - timedelta(days=10)
        _milestone(session, project.id, "Open step", PRE, 1, due_date=TODAY - timedelta(days=5))
    session.commit()
    _evaluate(session)
    assert _findings(session, cancelled.id) == [] and _findings(session, completed.id) == []
    assert {"milestone_overdue", "project_past_target"} <= _open_rules(session, on_hold.id)


# ----------------------------------------------------------------- B: estimate overrun


def test_realized_overrun_uses_approved_estimate_and_never_changes_it(session):
    over = _project(session, quoted="5", code="CT-OVER")
    _staged(session, over, {PRE: "10"}, {PRE: "12"})
    exact = _project(session, code="CT-EXACT")
    _staged(session, exact, {PRE: "10"}, {PRE: "10"})
    under = _project(session, code="CT-UNDER")
    _staged(session, under, {PRE: "10"}, {PRE: "8"})
    quoted_only = _project(session, quoted="5", code="CT-QUOTED")
    _book(session, quoted_only.id, "30")
    session.commit()

    _evaluate(session)
    finding = _findings(session, over.id, rule="estimate_overrun_realized")
    assert len(finding) == 1
    f = finding[0]
    assert (f.severity, f.category, f.status) == ("high", "effort", "active")
    evidence = _evidence(f)
    assert evidence["Approved estimate"].startswith("10.00 h")
    assert evidence["Actual hours"] == "12.00 h" and evidence["Over estimate by"] == "2.00 h"
    assert "Approved timesheet hours" in evidence and "On rejected timesheets" in evidence
    assert '"basis": "realized"' in f.metrics_json
    assert _findings(session, exact.id, rule="estimate_overrun_realized") == []  # strictly greater
    assert _findings(session, under.id, rule="estimate_overrun_realized") == []
    # Quoted hours alone are not an approved estimate: data quality, not an overrun.
    assert _findings(session, quoted_only.id, rule="estimate_overrun_realized") == []
    assert len(_findings(session, quoted_only.id, rule="dq_approved_estimate_missing")) == 1

    session.expire_all()
    estimate = session.scalar(select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == over.id))
    assert estimate.current_hours == Decimal("10") and estimate.original_hours == Decimal("10")
    assert session.get(Project, over.id).quoted_hours == Decimal("5")


def test_overrun_respects_working_model(session):
    model = WorkingModel(id=uuid.uuid4(), code=f"wm_{uuid.uuid4().hex[:8]}",
                         strategy_key=WorkingModelCode.retainer, name="Retainer CT", is_active=True)
    session.add(model)
    retainer = _project(session, code="CT-RETAINER")
    retainer.working_model_id = model.id
    _staged(session, retainer, {PRE: "10"}, {PRE: "20"})
    session.commit()
    _evaluate(session)
    rules = _open_rules(session, retainer.id)
    assert "estimate_overrun_realized" not in rules and "dq_approved_estimate_missing" not in rules


# ----------------------------------------------------------------- C: delivery risk


def test_project_past_target_shows_current_and_original_separately(session):
    late = _project(session, code="CT-LATE")
    original = TODAY - timedelta(days=20)
    late.baseline_completion_date = TODAY - timedelta(days=2)
    late.due_date = TODAY - timedelta(days=2)
    session.add(ProjectBaselineRevision(
        project_id=late.id, revision_number=1, previous_completion_date=None,
        new_completion_date=original, reason="initial approval", revised_at=datetime(2025, 3, 1),
    ))
    session.add(ProjectBaselineRevision(
        project_id=late.id, revision_number=2, previous_completion_date=original,
        new_completion_date=late.due_date, reason="customer change", revised_at=datetime(2025, 4, 1),
    ))
    fine = _project(session, code="CT-FINE")
    no_target = _project(session, code="CT-NOTARGET")
    no_target.due_date = None
    session.commit()

    _evaluate(session)
    finding = _findings(session, late.id, rule="project_past_target")
    assert len(finding) == 1 and finding[0].severity == "critical" and finding[0].category == "delivery"
    evidence = _evidence(finding[0])
    assert evidence["Current target"].startswith(late.due_date.isoformat())
    assert evidence["Original baseline"] == original.isoformat()
    assert evidence["Target moved since original"] == "18 day(s)"
    assert evidence["Days past target"] == "2"
    assert finding[0].owner_user_id == IDS["user_anurag"] and finding[0].owner_basis == "design_leader"
    assert "dq_original_baseline_unavailable" not in _open_rules(session, late.id)

    assert "project_past_target" not in _open_rules(session, fine.id)
    assert "dq_original_baseline_unavailable" in _open_rules(session, fine.id)
    assert _open_rules(session, no_target.id) >= {"dq_project_target_missing"}
    assert "project_past_target" not in _open_rules(session, no_target.id)

    session.expire_all()
    stored = session.get(Project, late.id)
    assert stored.due_date == TODAY - timedelta(days=2)  # dates are never changed
    assert stored.baseline_completion_date == TODAY - timedelta(days=2)


# ----------------------------------------------------------------- D: finding lifecycle


def test_lifecycle_no_duplicates_update_resolve_and_recur(session):
    project = _project(session, code="CT-LIFE")
    step = _milestone(session, project.id, "Step", PRE, 1, due_date=TODAY - timedelta(days=1))
    session.commit()

    first_run = _evaluate(session)
    [finding] = _findings(session, project.id, rule="milestone_overdue")
    first_id, first_seen = finding.id, finding.first_detected_at
    assert first_run.findings_opened >= 1 and first_run.status == "succeeded"

    _evaluate(session, today=TODAY + timedelta(days=2))  # evidence changes, same episode
    [again] = _findings(session, project.id, rule="milestone_overdue")
    assert again.id == first_id and again.first_detected_at == first_seen
    assert _evidence(again)["Days past target"] == "3"
    assert again.evaluation_date == TODAY + timedelta(days=2)

    session.get(Milestone, step.id).status = MilestoneStatus.completed
    session.get(Milestone, step.id).completed_date = TODAY
    session.commit()
    _evaluate(session)
    [resolved] = _findings(session, project.id, rule="milestone_overdue")
    assert resolved.status == "resolved" and resolved.resolved_at is not None
    assert resolved.resolution_note == "Condition no longer met."

    session.get(Milestone, step.id).status = MilestoneStatus.in_progress
    session.commit()
    _evaluate(session)
    episodes = _findings(session, project.id, rule="milestone_overdue")
    assert [e.status for e in episodes] == ["resolved", "active"]
    assert episodes[1].previous_episode_id == first_id
    events = [
        e.event for e in session.scalars(
            select(ProjectRiskFindingEvent).where(ProjectRiskFindingEvent.finding_id == episodes[1].id)
        )
    ]
    assert events == ["reopened"]


def test_missing_inputs_make_a_finding_not_assessable_instead_of_resolved(session):
    project = _project(session, code="CT-NA")
    step = _milestone(session, project.id, "Step", PRE, 1, due_date=TODAY - timedelta(days=1))
    session.commit()
    _evaluate(session)
    [finding] = _findings(session, project.id, rule="milestone_overdue")

    session.get(Milestone, step.id).due_date = None
    session.commit()
    _evaluate(session)
    [same] = _findings(session, project.id, rule="milestone_overdue")
    assert same.id == finding.id and same.status == "not_assessable"
    assert "no due date" in same.not_assessable_reason
    assert "dq_milestone_target_missing" in _open_rules(session, project.id)

    session.get(Milestone, step.id).due_date = TODAY - timedelta(days=1)
    session.commit()
    _evaluate(session)
    [back] = _findings(session, project.id, rule="milestone_overdue")
    assert back.id == finding.id and back.status == "active" and back.not_assessable_reason is None
    assert "dq_milestone_target_missing" not in _open_rules(session, project.id)


def test_findings_resolve_when_project_closes(session):
    project = _project(session, code="CT-CLOSE")
    project.due_date = TODAY - timedelta(days=1)
    session.commit()
    _evaluate(session)
    assert "project_past_target" in _open_rules(session, project.id)
    stored = session.get(Project, project.id)
    stored.execution_status = ExecutionStatus.completed
    stored.completed_at = datetime.now()
    session.commit()
    _evaluate(session)
    findings = _findings(session, project.id)
    assert findings and all(f.status == "resolved" for f in findings)
    assert all("no longer open" in f.resolution_note for f in findings)


def test_failed_evaluation_keeps_findings_and_is_never_shown_as_clean(client, session, monkeypatch):
    initial = _get(client)
    assert initial["state"] == "never_evaluated" and initial["findings"] == []
    assert "not because there are no risks" in initial["state_message"]

    project = _project(session, code="CT-FAIL")
    project.due_date = TODAY - timedelta(days=1)
    session.commit()
    _evaluate(session)
    before = {f.id: f.status for f in _findings(session, project.id)}

    def boom(*_args, **_kwargs):
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(ct, "detect_all", boom)
    response = client.post(f"{URL}/evaluate", headers=client.auth_headers)
    assert response.status_code == 500
    assert {f.id: f.status for f in _findings(session, project.id)} == before

    body = _get(client, project_id=str(project.id))
    assert body["state"] == "last_run_failed"
    assert body["latest_run"]["status"] == "failed" and "metrics unavailable" in body["latest_run"]["error"]
    assert body["last_successful_run"]["status"] == "succeeded"
    assert body["total"] >= 1  # previous findings still shown, flagged as possibly out of date


def test_concurrent_evaluation_is_refused(client, session):
    session.add(ProjectRiskEvaluationRun(
        status="running", trigger="manual", evaluation_date=TODAY, rules_version="1",
        started_at=ct._now(),
    ))
    session.commit()
    response = client.post(f"{URL}/evaluate", headers=client.auth_headers)
    assert response.status_code == 409
    assert _get(client)["state"] == "running"


def test_acknowledgement_is_recorded_and_audited(client, session):
    project = _project(session, code="CT-ACK")
    project.due_date = TODAY - timedelta(days=1)
    session.commit()
    run = client.post(f"{URL}/evaluate", headers=client.auth_headers)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "succeeded"
    [finding] = _findings(session, project.id, rule="project_past_target")

    ack = client.post(f"{URL}/findings/{finding.id}/acknowledge", json={"note": "Customer informed"},
                      headers=client.auth_headers)
    assert ack.status_code == 200, ack.text
    body = ack.json()
    assert body["acknowledged_by_name"] and body["acknowledgement_note"] == "Customer informed"
    assert [e["event"] for e in body["events"]] == ["opened", "acknowledged"]
    assert body["status"] == "active"  # acknowledging never resolves
    again = client.post(f"{URL}/findings/{finding.id}/acknowledge", json={}, headers=client.auth_headers)
    assert again.status_code == 409

    stored = session.get(Project, project.id)
    stored.due_date = TODAY + timedelta(days=5)
    session.commit()
    _evaluate(session)
    resolved = client.post(f"{URL}/findings/{finding.id}/acknowledge", json={}, headers=client.auth_headers)
    assert resolved.status_code == 409


# ----------------------------------------------------------------- E: API, filters, permissions


def _seed_api(session):
    project = _project(session, code="CT-API")
    project.due_date = TODAY - timedelta(days=1)
    _milestone(session, project.id, "Late A", PRE, 1, due_date=TODAY - timedelta(days=2))
    _milestone(session, project.id, "Late B", PRE, 2, due_date=TODAY - timedelta(days=3), is_required=False)
    _milestone(session, project.id, "Undated", PRE, 3)
    session.commit()
    return project


def test_api_views_filters_pagination_and_summary(client, session):
    project = _seed_api(session)
    assert client.post(f"{URL}/evaluate", headers=client.auth_headers).status_code == 200
    pid = str(project.id)
    risks = _get(client, project_id=pid)
    assert risks["state"] == "ok" and risks["can_evaluate"] is True
    assert {f["rule_id"] for f in risks["findings"]} == {"milestone_overdue", "project_past_target"}
    assert all(f["category"] != "data_quality" for f in risks["findings"])
    assert [f["severity"] for f in risks["findings"]] == ["critical", "high", "medium"]  # ordered by severity
    first = risks["findings"][0]
    assert first["project"]["code"] == "CT-API" and first["evidence"] and first["recommended_action"]
    milestone_rows = [f for f in risks["findings"] if f["milestone"]]
    assert {m["milestone"]["name"] for m in milestone_rows} == {"Late A", "Late B"}

    dq = _get(client, project_id=pid, view="data_quality")
    assert dq["findings"] and all(f["category"] == "data_quality" for f in dq["findings"])
    assert "dq_milestone_target_missing" in {f["rule_id"] for f in dq["findings"]}

    assert {f["severity"] for f in _get(client, project_id=pid, severity="high")["findings"]} == {"high"}
    assert {f["category"] for f in _get(client, project_id=pid, category="delivery")["findings"]} == {"delivery"}
    owner = _get(client, project_id=pid, owner_id=str(IDS["user_anurag"]))
    assert owner["total"] == 3
    assert _get(client, project_id=pid, owner_id="unassigned")["total"] == 0
    filtered = _get(client, project_id=pid, search="no-such-project")
    assert filtered["total"] == 0 and filtered["empty_message"] == "No findings match these filters."

    page = _get(client, project_id=pid, page_size=2)
    assert page["total"] == 3 and len(page["findings"]) == 2
    page2 = _get(client, project_id=pid, page_size=2, page=2)
    assert len(page2["findings"]) == 1

    summary = risks["summary"]
    assert summary["open_risks"] >= 3 and summary["projects_with_risks"] >= 1
    assert {row["severity"] for row in summary["by_severity"]} == {"critical", "high", "medium"}
    assert {row["category"] for row in summary["by_category"]} == {
        "schedule", "effort", "delivery", "data_quality", "capability", "resource",
    }
    assert summary["open_predictive"] == 0 and summary["dismissed"] == 0
    assert {r["rule_id"] for r in risks["deferred_rules"]} == {"stage_overrun"}
    assert {r["rule_id"] for r in risks["rules"] if r["kind"] == "predictive"} == {
        "estimate_overrun_forecast", "delivery_forecast_risk", "milestone_delay_forecast", "resource_bottleneck",
    }
    assert _get(client, view="resolved", status="active", expect=422)
    assert _get(client, owner_id="not-a-uuid", expect=422)


def test_get_never_writes(client, session):
    _seed_api(session)
    _get(client)
    _get(client, view="data_quality")
    session.expire_all()
    assert session.scalar(select(func.count(ProjectRiskEvaluationRun.id))) == 0
    assert session.scalar(select(func.count(ProjectRiskFinding.id))) == 0


def _scoped_user(session, *, modules: str, specials: str = "[]") -> None:
    designer = session.get(User, IDS["user_binil"])
    designer.module_access = modules
    designer.special_permissions = specials
    session.commit()


def test_permissions_in_api(client, session):
    mine = _project(session, code="CT-MINE")
    mine.due_date = TODAY - timedelta(days=1)
    hidden = _project(session, code="CT-HIDDEN")
    hidden.due_date = TODAY - timedelta(days=1)
    hidden.designer_id = IDS["user_ranjith"]
    hidden.design_leader_id = IDS["user_pm"]
    session.commit()
    _evaluate(session)
    [hidden_finding] = _findings(session, hidden.id, rule="project_past_target")

    _scoped_user(session, modules='["dashboard", "projects", "timesheets"]')
    headers = login(client, "binil@prosohm.com")
    assert client.get(URL, headers=headers).status_code == 403

    _scoped_user(session, modules='["dashboard", "projects", "timesheets", "reports"]')
    body = _get(client, headers=headers)
    codes = {f["project"]["code"] for f in body["findings"]}
    assert "CT-MINE" in codes and "CT-HIDDEN" not in codes
    assert body["can_evaluate"] is False and body["can_acknowledge"] is False
    assert _get(client, headers=headers, project_id=str(hidden.id))["total"] == 0
    assert "CT-HIDDEN" not in {o["label"] for o in body["project_options"]}
    assert client.get(f"{URL}/findings/{hidden_finding.id}", headers=headers).status_code == 404
    assert client.post(f"{URL}/evaluate", headers=headers).status_code == 403
    assert client.post(
        f"{URL}/findings/{hidden_finding.id}/acknowledge", json={}, headers=headers
    ).status_code == 403
    assert client.get(URL).status_code == 401


# ----------------------------------------------------------------- F: performance and regression


def test_evaluation_uses_a_constant_number_of_queries(session):
    def _seed(count: int, prefix: str):
        for index in range(count):
            project = _project(session, code=f"{prefix}-{index}")
            project.due_date = TODAY - timedelta(days=1)
            _milestone(session, project.id, "Late", PRE, 1, due_date=TODAY - timedelta(days=1))
            _estimate(session, project.id, PRE, "10")
        session.commit()

    engine = session.get_bind()

    def _count_detect() -> int:
        statements: list[str] = []

        def _count(conn, cursor, statement, *args):
            statements.append(statement)

        session.expire_all()
        event.listen(engine, "before_cursor_execute", _count)
        try:
            ct.detect_all(session, TODAY)
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        return len(statements)

    _seed(2, "CT-Q2")
    small = _count_detect()
    _seed(10, "CT-Q10")
    assert _count_detect() == small


def test_command_center_uses_shared_overdue_definitions(client, session):
    project = _project(session, code="CT-CC")
    _milestone(session, project.id, "Cancelled late", PRE, 1, due_date=TODAY - timedelta(days=4),
               status=MilestoneStatus.cancelled)
    _milestone(session, project.id, "Open late", PRE, 2, due_date=TODAY - timedelta(days=4))
    project.due_date = None
    project.baseline_completion_date = TODAY - timedelta(days=1)
    session.commit()
    response = client.get(f"/api/v1/projects/{project.id}/command-center", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    risks = response.json()["risks"]
    titles = [r["title"] for r in risks]
    assert "Delayed milestone: Open late" in titles
    assert "Delayed milestone: Cancelled late" not in titles
    assert any(r["risk_type"] == "overdue" for r in risks)  # baseline completion used when no due date

    _evaluate(session)
    assert {"milestone_overdue", "project_past_target"} <= _open_rules(session, project.id)
