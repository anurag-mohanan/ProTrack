"""Phase 8 Stages 2-3: management cockpit, customer intelligence and engineering efficiency.

Deterministic data only. Figures must come from the existing Finance ledger, Quote-to-Delivery
metrics, official hours rule and capacity calendar, with actuals, plans and forecasts kept apart.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.enums import ProjectClassification, ProjectStage, TimesheetStatus, UserType
from app.models.finance import Quote, QuotePaymentLine, QuoteRevision
from app.models.foundation import Holiday
from app.models.models import Customer, User
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash
from app.services.management.access import ManagementForbidden, resolve_access
from app.services.management.business import build_business
from app.services.management.customers import build_customer_profile, build_customer_table
from app.services.management.efficiency import build_efficiency
from app.services.management.filters import (
    CockpitFilters,
    build_filters,
    fy_period,
    resolve_period,
    sub_period,
)
from app.services.management.operations import booked_hours, build_operations
from app.services.management.workforce import build_workforce, capacity_totals
from tests.conftest import IDS, login
from tests.test_engineering_metrics import _book, _project
from tests.test_stage_delivery_metrics import _completed, _staged

FY25 = fy_period(2025, 4)
TODAY = date(2026, 2, 15)
URL = "/api/v1/management"


def _kpi(section: dict, key: str) -> dict:
    return next(k for k in section["kpis"] if k["key"] == key)


def _admin(session):
    return resolve_access(session, session.get(User, IDS["user_admin"]))


def _customer(session, name: str) -> Customer:
    row = Customer(id=uuid.uuid4(), name=name, code=f"C{uuid.uuid4().hex[:5]}", is_active=True)
    session.add(row)
    session.flush()
    return row


def _quote(session, customer_id, *, revenue: str, base_inr: str | None = None, currency: str = "INR",
           quoted: date | None = None, active: bool = True, project_id=None) -> Quote:
    quote = Quote(id=uuid.uuid4(), customer_id=customer_id, tool_number=f"MQ-{uuid.uuid4().hex[:6]}",
                  currency_code=currency, is_active=active, quoted_date=quoted, project_id=project_id)
    session.add(quote)
    session.flush()
    session.add(QuoteRevision(
        id=uuid.uuid4(), quote_id=quote.id, version=1, revision="A", quoted_hours=Decimal("10"),
        estimated_cost=Decimal("0"), quoted_revenue=Decimal(revenue), margin=Decimal("0"), margin_percent=Decimal("0"),
        base_estimated_cost_inr=Decimal("0"), base_quoted_revenue_inr=Decimal(base_inr or revenue),
        fx_rate=Decimal("1"), fx_date=date(2025, 1, 1),
    ))
    session.flush()
    return quote


def _invoice(session, quote: Quote, amount: str, on: date, due: date | None = None) -> None:
    from app.models.finance import QuoteInvoiceLine

    session.add(QuoteInvoiceLine(quote_id=quote.id, amount=Decimal(amount), line_date=on, due_date=due))
    session.flush()


def _payment(session, quote: Quote, amount: str, on: date) -> None:
    session.add(QuotePaymentLine(quote_id=quote.id, amount=Decimal(amount), line_date=on))
    session.flush()


def _seed_finance(session):
    """Customer A: repeat (first invoiced in FY24). Customer B: new, billed in USD at 80 INR."""
    a, b = _customer(session, "Alpha Tooling"), _customer(session, "Beta Molds")
    qa = _quote(session, a.id, revenue="1000", quoted=date(2024, 11, 1))
    _invoice(session, qa, "300", date(2024, 12, 10))
    _invoice(session, qa, "400", date(2025, 6, 10), due=date(2025, 7, 10))
    _payment(session, qa, "250", date(2025, 7, 1))
    qb = _quote(session, b.id, revenue="10", base_inr="800", currency="USD", quoted=date(2025, 7, 15))
    _invoice(session, qb, "10", date(2025, 8, 1))
    inactive = _quote(session, a.id, revenue="5000", quoted=date(2025, 5, 1), active=False)
    _invoice(session, inactive, "5000", date(2025, 5, 2))
    session.commit()
    return a, b, qa, qb


# ----------------------------------------------------------------- 1: financial-year filters


def test_financial_year_and_sub_periods_follow_april_to_march():
    assert (FY25.start, FY25.end) == (date(2025, 4, 1), date(2026, 3, 31))
    assert "2025" in FY25.label
    q4 = sub_period(2025, 4, "quarterly", 4)
    assert (q4.start, q4.end) == (date(2026, 1, 1), date(2026, 3, 31))
    m12 = sub_period(2025, 4, "monthly", 12)
    assert (m12.start, m12.end) == (date(2026, 3, 1), date(2026, 3, 31))
    assert len(FY25.months()) == 12 and FY25.months()[0][0] == date(2025, 4, 1)
    prev = q4.previous()
    assert prev.end == date(2025, 12, 31) and (prev.end - prev.start) == (q4.end - q4.start)
    with pytest.raises(ValueError):
        sub_period(2025, 4, "quarterly", 5)
    with pytest.raises(ValueError):
        sub_period(2025, 4, "weekly", 1)


def test_resolve_period_uses_company_fy_and_custom_range(session):
    fy = resolve_period(session, fy_start_year=2025)
    assert (fy.start, fy.end, fy.fy_start_year) == (date(2025, 4, 1), date(2026, 3, 31), 2025)
    current = resolve_period(session, today=date(2026, 2, 1))
    assert current.start == date(2025, 4, 1)  # February belongs to the FY that started in April
    custom = resolve_period(session, start=date(2025, 6, 1), end=date(2025, 6, 30))
    assert (custom.start, custom.end) == (date(2025, 6, 1), date(2025, 6, 30))
    with pytest.raises(ValueError):
        resolve_period(session, start=date(2025, 7, 1), end=date(2025, 6, 1))


# ----------------------------------------------------------------- 2: revenue vs collections vs awarded


def test_business_keeps_awarded_invoiced_collected_and_outstanding_apart(session):
    a, b, qa, qb = _seed_finance(session)
    access = _admin(session)
    body = build_business(session, access, CockpitFilters(FY25), TODAY)
    assert body["visible"] is True
    assert _kpi(body, "invoiced_revenue")["value"] == 1200  # 400 INR + 10 USD x 80; inactive quote ignored
    assert _kpi(body, "collections")["value"] == 250  # payment date, never the invoice
    assert _kpi(body, "awarded_value")["value"] == 800  # only quote B was quoted in FY25
    assert _kpi(body, "fy_invoiced_revenue")["value"] == 1200
    expected_outstanding = sum(
        Decimal(str(summarize_quote_cash(session, q)["balance_due"])) * fx for q, fx in ((qa, 1), (qb, 80))
    )
    assert Decimal(str(_kpi(body, "outstanding_receivables")["value"])) == expected_outstanding
    months = {m["month"]: m for m in body["monthly"]}
    assert months["Jun 2025"]["invoiced"] == 400 and months["Jun 2025"]["collected"] == 0
    assert months["Jul 2025"]["collected"] == 250 and months["Jul 2025"]["invoiced"] == 0
    assert months["Aug 2025"]["invoiced"] == 800
    assert {k["kind"] for k in body["kpis"]} == {"actual"}


def test_customer_contribution_and_new_vs_repeat(session):
    a, b, _, _ = _seed_finance(session)
    body = build_business(session, _admin(session), CockpitFilters(FY25), TODAY)
    rows = {r["customer"]: r for r in body["customers"]}
    assert rows["Beta Molds"]["share_percent"] == pytest.approx(66.67)
    assert rows["Alpha Tooling"]["share_percent"] == pytest.approx(33.33)
    assert rows["Beta Molds"]["segment"] == "new"
    assert rows["Alpha Tooling"]["segment"] == "repeat"
    assert body["customers"][0]["customer"] == "Beta Molds"
    # Invoice history starts Dec 2024, less than a year before the period: limited, not established.
    assert body["new_vs_repeat"]["status"] == "limited"
    assert _kpi(body, "repeat_revenue_share")["status"] == "limited"
    only_a = build_business(session, _admin(session), CockpitFilters(FY25, customer_id=a.id), TODAY)
    assert _kpi(only_a, "invoiced_revenue")["value"] == 400


def test_payment_lead_time_uses_fully_paid_lines(session):
    _, _, qa, _ = _seed_finance(session)
    body = build_business(session, _admin(session), CockpitFilters(FY25), TODAY)
    lead = _kpi(body, "payment_lead_days")
    # 250 paid on 1 Jul goes to the older 300 line first (FIFO): no line is fully paid yet.
    assert lead["sample"] == 0 and lead["value"] is None and lead["status"] == "unavailable"
    _payment(session, qa, "450", date(2025, 7, 20))
    session.commit()
    body = build_business(session, _admin(session), CockpitFilters(FY25), TODAY)
    lead = _kpi(body, "payment_lead_days")
    # Both lines settle on 20 Jul: 222 days after 10 Dec 2024 and 40 days after 10 Jun 2025.
    assert lead["sample"] == 2 and lead["value"] == 131


# ----------------------------------------------------------------- 3 + 5: completed vs active, actual hours


def test_operations_separate_completed_and_active_projects(session):
    done = _completed(session, "MG-DONE", completed=datetime(2025, 5, 5, 10))
    done.quoted_hours = Decimal("120")
    _staged(session, done, {ProjectStage.preliminary: "100"}, {ProjectStage.preliminary: "50"})
    late = _project(session, quoted="10", code="MG-LATE")
    late.due_date = TODAY - timedelta(days=3)
    old = _completed(session, "MG-OLD", completed=datetime(2024, 5, 5, 10))  # before FY25
    session.commit()
    body = build_operations(session, _admin(session), CockpitFilters(FY25), TODAY)
    assert body["completed"]["projects"] == 1
    hours = body["completed"]["hours"]
    assert hours["approved_estimate_hours"]["value"] == 100
    assert hours["actual_hours"]["value"] == 50
    assert hours["quoted_hours"]["value"] == 120
    assert {h["kind"] for h in (hours["approved_estimate_hours"], hours["actual_hours"])} == {"approved_plan", "actual"}
    active_count = body["active"]["projects"]
    assert active_count >= 2  # seeded project and MG-LATE; completed projects never count as active
    assert body["active"]["overdue"] >= 1
    assert _kpi(body, "active_projects")["value"] == active_count
    assert _kpi(body, "projects_forecast_risk")["kind"] == "forecast"
    assert old.id and late.id


def test_booked_hours_count_only_approved_hours_in_period(session):
    project = _project(session, quoted="40", code="MG-HOURS")
    _book(session, project.id, "16", week_offset=22)  # June 2025, approved
    _book(session, project.id, "8", week_offset=23, status=TimesheetStatus.draft)  # never counted
    _book(session, project.id, "4", week_offset=0)  # January 2025, outside FY25
    session.commit()
    rows = booked_hours(session, _admin(session), CockpitFilters(FY25), "month")
    assert [(r["key"], r["hours"]) for r in rows] == [("2025-06", 16)]
    stage = booked_hours(session, _admin(session), CockpitFilters(FY25), "stage")
    assert sum(r["hours"] for r in stage) == 16


# ----------------------------------------------------------------- 6: capacity


def test_capacity_uses_personal_hours_holidays_and_skips_virtual_users(session):
    binil = session.get(User, IDS["user_binil"])
    binil.working_hours_per_day = Decimal("6")
    binil.working_days = "Mon,Tue,Wed,Thu,Fri"
    session.commit()
    week = (date(2025, 6, 2), date(2025, 6, 8))
    base = capacity_totals(session, [binil], *week, TODAY)["totals"]
    assert base["available"] == Decimal("30")  # 5 days x 6 h, not 8 h
    session.add(Holiday(name="Test holiday", holiday_date=date(2025, 6, 4)))
    session.commit()
    after = capacity_totals(session, [binil], *week, TODAY)
    assert after["totals"]["available"] == Decimal("24") and after["totals"]["holiday"] == Decimal("6")

    filters = CockpitFilters(resolve_period(session, start=week[0], end=week[1]))
    before = _kpi(build_workforce(session, _admin(session), filters, TODAY), "active_employees")["value"]
    session.add(User(id=uuid.uuid4(), email="shared-cad@prosohm.com", password_hash="x", first_name="Shared",
                     last_name="CAD", is_active=True, user_type=UserType.virtual, role_id=IDS["role_designer"]))
    session.commit()
    body = build_workforce(session, _admin(session), filters, TODAY)
    assert _kpi(body, "active_employees")["value"] == before
    assert _kpi(body, "allocated_capacity")["status"] == "unavailable"
    assert _kpi(body, "approved_remaining_hours")["kind"] == "approved_plan"
    assert body["bottlenecks"]["kind"] == "forecast"


# ----------------------------------------------------------------- 4: customer intelligence


def test_customer_table_and_profile(session):
    _seed_finance(session)
    done = _completed(session, "MG-CUST", completed=datetime(2025, 9, 1, 10))
    done.project_classification = ProjectClassification.small_task
    session.commit()
    access = _admin(session)
    table = build_customer_table(session, access, CockpitFilters(FY25), TODAY)
    rows = {r["customer"]: r for r in table["rows"]}
    assert rows["Beta Molds"]["invoiced"] == 800
    assert rows["Prosohm Test Customer"]["completed_in_period"] == 1
    assert table["finance_visible"] is True

    profile = build_customer_profile(session, access, CockpitFilters(FY25), IDS["customer"], TODAY)
    assert profile["contacts"][0]["name"] == "Steve Johnson"
    assert [p["code"] for p in profile["projects"]["completed_in_period"]] == ["MG-CUST"]
    assert profile["projects"]["by_classification"].get("small_task") == 1
    assert profile["forecasts"]["kind"] == "forecast"
    assert all(s["observed"] for s in profile["signals"])
    assert {n["code"] for n in profile["not_assessable"]} >= {"repeated_delays", "estimate_overruns"}
    assert "profit" in " ".join(profile["notes"]).lower()


def test_customer_profile_hides_finance_and_out_of_scope_customers(session):
    a, *_ = _seed_finance(session)
    leader = resolve_access(session, session.get(User, IDS["user_anurag"]))
    assert leader.finance is False
    table = build_customer_table(session, leader, CockpitFilters(FY25), TODAY)
    assert table["finance_visible"] is False
    assert all("invoiced" not in r for r in table["rows"])
    with pytest.raises(ManagementForbidden):
        build_customer_profile(session, leader, CockpitFilters(FY25), a.id, TODAY)  # only quotes, no projects


# ----------------------------------------------------------------- efficiency


def test_efficiency_groups_completed_projects_without_ranking_designers(session):
    a = _completed(session, "MG-EA", completed=datetime(2025, 5, 5, 10))
    a.project_classification = ProjectClassification.small_task
    _staged(session, a, {ProjectStage.preliminary: "10"}, {ProjectStage.preliminary: "20"})
    b = _completed(session, "MG-EB", completed=datetime(2025, 11, 5, 10))
    b.project_classification = ProjectClassification.full_design
    _staged(session, b, {ProjectStage.preliminary: "40"}, {ProjectStage.preliminary: "30"})
    session.commit()
    access = _admin(session)
    by_class = build_efficiency(session, access, CockpitFilters(FY25), compare_by="classification", today=TODAY)
    groups = {g["key"]: g for g in by_class["comparison"]}
    assert groups["small_task"]["projects_over_estimate"] == 1
    assert groups["full_design"]["hour_variance_percent"] == -25.0
    quarters = build_efficiency(session, access, CockpitFilters(FY25), compare_by="quarter", today=TODAY)
    assert [g["key"] for g in quarters["comparison"]] == ["2025-Q1", "2025-Q3"]
    assert "designer" not in {d["value"] for d in by_class["dimensions"]}
    assert "performance-review" in by_class["fairness_note"]
    with pytest.raises(ValueError):
        build_efficiency(session, access, CockpitFilters(FY25), compare_by="designer", today=TODAY)


# ----------------------------------------------------------------- 15: permissions (API)


def test_cockpit_requires_reports_access(client):
    designer = login(client, "binil@prosohm.com")
    assert client.get(f"{URL}/cockpit", headers=designer).status_code == 403
    assert client.get(f"{URL}/filters", headers=designer).status_code == 403


def test_cockpit_hides_finance_and_workforce_without_access(client, session):
    _seed_finance(session)
    leader = login(client, "anurag@prosohm.com")
    body = client.get(f"{URL}/cockpit", params={"fy_start_year": 2025}, headers=leader).json()
    assert body["business"] == {"visible": False, "reason": body["business"]["reason"]}
    assert body["workforce"]["visible"] is False
    assert body["can"]["finance"] is False
    assert not any(d["finance"] for d in body["definitions"])
    assert all("invoiced" not in row for row in body["customers"]["rows"])

    board = login(client, "planning-board@prosohm.com")
    body = client.get(f"{URL}/cockpit", params={"fy_start_year": 2025}, headers=board).json()
    assert body["business"]["visible"] is False and body["workforce"]["visible"] is True

    admin = client.get(f"{URL}/cockpit", params={"fy_start_year": 2025}, headers=client.auth_headers).json()
    assert admin["business"]["visible"] is True
    assert _kpi(admin["business"], "invoiced_revenue")["value"] == 1200
    assert admin["filters"]["period"]["start"] == "2025-04-01"


def test_filter_validation_and_options(client, session):
    ok = client.get(f"{URL}/filters", headers=client.auth_headers).json()
    assert ok["fy_start_month"] == 4
    assert ok["business_unit_supported"] is False
    assert "design leader" in ok["project_manager_basis"]
    bad = client.get(f"{URL}/cockpit", params={"classification": "nope"}, headers=client.auth_headers)
    assert bad.status_code == 422
    bad = client.get(f"{URL}/cockpit", params={"start_date": "2025-07-01", "end_date": "2025-06-01"},
                     headers=client.auth_headers)
    assert bad.status_code == 422
    assert client.get(f"{URL}/efficiency", params={"compare_by": "designer"},
                      headers=client.auth_headers).status_code == 422
    customer = client.get(f"{URL}/customers/{IDS['customer']}", params={"fy_start_year": 2025},
                          headers=client.auth_headers)
    assert customer.status_code == 200, customer.text
    assert customer.json()["customer"]["name"] == "Prosohm Test Customer"
    assert client.get(f"{URL}/customers/{uuid.uuid4()}", headers=client.auth_headers).status_code == 403


def test_build_filters_rejects_unknown_values(session):
    access = _admin(session)
    with pytest.raises(ValueError):
        build_filters(session, access, period=FY25, customer_id=uuid.uuid4())
    with pytest.raises(ValueError):
        build_filters(session, access, period=FY25, classification="nope")
    f = build_filters(session, access, period=FY25, classification="small_task", customer_id=IDS["customer"])
    assert f.labels["customer"] == "Prosohm Test Customer" and f.narrows_projects
