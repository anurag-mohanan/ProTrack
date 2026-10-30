"""Phase 5 workflow automation: opt-in rules, dedupe, failure/retry, review, audit, access."""

import dataclasses
import json
import uuid
from datetime import date, datetime

from sqlalchemy import func, select

from app.models.control_tower import ProjectRiskFinding
from app.models.enums import ActivityAction, MilestoneStatus, NotificationType, ProjectStage
from app.models.models import Activity, Milestone, Notification, Project, ProjectTemplate
from app.models.workflow import AutomationExecution, AutomationRule
from app.services.automation import engine, events
from app.services.scheduling_service import dump_id_list
from tests.conftest import IDS, login
from tests.test_template_reconciliation import _apply, _mold, _new_project, _preview, _template

SWEEP_DAY = date(2026, 7, 1)


def _enable(client, key: str, enabled: bool = True):
    response = client.patch(f"/api/v1/automation/rules/{key}", json={"is_enabled": enabled, "reason": "test"},
                            headers=client.auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


def _executions(session, rule_key: str | None = None) -> list[AutomationExecution]:
    session.expire_all()
    stmt = select(AutomationExecution).order_by(AutomationExecution.started_at)
    if rule_key:
        stmt = stmt.where(AutomationExecution.rule_key == rule_key)
    return list(session.scalars(stmt).all())


def _automation_notes(session, user_id=None) -> list[Notification]:
    session.expire_all()
    stmt = select(Notification).where(Notification.notification_type == NotificationType.workflow_automation)
    if user_id:
        stmt = stmt.where(Notification.user_id == user_id)
    return list(session.scalars(stmt).all())


def _seeded(session) -> list[Milestone]:
    session.expire_all()
    return list(session.scalars(
        select(Milestone).where(Milestone.project_id == IDS["project"]).order_by(Milestone.sort_order)
    ).all())


def _finding(session, milestone: Milestone) -> ProjectRiskFinding:
    now = datetime(2026, 7, 1, 6, 0)
    row = ProjectRiskFinding(
        finding_key=f"overdue:{milestone.id}", rule_id="milestone_overdue", category="schedule", severity="high",
        status="active", project_id=milestone.project_id, milestone_id=milestone.id, title="Overdue",
        explanation="Past due", recommended_action="Re-plan", first_detected_at=now, last_evaluated_at=now,
        last_changed_at=now, evaluation_date=now.date(),
    )
    session.add(row)
    session.commit()
    return row


# --------------------------------------------------------------------------- defaults and access


def test_rules_are_off_by_default_and_do_nothing(client, session):
    rules = client.get("/api/v1/automation/rules", headers=client.auth_headers).json()
    assert rules and not any(r["is_enabled"] for r in rules)
    assert {r["kind"] for r in rules} == {"event", "sweep", "external"}

    first, second = _seeded(session)[:2]
    second.depends_on_ids = dump_id_list([first.id])
    session.commit()
    response = client.patch(f"/api/v1/milestones/{first.id}", json={"status": "completed"}, headers=client.auth_headers)
    assert response.status_code == 200, response.text

    assert engine.run_sweeps(session, today=SWEEP_DAY) == {}
    assert client.post("/api/v1/automation/run-sweeps", json={}, headers=client.auth_headers).json() == {}
    assert _executions(session) == []
    assert _automation_notes(session) == []


def test_automation_endpoints_are_admin_only(client):
    for email in ("pm@prosohm.com", "readonly@prosohm.com", "anurag@prosohm.com"):
        headers = login(client, email)
        assert client.get("/api/v1/automation/rules", headers=headers).status_code == 403
        assert client.get("/api/v1/automation/executions", headers=headers).status_code == 403
        assert client.get("/api/v1/automation/decision-audit", headers=headers).status_code == 403
        assert client.patch("/api/v1/automation/rules/milestones.overdue_alert", json={"is_enabled": True},
                            headers=headers).status_code == 403
        assert client.post("/api/v1/automation/run-sweeps", json={}, headers=headers).status_code == 403


def test_external_rules_cannot_be_switched_and_toggle_is_audited(client, session):
    response = client.patch("/api/v1/automation/rules/finance.payment_follow_up", json={"is_enabled": True},
                            headers=client.auth_headers)
    assert response.status_code == 409
    assert client.patch("/api/v1/automation/rules/no.such.rule", json={"is_enabled": True},
                        headers=client.auth_headers).status_code == 404
    assert session.scalar(select(AutomationRule).where(AutomationRule.rule_key == "finance.payment_follow_up")) is None

    state = _enable(client, "milestones.overdue_alert")
    assert state["is_enabled"] is True
    _enable(client, "milestones.overdue_alert")  # no change, no second audit row
    _enable(client, "milestones.overdue_alert", False)
    session.expire_all()
    changes = session.scalars(
        select(Activity).where(Activity.action == ActivityAction.automation_rule_changed).order_by(Activity.created_at)
    ).all()
    assert [a.new_value for a in changes] == [
        "milestones.overdue_alert: enabled — test",
        "milestones.overdue_alert: disabled — test",
    ]
    assert all(a.user_id == IDS["user_admin"] for a in changes)

    audit = client.get("/api/v1/automation/decision-audit", params={"kind": "rule_change"},
                       headers=client.auth_headers).json()
    assert audit["total"] == 2
    assert audit["items"][0]["actor_name"] and audit["items"][0]["action"] == "Automation rule switched"


# --------------------------------------------------------------------------- milestone completed


def test_dependency_ready_notifies_and_never_changes_status(client, session):
    _enable(client, "milestones.dependency_ready")
    first, second, third, fourth = _seeded(session)[:4]
    second.depends_on_ids = dump_id_list([first.id])
    second.assigned_user_id = IDS["user_binil"]
    third.depends_on_ids = dump_id_list([first.id, fourth.id])  # still waits for fourth
    session.commit()

    response = client.patch(f"/api/v1/milestones/{first.id}", json={"status": "completed"}, headers=client.auth_headers)
    assert response.status_code == 200, response.text

    rows = _executions(session, "milestones.dependency_ready")
    assert len(rows) == 1 and rows[0].status == "succeeded", rows and rows[0].error_message
    assert rows[0].actor_id == IDS["user_admin"] and rows[0].trigger_event == "milestone.completed"
    assert json.loads(rows[0].result_json)["result"]["ready_milestone_ids"] == [str(second.id)]
    notes = _automation_notes(session)
    assert [n.user_id for n in notes] == [IDS["user_binil"]]
    assert notes[0].entity_id == second.id

    session.expire_all()
    assert session.get(Milestone, second.id).status == MilestoneStatus.not_started
    assert session.get(Milestone, third.id).status == MilestoneStatus.not_started

    events.milestone_completed(session, session.get(Milestone, first.id), actor=None)
    assert len(_executions(session, "milestones.dependency_ready")) == 1
    assert len(_automation_notes(session)) == 1


# --------------------------------------------------------------------------- overdue sweep


def test_overdue_sweep_links_control_tower_and_never_duplicates(client, session):
    _enable(client, "milestones.overdue_alert")
    milestones = _seeded(session)
    first = milestones[0]
    _complete_on = milestones[-1]
    _complete_on.status = MilestoneStatus.completed
    _complete_on.completed_date = date(2026, 6, 7)
    session.commit()
    finding = _finding(session, first)

    summary = engine.run_sweeps(session, today=SWEEP_DAY)["milestones.overdue_alert"]
    assert summary == {"evaluated": 6, "new": 6, "deduplicated": 0, "failed": 0}
    rows = {r.target_id: r for r in _executions(session, "milestones.overdue_alert")}
    assert _complete_on.id not in rows
    result = json.loads(rows[first.id].result_json)["result"]
    assert result["control_tower_finding_id"] == str(finding.id)
    assert result["recipient_basis"] == "design leader"
    assert rows[first.id].summary == "Overdue by 30 day(s); notified 1."
    assert len(_automation_notes(session, IDS["user_anurag"])) == 6

    again = engine.run_sweeps(session, today=SWEEP_DAY)["milestones.overdue_alert"]
    assert again == {"evaluated": 6, "new": 0, "deduplicated": 6, "failed": 0}
    assert len(_automation_notes(session)) == 6

    first = session.get(Milestone, first.id)
    first.due_date = date(2026, 6, 20)
    session.commit()
    moved = engine.run_sweeps(session, today=SWEEP_DAY)["milestones.overdue_alert"]
    assert moved["new"] == 1 and moved["deduplicated"] == 5
    assert len(_automation_notes(session)) == 7

    rule = session.scalar(select(AutomationRule).where(AutomationRule.rule_key == "milestones.overdue_alert"))
    assert rule.last_run_at is not None and rule.last_status == "succeeded"


def test_overdue_sweep_ignores_closed_projects_and_inactive_milestones(client, session):
    _enable(client, "milestones.overdue_alert")
    milestones = _seeded(session)
    milestones[0].lifecycle_state = "superseded"
    session.commit()
    summary = engine.run_sweeps(session, today=SWEEP_DAY)["milestones.overdue_alert"]
    assert summary["evaluated"] == 6
    assert milestones[0].id not in {r.target_id for r in _executions(session)}

    project = session.get(Project, IDS["project"])
    project.is_archived = True
    session.commit()
    assert engine.run_sweeps(session, today=date(2026, 8, 1))["milestones.overdue_alert"]["evaluated"] == 0


# --------------------------------------------------------------------------- failure and retry


def test_failed_action_is_recorded_rolled_back_and_retried(client, session, monkeypatch):
    _enable(client, "milestones.overdue_alert")
    original = engine.get_rule("milestones.overdue_alert")

    def broken(db, ctx):
        engine.notify(db, [IDS["user_anurag"]], title="partial", message="should roll back",
                      entity_type=None, entity_id=uuid.uuid4())
        raise RuntimeError("mail relay down")

    monkeypatch.setitem(engine.REGISTRY, original.key, dataclasses.replace(original, perform=broken))
    summary = engine.run_sweeps(session, today=SWEEP_DAY)["milestones.overdue_alert"]
    assert summary["new"] == 7 and summary["failed"] == 7
    rows = _executions(session, original.key)
    assert all(r.status == "failed" and r.error_message == "RuntimeError: mail relay down" for r in rows)
    assert _automation_notes(session) == []

    failures = client.get("/api/v1/automation/executions", params={"status": "failed"},
                          headers=client.auth_headers).json()
    assert failures["total"] == 7
    rule_state = next(r for r in client.get("/api/v1/automation/rules", headers=client.auth_headers).json()
                      if r["key"] == original.key)
    assert rule_state["failed_count"] == 7 and rule_state["last_status"] == "failed"

    assert engine.run_sweeps(session, today=SWEEP_DAY)[original.key]["deduplicated"] == 7  # no automatic retry

    monkeypatch.setitem(engine.REGISTRY, original.key, original)
    response = client.post(f"/api/v1/automation/executions/{rows[0].id}/retry", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "succeeded" and body["attempts"] == 2 and body["error_message"] is None
    assert len(_automation_notes(session)) == 1
    assert client.post(f"/api/v1/automation/executions/{rows[0].id}/retry",
                       headers=client.auth_headers).status_code == 409


# --------------------------------------------------------------------------- recommendation and review


def test_template_update_is_only_recommended_and_reviewed(client, session):
    mold = _mold(session).id
    v1 = ProjectTemplate(name="Family", project_type_id=mold, is_active=False, version=1)
    session.add(v1)
    session.flush()
    v1.template_family_id = v1.id
    v2 = ProjectTemplate(name="Family", project_type_id=mold, is_active=True, version=2, template_family_id=v1.id)
    session.add(v2)
    project = session.get(Project, IDS["project"])
    project.project_template_id = v1.id
    session.commit()

    _enable(client, "projects.template_update_available")
    engine.run_sweeps(session, today=SWEEP_DAY)
    rows = _executions(session, "projects.template_update_available")
    assert len(rows) == 1 and rows[0].status == "pending_review"
    assert [n.user_id for n in _automation_notes(session)] == [IDS["user_anurag"]]
    session.expire_all()
    assert session.get(Project, IDS["project"]).project_template_id == v1.id
    assert len(_seeded(session)) == 7

    response = client.post(f"/api/v1/automation/executions/{rows[0].id}/review",
                           json={"decision": "acknowledge", "note": "Will preview next week"},
                           headers=client.auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "succeeded" and response.json()["reviewed_by_name"]
    assert client.post(f"/api/v1/automation/executions/{rows[0].id}/review", json={"decision": "dismiss"},
                       headers=client.auth_headers).status_code == 409
    engine.run_sweeps(session, today=SWEEP_DAY)
    assert len(_executions(session, "projects.template_update_available")) == 1
    session.expire_all()
    assert session.get(Project, IDS["project"]).project_template_id == v1.id


def test_project_without_designer_is_flagged_once_per_week(client, session):
    project = session.get(Project, IDS["project"])
    project.designer_id = None
    session.commit()
    _enable(client, "resource.project_without_designer")
    key = "resource.project_without_designer"
    assert engine.run_sweeps(session, today=date(2026, 7, 6))[key]["new"] == 1
    assert engine.run_sweeps(session, today=date(2026, 7, 9))[key]["deduplicated"] == 1
    assert engine.run_sweeps(session, today=date(2026, 7, 13))[key]["new"] == 1
    assert len(_automation_notes(session, IDS["user_anurag"])) == 2
    session.expire_all()
    assert session.get(Project, IDS["project"]).designer_id is None


# --------------------------------------------------------------------------- reconciliation event + decision audit


def test_reconciliation_notifies_owners_and_appears_in_decision_audit(client, session):
    _enable(client, "milestones.template_reconciled_notice")
    _enable(client, "milestones.added_needs_owner")
    small = _template(session, "Small Auto", [{"name": "Blockout", "stage": ProjectStage.preliminary}])
    full = _template(session, "Full Auto", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Roughing", "stage": ProjectStage.preliminary, "deps": ["Blockout"]},
    ])
    project_id = _new_project(client, session, small)
    before = len(_automation_notes(session))
    preview = _preview(client, project_id, full.id)
    result = _apply(client, project_id, preview, reason="Customer asked for full design")
    recon_id = uuid.UUID(result["reconciliation"]["id"])

    notice = _executions(session, "milestones.template_reconciled_notice")
    assert len(notice) == 1 and notice[0].status == "succeeded", notice and notice[0].error_message
    notified = set(json.loads(notice[0].result_json)["result"]["notified_user_ids"])
    assert notified == {str(IDS["user_anurag"]), str(IDS["user_binil"])}  # not the admin who applied it

    owner = _executions(session, "milestones.added_needs_owner")
    assert len(owner) == 1 and owner[0].status in {"succeeded", "skipped"}
    unowned = session.scalars(select(Milestone).where(
        Milestone.reconciliation_id == recon_id, Milestone.assigned_user_id.is_(None))).all()
    if unowned:
        assert json.loads(owner[0].result_json)["result"]["milestone_ids"] == [str(m.id) for m in unowned]
    assert session.scalar(select(func.count()).select_from(Milestone).where(
        Milestone.reconciliation_id == recon_id)) == 1
    assert len(_automation_notes(session)) > before

    audit = client.get("/api/v1/automation/decision-audit", params={"search": "Full Auto"},
                       headers=client.auth_headers).json()
    entry = next(i for i in audit["items"] if i["kind"] == "template_change")
    assert entry["previous_value"].startswith("Small Auto") and entry["new_value"].startswith("Full Auto")
    assert entry["reason"] == "Customer asked for full design"
    assert entry["approval_reference"] == f"reconciliation:{recon_id}"
    assert entry["result"] == "applied" and entry["project_id"] == str(project_id)

    scoped = client.get("/api/v1/automation/decision-audit",
                        params={"project_id": str(project_id), "kind": "automation"},
                        headers=client.auth_headers).json()
    assert scoped["total"] == 2
    assert {i["trigger"] for i in scoped["items"]} == {"project.template_reconciled"}
