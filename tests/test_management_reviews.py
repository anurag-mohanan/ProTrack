"""Phase 8 Stage 6: management reviews (generation, finalising, decisions, history, comparison)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.enums import NotificationType
from app.models.models import Notification
from tests.conftest import IDS, login
from tests.test_management_cockpit import _invoice, _seed_finance

URL = "/api/v1/management/reviews"
JUNE = {"review_type": "monthly", "fy_start_year": 2025, "period_index": 3}  # April-start FY: month 3 is June
JULY = {**JUNE, "period_index": 4}


def _kpi(section: dict, key: str) -> dict:
    return next(k for k in section["kpis"] if k["key"] == key)


def _review(client, body=None, headers=None, expect: int = 201) -> dict:
    response = client.post(URL, json=body or JUNE, headers=headers or client.auth_headers)
    assert response.status_code == expect, response.text
    return response.json()


# ----------------------------------------------------------------- 11: generation


def test_review_generates_all_sections_with_forecasts_apart(client, session):
    _seed_finance(session)
    review = _review(client)
    assert review["status"] == "draft" and review["period"] == {"start": "2025-06-01", "end": "2025-06-30"}
    snap = review["snapshot"]
    assert set(review["sections"]) <= set(snap)
    assert _kpi(snap["financial"], "invoiced_revenue")["value"] == 400
    assert _kpi(snap["financial"], "collections")["value"] == 0
    assert snap["forecasts"]["kind"] == "forecast"
    assert all(k["kind"] != "forecast" for k in snap["financial"]["kpis"])
    assert any("INR 400" in h for h in snap["executive_summary"]["generated_highlights"])
    assert review["executive_summary"] is None  # generated text is never the official summary
    assert {e["event_type"] for e in review["events"]} == {"created", "generated"}
    _review(client, {"review_type": "monthly", "fy_start_year": 2040, "period_index": 1}, expect=422)
    _review(client, {"review_type": "quarterly", "fy_start_year": 2025}, expect=422)


# ----------------------------------------------------------------- 12 + 13: finalising, history, decisions


def test_finalising_needs_human_summary_and_approval_then_freezes(client, session):
    a, _, qa, _ = _seed_finance(session)
    review = _review(client)
    url = f"{URL}/{review['id']}"
    assert client.post(f"{url}/finalise", headers=client.auth_headers).status_code == 422  # no summary yet
    pm = login(client, "pm@prosohm.com")
    assert client.patch(url, headers=pm, json={"executive_summary": "June was steady."}).status_code == 200
    assert client.post(f"{url}/finalise", headers=pm).status_code == 403  # manage, but not approve
    final = client.post(f"{url}/finalise", headers=client.auth_headers)
    assert final.status_code == 200, final.text
    body = final.json()
    assert body["status"] == "final" and body["finalised_by"] == "System Admin"
    assert client.patch(url, headers=client.auth_headers, json={"executive_summary": "Rewritten"}).status_code == 422
    assert client.post(f"{url}/regenerate", headers=client.auth_headers).status_code == 422

    _invoice(session, qa, "999", date(2025, 6, 20))  # a later Finance entry does not rewrite the review
    session.commit()
    again = client.get(url, headers=client.auth_headers).json()
    assert _kpi(again["snapshot"]["financial"], "invoiced_revenue")["value"] == 400
    assert again["executive_summary"] == "June was steady."


def test_decisions_create_linked_actions(client, session):
    review = _review(client)
    url = f"{URL}/{review['id']}"
    response = client.post(f"{url}/decisions", headers=client.auth_headers, json={
        "text": "Hire two contract designers for Q2 peak", "action_title": "Raise hiring request",
        "action_owner_id": str(IDS["user_pm"]), "action_due_date": "2025-07-15", "action_priority": "high"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert [d["summary"] for d in body["decisions"]] == ["Hire two contract designers for Q2 peak"]
    assert len(body["actions"]) == 1
    action = body["actions"][0]
    assert action["title"] == "Raise hiring request" and action["from_decision"] is True
    assert action["review"]["id"] == review["id"]
    assert session.scalars(select(Notification).where(
        Notification.notification_type == NotificationType.management_action_assigned)).first() is not None
    plain = client.post(f"{url}/decisions", headers=client.auth_headers, json={"text": "Keep pricing unchanged"})
    assert len(plain.json()["decisions"]) == 2 and len(plain.json()["actions"]) == 1
    bad = client.post(f"{url}/decisions", headers=client.auth_headers,
                      json={"text": "Needs an owner", "action_title": "Orphan action"})
    assert bad.status_code == 422


def test_review_history_and_period_comparison(client, session):
    _seed_finance(session)
    june = _review(client)
    july = _review(client, JULY)
    assert july["previous_review_id"] == june["id"]
    history = client.get(URL, params={"review_type": "monthly"}, headers=client.auth_headers).json()["reviews"]
    assert [r["id"] for r in history] == [july["id"], june["id"]]
    comparison = client.get(f"{URL}/{july['id']}/compare", headers=client.auth_headers).json()
    rows = {r["key"]: r for r in comparison["rows"]}
    assert rows["invoiced_revenue"]["previous"] == 400 and rows["invoiced_revenue"]["current"] == 0
    assert rows["invoiced_revenue"]["change"] == -400
    assert rows["collections"]["current"] == 250
    first = client.get(f"{URL}/{june['id']}/compare", headers=client.auth_headers).json()
    assert first["other"] is None


# ----------------------------------------------------------------- 15: permissions


def test_review_permissions_and_redaction(client, session):
    _seed_finance(session)
    review = _review(client)
    leader = login(client, "anurag@prosohm.com")  # not organisation-wide, no strategy permission
    assert client.get(URL, headers=leader).status_code == 403
    assert client.get(f"{URL}/{review['id']}", headers=leader).status_code == 403
    _review(client, headers=leader, expect=403)

    board = login(client, "planning-board@prosohm.com")  # organisation-wide, no Finance access
    seen = client.get(f"{URL}/{review['id']}", headers=board).json()
    assert seen["snapshot"]["financial"] == {"visible": False, "reason": "Needs Finance view access."}
    assert all("invoiced" not in r for r in seen["snapshot"]["customer"]["rows"])
    assert not any("INR" in h for h in seen["snapshot"]["executive_summary"]["generated_highlights"])
    assert seen["snapshot"]["workforce"]["visible"] is True
    assert seen["can_edit"] is False and seen["can_finalise"] is False
    compare = client.get(f"{URL}/{review['id']}/compare", headers=board).json()
    assert compare["rows"] == []
    assert client.post(f"{URL}/{review['id']}/decisions", headers=board, json={"text": "Not allowed"}).status_code == 403
