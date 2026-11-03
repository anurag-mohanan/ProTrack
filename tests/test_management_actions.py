"""Phase 8 Stage 5: strategic initiatives and management action tracking."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.models.enums import NotificationType
from app.models.models import Notification
from tests.conftest import IDS, login

BASE = "/api/v1/management"


def _objective(client) -> dict:
    response = client.post(f"{BASE}/objectives", headers=client.auth_headers, json={
        "title": "Reduce delivery delays", "fy_start_year": 2025, "unit": "percentage", "category": "delivery",
        "measurement": "automatic", "metric_key": "on_time_delivery_rate", "target_value": "90"})
    assert response.status_code == 201, response.text
    return response.json()


# ----------------------------------------------------------------- 10: initiatives


def test_initiative_links_objective_and_existing_projects(client):
    objective = _objective(client)
    response = client.post(f"{BASE}/initiatives", headers=client.auth_headers, json={
        "name": "Stage-gate design reviews", "objective_id": objective["id"], "owner_id": str(IDS["user_pm"]),
        "start_date": "2025-04-01", "target_date": "2025-12-31", "priority": "high",
        "milestones": [{"title": "Checklist agreed", "due_date": "2025-05-15"}, {"title": "Rolled out to all teams"}],
        "risks": "Designer availability", "related_project_ids": [str(IDS["project"])]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["objective"] == "Reduce delivery delays"
    assert [p["code"] for p in body["projects"]] == ["TEST-001"]  # referenced, not copied
    assert body["progress_kind"] == "reported" and body["milestones_done"] == 0
    detail = client.get(f"{BASE}/objectives/{objective['id']}", headers=client.auth_headers).json()
    assert [i["name"] for i in detail["initiatives"]] == ["Stage-gate design reviews"]

    pm = login(client, "pm@prosohm.com")
    ok = client.patch(f"{BASE}/initiatives/{body['id']}", headers=pm, json={
        "progress_percent": 40, "milestones": [{"title": "Checklist agreed", "due_date": "2025-05-15", "done": True},
                                               {"title": "Rolled out to all teams"}]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["progress_percent"] == 40 and ok.json()["milestones_done"] == 1
    held = client.patch(f"{BASE}/initiatives/{body['id']}", headers=pm, json={"status": "on_hold"})
    assert held.status_code == 422  # reason required
    held = client.patch(f"{BASE}/initiatives/{body['id']}", headers=pm,
                        json={"status": "on_hold", "status_reason": "Waiting for new hires"})
    assert held.json()["status"] == "on_hold"
    assert {e["event_type"] for e in held.json()["events"]} >= {"created", "updated", "status_changed"}
    bad = client.post(f"{BASE}/initiatives", headers=client.auth_headers,
                      json={"name": "Ghost", "related_project_ids": [str(IDS["customer"])]})
    assert bad.status_code == 422


def test_initiative_permissions(client):
    leader = login(client, "anurag@prosohm.com")
    assert client.post(f"{BASE}/initiatives", headers=leader, json={"name": "Not allowed"}).status_code == 403
    created = client.post(f"{BASE}/initiatives", headers=client.auth_headers,
                          json={"name": "Owner limits", "owner_id": str(IDS["user_anurag"])}).json()
    renamed = client.patch(f"{BASE}/initiatives/{created['id']}", headers=leader, json={"name": "Renamed"})
    assert renamed.status_code == 403  # owner may update progress and status only
    assert client.patch(f"{BASE}/initiatives/{created['id']}", headers=leader,
                        json={"progress_percent": 10}).status_code == 200


# ----------------------------------------------------------------- 13: actions


def test_action_assignment_notifies_owner_and_completion_needs_evidence(client, session):
    objective = _objective(client)
    due = (date.today() + timedelta(days=7)).isoformat()
    response = client.post(f"{BASE}/actions", headers=client.auth_headers, json={
        "title": "Publish design review checklist", "owner_id": str(IDS["user_pm"]), "due_date": due,
        "priority": "high", "objective_id": objective["id"], "project_id": str(IDS["project"])})
    assert response.status_code == 201, response.text
    action = response.json()
    assert action["status"] == "open" and action["owner"] == "Project Manager"
    assert action["objective"]["title"] == "Reduce delivery delays" and action["project"]["code"] == "TEST-001"
    note = session.scalars(select(Notification).where(
        Notification.user_id == IDS["user_pm"],
        Notification.notification_type == NotificationType.management_action_assigned)).all()
    assert len(note) == 1 and "Publish design review checklist" in note[0].message

    pm = login(client, "pm@prosohm.com")
    url = f"{BASE}/actions/{action['id']}"
    assert client.patch(url, headers=pm, json={"status": "completed"}).status_code == 422
    assert client.patch(url, headers=pm, json={"status": "blocked"}).status_code == 422
    done = client.patch(url, headers=pm, json={"status": "completed",
                                               "completion_evidence": "Checklist v1 on the shared drive"})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed" and body["completed_at"]
    completed = next(e for e in body["events"] if e["event_type"] == "completed")
    assert completed["body"] == "Checklist v1 on the shared drive" and completed["actor"] == "Project Manager"


def test_action_visibility_and_reopening(client):
    created = client.post(f"{BASE}/actions", headers=client.auth_headers, json={
        "title": "Owner-only visibility", "owner_id": str(IDS["user_anurag"]),
        "due_date": (date.today() - timedelta(days=2)).isoformat()}).json()
    other = client.post(f"{BASE}/actions", headers=client.auth_headers, json={
        "title": "Someone else's action", "owner_id": str(IDS["user_pm"])}).json()
    leader = login(client, "anurag@prosohm.com")
    listed = client.get(f"{BASE}/actions", headers=leader).json()
    assert [a["id"] for a in listed["actions"]] == [created["id"]]  # no organisation-wide scope: own actions only
    assert listed["summary"]["overdue"] == 1 and listed["actions"][0]["overdue"] is True
    assert client.get(f"{BASE}/actions/{other['id']}", headers=leader).status_code == 404
    assert client.post(f"{BASE}/actions", headers=leader,
                       json={"title": "Self-assigned", "owner_id": str(IDS["user_anurag"])}).status_code == 403

    url = f"{BASE}/actions/{created['id']}"
    assert client.patch(url, headers=leader, json={"due_date": "2030-01-01"}).status_code == 403  # owner: status only
    client.patch(url, headers=leader, json={"status": "completed", "completion_evidence": "Done and verified"})
    assert client.patch(url, headers=leader, json={"status": "open"}).status_code == 403
    reopened = client.patch(url, headers=client.auth_headers, json={"status": "in_progress"})
    assert reopened.status_code == 200 and reopened.json()["completed_at"] is None
    admin = client.get(f"{BASE}/actions", params={"open_only": True}, headers=client.auth_headers).json()
    assert {a["id"] for a in admin["actions"]} == {created["id"], other["id"]}
