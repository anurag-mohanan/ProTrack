"""Phase 8 Stage 4: strategic objectives, automatic and manual KPIs, approvals and audit."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.models import Activity
from app.models.enums import ActivityAction
from app.services.management.objectives import pace, progress_percent
from tests.conftest import IDS, login
from tests.test_management_cockpit import _seed_finance

URL = "/api/v1/management/objectives"


def _create(client, headers=None, expect: int = 201, **body):
    payload = {"title": "Grow invoiced revenue", "fy_start_year": 2025, "unit": "currency",
               "category": "financial", "measurement": "automatic", "metric_key": "invoiced_revenue",
               "target_value": "2000", **body}
    response = client.post(URL, json=payload, headers=headers or client.auth_headers)
    assert response.status_code == expect, response.text
    return response.json()


def _manual(client, headers=None, expect: int = 201, **body):
    return _create(client, headers, expect, **{"title": "New customer logos", "unit": "count", "category": "growth",
                                              "measurement": "manual", "metric_key": None, "target_value": "4", **body})


# ----------------------------------------------------------------- 7 + 8: CRUD and automatic KPIs


def test_automatic_objective_reads_finance_actual(client, session):
    _seed_finance(session)
    body = _create(client, baseline_value="500")
    assert body["period"]["start"] == "2025-04-01" and body["period"]["end"] == "2026-03-31"
    assert body["current"]["value"] == 1200 and body["current"]["kind"] == "actual"
    assert body["target"] == {"value": 2000, "kind": "target", "state": "approved"}
    assert body["progress_percent"] == 46.7  # (1200 - 500) / (2000 - 500)
    assert body["pace"]["basis"] == "cumulative"
    assert body["target_state"] == "approved" and body["target_approved_by"] == "System Admin"
    assert [e["event_type"] for e in body["events"]] == ["created"]
    listed = client.get(URL, params={"fy_start_year": 2025}, headers=client.auth_headers).json()["objectives"]
    assert [o["id"] for o in listed] == [body["id"]]


def test_manual_values_never_overwrite_automatic_actuals(client, session):
    _seed_finance(session)
    auto = _create(client)
    response = client.post(f"{URL}/{auto['id']}/measurements", headers=client.auth_headers,
                           json={"value": "999999", "period_start": "2025-04-01", "period_end": "2025-06-30",
                                 "evidence": "Spreadsheet"})
    assert response.status_code == 422
    assert "automatically" in response.json()["detail"]
    assert client.get(f"{URL}/{auto['id']}", headers=client.auth_headers).json()["current"]["value"] == 1200
    response = client.patch(f"{URL}/{auto['id']}", json={"current_value": "5"}, headers=client.auth_headers)
    assert response.status_code == 422  # no such field: actuals are not editable


def test_manual_measurement_with_audit_and_correction(client):
    obj = _manual(client)
    assert obj["current"]["status"] == "unavailable" and obj["current"]["kind"] == "manual"
    first = client.post(f"{URL}/{obj['id']}/measurements", headers=client.auth_headers,
                        json={"value": "2", "period_start": "2025-04-01", "period_end": "2025-09-30",
                              "evidence": "Signed POs from two new customers"})
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["current"]["value"] == 2 and body["current"]["recorded_by"] == "System Admin"
    assert body["progress_percent"] == 50.0
    original = body["measurements"][0]["id"]
    fix = client.post(f"{URL}/{obj['id']}/measurements", headers=client.auth_headers,
                      json={"value": "3", "period_start": "2025-04-01", "period_end": "2025-09-30",
                            "evidence": "Third PO found", "supersedes_id": original}).json()
    assert fix["current"]["value"] == 3
    assert len(fix["measurements"]) == 2  # appended, the first value is kept
    assert {e["event_type"] for e in fix["events"]} >= {"created", "measurement_recorded"}
    outside = client.post(f"{URL}/{obj['id']}/measurements", headers=client.auth_headers,
                          json={"value": "1", "period_start": "2026-04-01", "period_end": "2026-04-30",
                                "evidence": "Next year"})
    assert outside.status_code == 422
    missing = client.post(f"{URL}/{obj['id']}/measurements", headers=client.auth_headers,
                          json={"value": "1", "period_start": "2025-04-01", "period_end": "2025-04-30"})
    assert missing.status_code == 422  # evidence is required


# ----------------------------------------------------------------- 11: target / baseline approvals


def test_target_changes_need_approval_and_record_the_approver(client, session):
    pm = login(client, "pm@prosohm.com")
    obj = _manual(client, headers=pm, baseline_value="1")
    assert obj["target_state"] == "proposed" and obj["target_approved_by"] is None
    denied = client.post(f"{URL}/{obj['id']}/target", headers=pm, json={"target_value": "10", "reason": "Stretch goal"})
    assert denied.status_code == 403
    assert client.post(f"{URL}/{obj['id']}/approve-target", headers=pm, json={}).status_code == 403

    approved = client.post(f"{URL}/{obj['id']}/approve-target", headers=client.auth_headers,
                           json={"note": "Agreed in board meeting"}).json()
    assert approved["target_state"] == "approved" and approved["target_approved_by"] == "System Admin"
    changed = client.post(f"{URL}/{obj['id']}/target", headers=client.auth_headers,
                          json={"target_value": "6", "baseline_value": "2", "reason": "Customer pipeline revised"})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["target"]["value"] == 6 and body["baseline"]["value"] == 2
    events = {e["event_type"]: e for e in body["events"]}
    assert events["target_changed"]["old_value"] == "4.00" and events["target_changed"]["new_value"] == "6"
    assert events["target_changed"]["approved_by"] == "System Admin"
    assert events["target_changed"]["reason"] == "Customer pipeline revised"
    assert "baseline_changed" in events and "target_approved" in events
    audit = session.scalars(select(Activity).where(Activity.action == ActivityAction.strategy_target_changed)).all()
    assert len(audit) >= 3
    no_reason = client.post(f"{URL}/{obj['id']}/target", headers=client.auth_headers, json={"target_value": "7"})
    assert no_reason.status_code == 422


# ----------------------------------------------------------------- 15: permissions


def test_objective_permissions_and_redaction(client, session):
    _seed_finance(session)
    obj = _create(client)
    leader = login(client, "anurag@prosohm.com")
    _create(client, headers=leader, expect=403)
    seen = client.get(f"{URL}/{obj['id']}", headers=leader).json()
    assert seen["restricted"] is True and seen["target"] is None and seen["current"] is None
    assert seen["measurements"] == []
    assert client.patch(f"{URL}/{obj['id']}", json={"title": "Hacked"}, headers=leader).status_code == 403
    comment = client.post(f"{URL}/{obj['id']}/comments", headers=leader, json={"text": "Looks good"})
    assert comment.status_code == 403

    designer = login(client, "binil@prosohm.com")
    assert client.get(URL, headers=designer).status_code == 403


def test_owner_updates_status_with_reason_but_not_other_fields(client):
    obj = _manual(client, owner_id=str(IDS["user_pm"]))
    pm = login(client, "pm@prosohm.com")
    response = client.patch(f"{URL}/{obj['id']}", headers=pm, json={"status": "at_risk"})
    assert response.status_code == 422  # reason required
    ok = client.patch(f"{URL}/{obj['id']}", headers=pm, json={"status": "at_risk", "status_reason": "Two deals slipped"})
    assert ok.status_code == 200 and ok.json()["status"] == "at_risk"
    status_event = next(e for e in ok.json()["events"] if e["event_type"] == "status_changed")
    assert status_event["reason"] == "Two deals slipped" and status_event["actor"] == "Project Manager"
    decision = client.post(f"{URL}/{obj['id']}/comments", headers=client.auth_headers,
                           json={"kind": "decision", "text": "Add a second sales channel"})
    assert decision.status_code == 201
    assert any(e["event_type"] == "decision" for e in decision.json()["events"])


def test_objective_validation(client):
    _create(client, unit="count", expect=422)  # invoiced revenue is a currency KPI
    _create(client, metric_key="made_up", expect=422)
    _create(client, metric_key="skill_verified_holders", unit="count", category="workforce", expect=422)  # skill_id
    _create(client, metric_key="outstanding_receivables", direction="decrease", expect=422)  # needs a baseline
    _create(client, measurement="manual", expect=422)  # manual cannot carry a KPI key
    _create(client, period_type="quarterly", period_index=2, metric_params={"skill_id": "x"}, expect=422)
    quarterly = _create(client, period_type="quarterly", period_index=2)
    assert quarterly["period"]["start"] == "2025-07-01" and quarterly["period"]["end"] == "2025-09-30"


# ----------------------------------------------------------------- progress and pace rules


def test_progress_and_pace_rules():
    assert progress_percent("increase", None, Decimal("100"), 25) == 25.0
    assert progress_percent("increase", Decimal("50"), Decimal("100"), 75) == 50.0
    assert progress_percent("decrease", Decimal("40"), Decimal("20"), 30) == 50.0
    assert progress_percent("decrease", None, Decimal("20"), 30) is None
    assert progress_percent("increase", None, Decimal("100"), None) is None

    class Obj:
        start_date, target_date, status, metric_key = date(2025, 4, 1), date(2026, 3, 31), "on_track", "invoiced_revenue"

    mid = pace(Obj, 20.0, date(2025, 9, 30))  # ~50 % of the year elapsed, 20 % achieved
    assert mid["basis"] == "cumulative" and mid["suggested_status"] == "delayed"
    assert pace(Obj, 30.0, date(2025, 9, 30))["suggested_status"] == "at_risk"
    assert pace(Obj, 45.0, date(2025, 9, 30))["suggested_status"] == "on_track"
    assert pace(Obj, 30.0, date(2025, 3, 1))["suggested_status"] == "not_started"
    assert pace(Obj, 90.0, date(2026, 4, 2))["suggested_status"] == "delayed"
    Obj.metric_key = "on_time_delivery_rate"
    assert pace(Obj, 80.0, date(2025, 6, 1))["basis"] == "level"
    assert pace(Obj, 80.0, date(2025, 6, 1))["suggested_status"] == "at_risk"
