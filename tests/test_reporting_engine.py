"""Tests for the engineering reporting engine."""

from datetime import date

import pytest

from app.services.reporting import reporting_engine


def test_report_catalog_lists_engineering_reports():
    catalog = reporting_engine.catalog()
    ids = {entry.id for entry in catalog.reports}
    assert "monthly-engineering" in ids
    assert "designer-productivity" in ids
    assert "tool-hours" in ids
    assert len(catalog.reports) >= 10


def test_build_monthly_engineering_report(session):
    payload = reporting_engine.build_report(
        session,
        report_id="monthly-engineering",
        period_type="monthly",
        anchor=date.today().replace(day=1),
    )
    assert payload.report_id == "monthly-engineering"
    assert payload.executive.kpis
    assert payload.period.period_type == "monthly"
    assert isinstance(payload.designer_productivity, list)
    assert isinstance(payload.tool_hours, list)


def test_export_engineering_excel_bytes(session):
    payload = reporting_engine.build_report(
        session,
        report_id="monthly-engineering",
        period_type="monthly",
        anchor=date.today().replace(day=1),
        ai_insights=["Test insight"],
    )
    content = reporting_engine.export_excel(payload)
    assert isinstance(content, bytes)
    assert content[:2] == b"PK"


def test_unknown_report_raises(session):
    with pytest.raises(KeyError):
        reporting_engine.build_report(session, report_id="does-not-exist")


def test_engineering_report_api_catalog(client, auth_headers):
    response = client.get("/api/v1/reports/catalog", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert any(report["id"] == "monthly-engineering" for report in body["reports"])


def test_engineering_report_api_preview(client, auth_headers):
    response = client.get(
        "/api/v1/reports/engine/monthly-engineering/preview",
        headers=auth_headers,
        params={"period_type": "monthly"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_id"] == "monthly-engineering"
    assert "executive" in body
    assert "designer_productivity" in body


def test_engineering_report_api_excel_export(client, auth_headers):
    response = client.get(
        "/api/v1/reports/engine/monthly-engineering/export.xlsx",
        headers=auth_headers,
        params={"period_type": "monthly"},
    )
    assert response.status_code == 200, response.text
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content[:2] == b"PK"


def test_engineering_report_schedule_stub(client, auth_headers):
    save = client.put(
        "/api/v1/reports/schedules",
        headers=auth_headers,
        json={
            "report_id": "monthly-engineering",
            "period_type": "monthly",
            "frequency": "monthly",
            "enabled": True,
        },
    )
    assert save.status_code == 200
    assert save.json()["enabled"] is True

    listed = client.get("/api/v1/reports/schedules", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["report_id"] == "monthly-engineering" for item in listed.json())
