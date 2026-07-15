"""Prosohm QT PDF quote parser and import."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest

from app.services.finance.prosohm_quote_pdf_parser import (
    looks_like_prosohm_qt_pdf,
    parse_prosohm_quote_text,
)

GOLDEN_QT_TEXT = """
Prosohm Projects (OPC) Private Limited
QUOTE
Quote# : QT-2026-27-001 Sales person : Anurag Mohanan
Quote Date : 10/04/2026 Customer Project # : 17974
Prepared For
Sybridge Technologies Canada Inc-MIS
465, Jutras Dr. S.
Kind Attention: Mr.Girish Ayyar
# Item & Description Qty/Hrs Rate Amount Amount
1 Full Tool Design ( Export) 220.00 28.00 6,160.00 6,160.00
Preliminary Design - 35 hrs.
Intermediate Design - 95 hrs
Final Design - 50 hrs.
Docs, File release, BOM = 40 hrs.
Sub Total 6,160.00 $6,160.00
Total $6,160.00
Total In Words
United States Dollar Six Thousand One Hundred Sixty
"""


def test_looks_like_prosohm_qt_from_filename():
    assert looks_like_prosohm_qt_pdf(filename="QT-2026-27-001-SY#17974.pdf", text="")


def test_looks_like_prosohm_qt_from_text():
    assert looks_like_prosohm_qt_pdf(filename="award.pdf", text=GOLDEN_QT_TEXT)
    assert not looks_like_prosohm_qt_pdf(
        filename="pack.pdf", text="Customer Tool Number Quoted Hours"
    )


def test_parse_prosohm_quote_golden_text():
    extract = parse_prosohm_quote_text(
        GOLDEN_QT_TEXT, filename="QT-2026-27-001-SY#17974.pdf"
    )
    assert extract.external_quote_number == "QT-2026-27-001"
    assert extract.tool_number == "17974"
    assert extract.quote_date == "10/04/2026"
    assert extract.prepared_for == "Sybridge Technologies Canada Inc-MIS"
    assert extract.quoted_hours == Decimal("220.00")
    assert extract.rate == Decimal("28.00")
    assert extract.quoted_revenue == Decimal("6160.00")
    assert extract.currency_code == "USD"
    row = extract.to_import_row()
    assert row["tool_number"] == "17974"
    assert row["external_quote_number"] == "QT-2026-27-001"
    assert row["_soft_customer_match"] is True


def test_parse_uses_filename_tool_hint_when_missing_in_text():
    text = GOLDEN_QT_TEXT.replace("Customer Project # : 17974", "")
    extract = parse_prosohm_quote_text(text, filename="QT-2026-27-001-SY#17974.pdf")
    assert extract.tool_number == "17974"


def test_quote_import_prosohm_qt_creates_and_links_project(
    client, auth_headers, monkeypatch, session
):
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
    from app.models.models import Customer, Project

    customer = Customer(
        name="QT Import Labs Unique Inc",
        code="QTILAB",
        is_active=True,
        default_currency_code="USD",
    )
    session.add(customer)
    team = ensure_corporate_shared_services_team(session)
    session.commit()

    text = GOLDEN_QT_TEXT.replace(
        "Sybridge Technologies Canada Inc-MIS",
        "QT Import Labs Unique Inc-MIS",
    )
    monkeypatch.setattr(
        "app.services.finance.prosohm_quote_pdf_parser.extract_prosohm_quote_text",
        lambda _content: text,
    )

    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id), "create_project": "true"},
        files={
            "file": (
                "QT-2026-27-001-SY#17974.pdf",
                BytesIO(b"%PDF-fake-qt"),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 1
    item = body["items"][0]
    assert item["tool_number"] == "17974"
    assert item["external_quote_number"] == "QT-2026-27-001"
    assert item["project_created"] is True
    assert item["project_linked"] is True
    assert Decimal(str(item["quoted_hours"])) == Decimal("220.00")
    assert Decimal(str(item["quoted_revenue"])) == Decimal("6160.00")
    assert item["currency_code"] == "USD"

    project = (
        session.query(Project)
        .filter(Project.tool_number == "17974", Project.is_deleted.is_(False))
        .one()
    )
    assert project.customer_id == customer.id
    assert project.notes == "created_from_quote_import"

    # Second import with revision B should link the same project (no duplicate).
    def _parse_rev_b(text: str, *, filename: str | None = None):
        extract = parse_prosohm_quote_text(text, filename=filename)
        base_row = extract.to_import_row()
        base_row["revision"] = "B"

        def _row():
            return base_row

        extract.to_import_row = _row  # type: ignore[method-assign]
        return extract

    monkeypatch.setattr(
        "app.services.finance.prosohm_quote_pdf_parser.parse_prosohm_quote_text",
        _parse_rev_b,
    )

    response2 = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id), "create_project": "true"},
        files={
            "file": (
                "QT-2026-27-001-SY#17974.pdf",
                BytesIO(b"%PDF-fake-qt-2"),
                "application/pdf",
            )
        },
    )
    assert response2.status_code == 200, response2.text
    item2 = response2.json()["items"][0]
    assert item2["project_created"] is False
    assert item2["project_linked"] is True
    count = (
        session.query(Project)
        .filter(Project.tool_number == "17974", Project.is_deleted.is_(False))
        .count()
    )
    assert count == 1


def test_quote_import_prosohm_qt_no_create_stays_unlinked(
    client, auth_headers, monkeypatch, session
):
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
    from app.models.models import Customer, Project

    session.add(
        Customer(
            name="QT NoCreate Labs Inc",
            code="QTNCL",
            is_active=True,
            default_currency_code="USD",
        )
    )
    team = ensure_corporate_shared_services_team(session)
    session.commit()

    text = (
        GOLDEN_QT_TEXT.replace("17974", "17999").replace(
            "Sybridge Technologies Canada Inc-MIS",
            "QT NoCreate Labs Inc-MIS",
        )
    )
    monkeypatch.setattr(
        "app.services.finance.prosohm_quote_pdf_parser.extract_prosohm_quote_text",
        lambda _content: text,
    )

    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id), "create_project": "false"},
        files={
            "file": ("QT-2026-27-009.pdf", BytesIO(b"%PDF-fake"), "application/pdf")
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["tool_number"] == "17999"
    assert item["project_linked"] is False
    assert item["project_created"] is False
    assert (
        session.query(Project)
        .filter(Project.tool_number == "17999", Project.is_deleted.is_(False))
        .count()
        == 0
    )


@pytest.mark.skipif(
    not Path(
        r"C:\Users\anumoh\OneDrive - Prosohm Projects (OPC) Pvt Ltd"
        r"\Prosohm Admin's files - Finance\Quotes 26-27"
        r"\QT-2026-27-001-SY#17974.pdf"
    ).exists(),
    reason="Sample Prosohm QT PDF not available on this machine",
)
def test_parse_real_sample_pdf():
    path = Path(
        r"C:\Users\anumoh\OneDrive - Prosohm Projects (OPC) Pvt Ltd"
        r"\Prosohm Admin's files - Finance\Quotes 26-27"
        r"\QT-2026-27-001-SY#17974.pdf"
    )
    from app.services.finance.prosohm_quote_pdf_parser import parse_prosohm_quote_pdf

    extract = parse_prosohm_quote_pdf(path.read_bytes(), filename=path.name)
    assert extract.tool_number == "17974"
    assert extract.quoted_hours == Decimal("220.00")
    assert extract.quoted_revenue == Decimal("6160.00")
