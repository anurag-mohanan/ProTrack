"""L1 tests for Excel/PDF import format policy and PDF table import."""

from __future__ import annotations

from io import BytesIO

import pytest

from app.core.exceptions import ProTrackValidationError
from app.services.import_file_formats import (
    DEFAULT_IMPORT_EXTENSIONS,
    assert_supported_suffix,
    normalize_import_bytes,
    with_csv,
)
from app.services.pdf_table_import import (
    extract_tables_as_dicts,
    pdf_content_to_xlsx_bytes,
)


def test_default_extensions_include_excel_and_pdf():
    assert ".xlsx" in DEFAULT_IMPORT_EXTENSIONS
    assert ".xlsm" in DEFAULT_IMPORT_EXTENSIONS
    assert ".pdf" in DEFAULT_IMPORT_EXTENSIONS
    assert ".csv" not in DEFAULT_IMPORT_EXTENSIONS
    assert ".csv" in with_csv()


def test_assert_supported_suffix_rejects_unknown():
    with pytest.raises(ValueError, match="Unsupported file type"):
        assert_supported_suffix("notes.txt", allowed=DEFAULT_IMPORT_EXTENSIONS)


def test_assert_supported_suffix_accepts_pdf_and_excel():
    assert assert_supported_suffix("a.xlsx") == ".xlsx"
    assert assert_supported_suffix("b.PDF") == ".pdf"


def test_extract_tables_as_dicts_from_matrix(monkeypatch):
    monkeypatch.setattr(
        "app.services.pdf_table_import.extract_tables_as_matrix",
        lambda _content: [
            ["Customer", "Tool Number", "Quoted Hours", "Estimated Cost", "Quoted Revenue", "Currency"],
            ["Acme", "T-100", "10", "100", "250", "USD"],
        ],
    )
    rows = extract_tables_as_dicts(b"%PDF-fake")
    assert len(rows) == 1
    assert rows[0]["Customer"] == "Acme"
    assert rows[0]["Tool Number"] == "T-100"


def test_pdf_content_to_xlsx_bytes(monkeypatch):
    monkeypatch.setattr(
        "app.services.pdf_table_import.extract_tables_as_matrix",
        lambda _content: [
            ["Customer", "Tool Number"],
            ["Acme", "T-1"],
        ],
    )
    raw = pdf_content_to_xlsx_bytes(b"%PDF-fake")
    assert raw[:2] == b"PK"  # zip/xlsx signature


def test_normalize_import_bytes_preserves_folder_path(monkeypatch):
    monkeypatch.setattr(
        "app.services.pdf_table_import.extract_tables_as_matrix",
        lambda _content: [["A", "B"], ["1", "2"]],
    )
    name, content = normalize_import_bytes("DesignerA/Jun-26.pdf", b"%PDF-fake")
    assert name == "DesignerA/Jun-26.xlsx"
    assert content[:2] == b"PK"


def test_normalize_import_bytes_passes_excel_through():
    payload = b"excel-bytes"
    name, content = normalize_import_bytes("book.xlsx", payload)
    assert name == "book.xlsx"
    assert content == payload


def test_quote_import_from_pdf(client, auth_headers, monkeypatch, session):
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
    from app.models.models import Customer
    from app.services.finance import quote_import_service

    customer = session.query(Customer).filter(Customer.is_active.is_(True)).first()
    assert customer is not None
    team = ensure_corporate_shared_services_team(session)
    session.commit()

    monkeypatch.setattr(
        "app.services.pdf_table_import.extract_tables_as_matrix",
        lambda _content: [
            [
                "Customer",
                "Tool Number",
                "Quoted Hours",
                "Estimated Cost",
                "Quoted Revenue",
                "Currency",
                "Version",
                "Revision",
            ],
            [
                customer.name,
                "PDF-QUOTE-1",
                "12",
                "500",
                "1200",
                "USD",
                "1",
                "A",
            ],
        ],
    )

    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id)},
        files={"file": ("quotes.pdf", BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported_count"] == 1
    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    ).json()
    match = next((q for q in listed if q["tool_number"] == "PDF-QUOTE-1"), None)
    assert match is not None
    assert match["team_id"] == str(team.id)


def test_quote_import_requires_team(client, auth_headers):
    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        files={"file": ("quotes.csv", BytesIO(b"Customer,Tool Number\nAcme,T1"), "text/csv")},
    )
    assert response.status_code in (400, 422)


def test_quote_import_rejects_legacy_xls(client, auth_headers, session):
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team

    team = ensure_corporate_shared_services_team(session)
    session.commit()
    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id)},
        files={"file": ("old.xls", BytesIO(b"not-excel"), "application/vnd.ms-excel")},
    )
    assert response.status_code == 400
    assert "xls" in response.json()["detail"].lower()

def test_empty_pdf_raises(monkeypatch):
    def _boom(_content: bytes):
        raise ProTrackValidationError("No usable table found in PDF.")

    monkeypatch.setattr(
        "app.services.pdf_table_import.extract_tables_as_matrix",
        _boom,
    )
    with pytest.raises(ProTrackValidationError, match="No usable table"):
        extract_tables_as_dicts(b"%PDF-fake")
