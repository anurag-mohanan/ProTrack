"""Regression: reject binary stdlib PDF scrape; keep Prosohm field mapping."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.finance.document_import_extract import extract_raw_document_text
from app.services.finance.document_intelligence_service import DocumentIntelligenceService
from app.services.finance.pdf_text_quality import is_usable_pdf_text
from app.services.workorder_pdf_extract import _extract_text_stdlib, extract_pdf_text

ROOT = Path(__file__).resolve().parents[1]
INVOICE = ROOT / "tests" / "fixtures" / "invoices" / "INV-2026-27-051.pdf"
QUOTE = ROOT / "tests" / "fixtures" / "quotes" / "QT-2026-27-036.pdf"


@pytest.mark.skipif(not INVOICE.exists(), reason="invoice fixture missing")
def test_stdlib_scrape_is_not_usable_text():
    blob = INVOICE.read_bytes()
    scraped = _extract_text_stdlib(blob)
    assert len(scraped) > 1000
    assert not is_usable_pdf_text(scraped)


@pytest.mark.skipif(not INVOICE.exists(), reason="invoice fixture missing")
def test_extract_pdf_text_rejects_stdlib_when_better_libs_missing():
    blob = INVOICE.read_bytes()
    real_import = __import__

    def no_libs(name, *args, **kwargs):
        if name in ("pdfplumber", "pypdf") or (
            isinstance(name, str)
            and (name.startswith("pdfplumber") or name.startswith("pypdf"))
        ):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=no_libs):
        with pytest.raises(Exception):
            extract_pdf_text(blob)
        raw = extract_raw_document_text(blob, document_kind="invoice", filename=INVOICE.name)
    assert raw.character_count == 0 or not raw.expected_keywords_found
    assert not any("labels were not found" in w for w in raw.warnings)


@pytest.mark.skipif(not INVOICE.exists(), reason="invoice fixture missing")
def test_invoice_extracts_without_pdfplumber_via_pypdf():
    blob = INVOICE.read_bytes()
    real_import = __import__

    def no_plumber(name, *args, **kwargs):
        if name == "pdfplumber" or (isinstance(name, str) and name.startswith("pdfplumber")):
            raise ImportError("no plumber")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=no_plumber):
        result = DocumentIntelligenceService().analyze_invoice_document(
            blob, filename=INVOICE.name
        )
    fields = result["fields"]
    assert result["extraction_status"] == "READY_FOR_REVIEW"
    assert fields["invoice_number"]["value"] == "INV-2026-27-051"
    assert fields["invoice_date"]["value"] == "2026-09-17"
    assert fields["due_date"]["value"] == "2026-09-17"
    assert fields["payment_terms"]["value"]
    assert fields["sales_person"]["value"] == "Anurag Mohanan"
    assert fields["po_number"]["value"] == "20774"
    assert fields["customer_project_number"]["value"] == "3177"
    assert "B & B" in (fields["customer_name"]["value"] or "")
    assert fields["quantity"]["value"] in ("240.0", "240.00", "240")
    assert fields["rate"]["value"] in ("25.0", "25.00", "25")
    assert fields["amount"]["value"] in ("6000.00", "6000.0", "6,000.00")
    assert not any("filename only" in w for w in result.get("warnings") or [])
    assert not any("labels were not found" in w for w in result.get("warnings") or [])
    assert any("work-breakdown" in w.lower() or "does not match" in w.lower() for w in result.get("warnings") or [])


@pytest.mark.skipif(not QUOTE.exists(), reason="quote fixture missing")
def test_quote_extracts_commercial_qty_separate_from_breakdown():
    blob = QUOTE.read_bytes()
    result = DocumentIntelligenceService().analyze_quote_document(blob, filename=QUOTE.name)
    fields = result["fields"]
    assert fields["quote_number"]["value"] == "QT-2026-27-036"
    assert fields["customer_project_number"]["value"] == "2654"
    qty = fields.get("quantity") or fields.get("raw_table_quantity") or {}
    assert str(qty.get("value") or "").startswith("180")
    assert any(
        "work-breakdown" in w.lower() or "does not match" in w.lower()
        for w in (result.get("warnings") or [])
    ) or float((fields.get("stage_hours_sum") or {}).get("value") or 0) == 280.0
