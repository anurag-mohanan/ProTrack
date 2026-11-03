"""Phase 8 Stage 8: management Excel exports use the screen's filters, permissions and redaction."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from uuid import UUID

from openpyxl import load_workbook
from sqlalchemy import select

from app.models.enums import ActivityAction
from app.models.models import Activity, User
from app.services.management.access import resolve_access
from app.services.management.exports import build_export
from app.services.management.filters import build_filters, fy_period
from tests.conftest import IDS, login
from tests.test_management_cockpit import _seed_finance
from tests.test_management_objectives import _create
from tests.test_management_reviews import _review

URL = "/api/v1/management"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cells(content: bytes) -> dict[str, list]:
    book = load_workbook(BytesIO(content))
    return {sheet.title: [c for row in sheet.iter_rows(values_only=True) for c in row if c is not None]
            for sheet in book.worksheets}


def _export(client, report, headers=None, expect=200, **params):
    response = client.get(f"{URL}/exports/{report}.xlsx", params=params, headers=headers or client.auth_headers)
    assert response.status_code == expect, response.text
    return response


def test_fy_performance_export_matches_filtered_cockpit_and_is_audited(client, session):
    a, _, _, _ = _seed_finance(session)
    params = {"fy_start_year": 2025, "customer_id": str(a.id)}
    response = _export(client, "fy-performance", **params)
    assert response.headers["content-type"] == XLSX
    assert "Management_fy_performance_20250401-20260331.xlsx" in response.headers["content-disposition"]
    cells = _cells(response.content)["FY performance"]
    assert "Alpha Tooling" in cells and "Beta Molds" not in cells  # same customer filter as the screen

    business = client.get(f"{URL}/cockpit", params=params, headers=client.auth_headers).json()["business"]
    invoiced = next(k for k in business["kpis"] if k["key"] == "invoiced_revenue")["value"]
    assert invoiced == 400 and 400 in cells and "Actual" in cells

    log = session.scalars(select(Activity).where(Activity.action == ActivityAction.data_exported)
                          .order_by(Activity.created_at.desc())).first()
    assert log is not None and "management-fy-performance" in str(log.new_value)
    assert str(a.id) in str(log.new_value)


def test_every_report_builds_for_an_administrator(client, session):
    _seed_finance(session)
    _create(client)
    review = _review(client)
    for report in ("fy-performance", "customer-contribution", "delivery", "efficiency", "utilisation", "objectives",
                   "actions"):
        assert _cells(_export(client, report, fy_start_year=2025).content), report
    assert _cells(_export(client, "review", review_id=review["id"]).content)
    customers = _cells(_export(client, "customer-contribution", fy_start_year=2025).content)["Customers"]
    assert "Alpha Tooling" in customers and "Beta Molds" in customers


def test_exports_enforce_export_finance_and_review_permissions(client, session):
    _seed_finance(session)
    for email in ("readonly@prosohm.com", "planning-board@prosohm.com"):  # no export_reports
        _export(client, "delivery", headers=login(client, email), expect=403, fy_start_year=2025)
    _export(client, "delivery", headers=login(client, "binil@prosohm.com"), expect=403)  # no Reports module

    leader = login(client, "anurag@prosohm.com")  # export, but no Finance, workforce or review scope
    _export(client, "delivery", headers=leader, fy_start_year=2025)
    _export(client, "efficiency", headers=leader, fy_start_year=2025, compare_by="quarter")
    for report in ("fy-performance", "customer-contribution", "utilisation"):
        _export(client, report, headers=leader, expect=403, fy_start_year=2025)
    review = _review(client)
    _export(client, "review", headers=leader, expect=403, review_id=review["id"])

    _export(client, "unknown", expect=404)
    _export(client, "review", expect=422)
    _export(client, "efficiency", expect=422, compare_by="designer")  # no per-designer ranking


def test_objectives_export_redacts_finance_values_for_non_finance_users(client, session):
    _seed_finance(session)
    _create(client, baseline_value="500")
    admin_cells = _cells(_export(client, "objectives", fy_start_year=2025).content)["Objectives"]
    assert 2000 in admin_cells and 1200 in admin_cells
    leader_cells = _cells(_export(client, "objectives", headers=login(client, "anurag@prosohm.com"),
                                  fy_start_year=2025).content)["Objectives"]
    assert "Grow invoiced revenue" in leader_cells and "restricted" in leader_cells
    assert 2000 not in leader_cells and 1200 not in leader_cells


def test_review_export_uses_stored_snapshot_with_redaction(client, session):
    _seed_finance(session)
    review = _review(client)
    full = _cells(_export(client, "review", review_id=review["id"]).content)
    assert {"Summary", "Financial", "Delivery", "Forecasts"} <= set(full)
    assert 400 in full["Financial"] and "Forecasts (not actuals)" in full["Forecasts"]

    admin = resolve_access(session, session.get(User, IDS["user_admin"]))
    no_finance = replace(admin, finance=False)
    filters = build_filters(session, no_finance, period=fy_period(2025, 4))
    sheets = {s.name: s for s in build_export(session, no_finance, "review", filters,
                                                           review_id=UUID(review["id"]))}
    assert sheets["Financial"].title == "Financial (restricted)" and not sheets["Financial"].kpis
    assert all("INR" not in str(row) for table in sheets["Summary"].tables for row in table.rows)
