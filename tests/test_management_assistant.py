"""Phase 8 Stage 7: AI management intelligence through the Phase 6 assistant (scripted provider only)."""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.models.models import User
from app.services.management.access import resolve_access
from app.services.management.business import build_business
from app.services.management.filters import CockpitFilters, fy_period
from tests.conftest import IDS, login
from tests.test_ai_assistant import _ask, _install, _isolate, call  # noqa: F401 - autouse fixture
from tests.test_management_cockpit import _seed_finance

FY25 = {"fy_start_year": 2025}


def _objective(client, **body) -> dict:
    response = client.post("/api/v1/management/objectives", headers=client.auth_headers, json={
        "title": "FY25 billing target", "fy_start_year": 2025, "unit": "currency", "category": "financial",
        "measurement": "automatic", "metric_key": "invoiced_revenue", "target_value": "2000", **body})
    assert response.status_code == 201, response.text
    return response.json()


def test_business_performance_matches_the_finance_ledger_and_keeps_targets_apart(client, session):
    _seed_finance(session)
    _objective(client)
    provider = _install([{"tool_calls": [call("get_business_performance", FY25)]}, {"content": "ok"}])
    answer = _ask(client, client.auth_headers, "How did Prosohm perform in FY 2025?")
    payload = provider.tool_payloads()[0]
    data = payload["data"]
    assert data["period"]["start"] == "2025-04-01" and data["period"]["end"] == "2026-03-31"
    assert data["value_kind"] == "actual"
    service = build_business(session, resolve_access(session, session.get(User, IDS["user_admin"])),
                             CockpitFilters(fy_period(2025, 4)), date.today())
    invoiced = next(k for k in data["kpis"] if k["metric"] == "Invoiced revenue")
    assert invoiced["value"] == next(k["value"] for k in service["kpis"] if k["key"] == "invoiced_revenue") == 1200
    target = data["targets"][0]
    assert target["target"]["kind"] == "target" and target["target"]["value"] == 2000
    assert target["actual"] == 1200 and target["actual_kind"] == "actual"
    assert any(s["key"].startswith("report:management-cockpit") for s in answer["sources"])
    assert answer["limitations"]


def test_finance_figures_never_reach_the_model_without_finance_access(client, session):
    _seed_finance(session)
    _objective(client)
    leader = login(client, "anurag@prosohm.com")
    provider = _install([
        {"tool_calls": [call("get_business_performance", FY25, "a"),
                        call("get_customer_performance", {"customer": "Prosohm Test", **FY25}, "b"),
                        call("get_strategic_objectives", FY25, "c")]},
        {"content": "ok"},
    ])
    _ask(client, leader, "How much did we bill and how is Prosohm Test Customer doing?")
    assert "get_business_performance" not in provider.requests[0]["tools"]
    denied, customer, objectives = provider.tool_payloads()
    assert denied["error"] == "access_denied" and "data" not in denied
    assert customer["data"]["finance"] is None and customer["data"]["finance_visible"] is False
    assert objectives["data"]["objectives"][0]["restricted"] is True
    assert objectives["data"]["objectives"][0]["target"] is None
    sent = json.dumps(provider.requests[-1]["messages"])
    assert "1200" not in sent and "Alpha Tooling" not in sent and "Beta Molds" not in sent


def test_customer_lookup_is_scoped_and_reports_observed_signals_separately(client, session):
    provider = _install([
        {"tool_calls": [call("get_customer_performance", {"customer": "Prosohm Test", **FY25}, "a"),
                        call("get_customer_performance", {"customer": "Nobody Ltd"}, "b")]},
        {"content": "ok"},
    ])
    _ask(client, client.auth_headers, "How is Prosohm Test Customer doing?")
    found, missing = provider.tool_payloads()
    assert found["data"]["customer"] == "Prosohm Test Customer"
    assert found["data"]["forecasts"]["kind"] == "forecast"
    assert all(s["observed"] for s in found["data"]["observed_signals"])
    assert missing["error"] == "invalid_request" and "customers you can access" in missing["message"]


def test_operations_objectives_and_focus_label_actuals_and_forecasts(client, session):
    client.post("/api/v1/management/actions", headers=client.auth_headers, json={
        "title": "Close the overdue design review", "owner_id": str(IDS["user_pm"]),
        "due_date": (date.today() - timedelta(days=3)).isoformat()})
    provider = _install([
        {"tool_calls": [call("get_engineering_operations", {**FY25, "compare_by": "classification"}, "a"),
                        call("get_management_focus", {}, "b")]},
        {"content": "ok"},
    ])
    answer = _ask(client, client.auth_headers, "Which stages use most hours and what should we focus on?")
    ops, focus = provider.tool_payloads()
    assert "effort_by_stage" in ops["data"] and ops["data"]["comparison"]["by"] == "Project classification"
    assert "forecast" in ops["data"]["kinds_note"]
    kinds = {i["kind"] for i in focus["data"]["focus_items"]}
    assert kinds <= {"actual", "forecast", "target_vs_actual"}
    assert any(i["item"] == "Close the overdue design review" for i in focus["data"]["focus_items"])
    assert focus["data"]["period"]["start"] == date(date.today().year, date.today().month, 1).isoformat()
    assert any("performance-review" in note for note in answer["limitations"])


def test_management_suggestions_answer_without_a_provider(client, session):
    _seed_finance(session)
    headers = client.auth_headers
    ids = {s["id"] for s in client.get("/api/v1/assistant/suggestions", headers=headers).json()}
    assert {"fy-performance", "stage-hours", "management-focus"} <= ids
    assert "objectives-at-risk" not in ids  # no objectives recorded yet
    answer = _ask(client, headers, "What should management focus on this month?", suggestion_id="management-focus")
    assert answer["status"] == "data"
    designer = login(client, "binil@prosohm.com")
    designer_ids = {s["id"] for s in client.get("/api/v1/assistant/suggestions", headers=designer).json()}
    assert not {"fy-performance", "stage-hours", "management-focus"} & designer_ids
