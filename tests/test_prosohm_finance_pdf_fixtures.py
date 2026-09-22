"""Acceptance tests for real Prosohm finance PDF fixtures.

QT-2026-27-036 and INV-2026-27-051 are the authoritative document formats.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.finance.invoice_pdf_parser import parse_invoice_pdf_text
from app.services.finance.prosohm_document_intelligence import (
    classify_finance_document,
    detect_hours_discrepancy,
    extract_stage_hours,
)
from app.services.finance.prosohm_quote_pdf_parser import (
    parse_prosohm_quote_pdf,
    parse_prosohm_quote_text,
)
from app.services.workorder_pdf_extract import extract_pdf_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"
QUOTE_PDF = FIXTURES / "quotes" / "QT-2026-27-036.pdf"
INVOICE_PDF = FIXTURES / "invoices" / "INV-2026-27-051.pdf"

pytestmark = pytest.mark.skipif(
    not QUOTE_PDF.exists() or not INVOICE_PDF.exists(),
    reason="Prosohm finance PDF fixtures not present",
)


def test_qt_2026_27_036_fixture_extraction():
    content = QUOTE_PDF.read_bytes()
    extract = parse_prosohm_quote_pdf(content, filename=QUOTE_PDF.name)

    assert extract.external_quote_number == "QT-2026-27-036"
    assert extract.tool_number == "2654"
    assert extract.prepared_for == "Crest Mold"
    assert extract.sales_person == "Anurag Mohanan"
    assert extract.quote_date == "2026-09-03"
    assert extract.quoted_revenue == Decimal("4500.00")
    assert extract.rate == Decimal("25.00")
    assert extract.quoted_hours == Decimal("180.00")
    assert extract.raw_table_quantity == Decimal("180.00")
    assert extract.raw_description_total_hours == Decimal("280")
    assert extract.currency_code == "USD"
    assert extract.payment_terms and "50%" in extract.payment_terms.upper()

    labels = {s.label.upper(): s.hours for s in extract.stage_hours.stages}
    assert labels.get("ROUGHING STAGE DESIGN") == Decimal("40")
    assert labels.get("INTERMEDIATE DESIGN+DOCUMENTATION") == Decimal("100")
    assert labels.get("FINAL DESIGN+BOM+DOCUMENTATION") == Decimal("40")
    assert extract.stage_hours.stage_hours_sum == Decimal("180")

    # Discrepancy must be flagged — never silently pick 180 or 280.
    assert any("DATA REVIEW REQUIRED" in w for w in extract.warnings)
    assert any("280" in w for w in extract.warnings)
    assert extract.confirmed_quoted_hours is None

    text = extract_pdf_text(content)
    classification = classify_finance_document(text=text, filename=QUOTE_PDF.name)
    assert classification.document_type == "quote"
    assert classification.confidence >= 80


def test_qt_036_discrepancy_helpers_do_not_auto_correct():
    text = extract_pdf_text(QUOTE_PDF.read_bytes())
    stages = extract_stage_hours(text)
    warnings = detect_hours_discrepancy(
        table_quantity=Decimal("180"),
        stages=stages,
    )
    assert stages.description_total_hours == Decimal("280")
    assert stages.stage_hours_sum == Decimal("180")
    assert len(warnings) >= 1
    # Parser still keeps table quantity as commercial hours candidate.
    parsed = parse_prosohm_quote_text(text, filename=QUOTE_PDF.name)
    assert parsed.quoted_hours == Decimal("180.00")
    assert parsed.raw_description_total_hours == Decimal("280")


def test_inv_2026_27_051_fixture_extraction():
    content = INVOICE_PDF.read_bytes()
    text = extract_pdf_text(content)
    result = parse_invoice_pdf_text(text, filename=INVOICE_PDF.name)

    assert result.invoice_number.value == "INV-2026-27-051"
    assert result.invoice_date.value == "2026-09-17"
    assert result.project_ref.value == "3177"
    assert result.customer_name.value == "B & B Tool & Mould Ltd."
    assert result.po_number.value == "20774"
    assert result.amount.value == "6000.00"
    assert result.balance_due.value == "6000.00"
    assert result.subtotal.value == "6000.00"
    assert result.tax_amount.value == "0.00"
    assert result.payment_terms.value and "Due on Receipt" in result.payment_terms.value
    assert result.quantity.value == "240.00"
    assert result.rate.value == "25.00"
    assert result.raw_table_quantity.value == "240.00"
    assert result.raw_description_total_hours.value == "320"
    assert result.stage_hours_sum.value == "320"
    assert result.currency_code.value == "USD"

    stage_labels = {s["label"].upper(): s["hours"] for s in result.stage_hours}
    assert stage_labels.get("FEASE") == 10.0
    assert stage_labels.get("BLOCKOUT DESIGN+DOCUMENTATION") == 50.0
    assert stage_labels.get("INTERMEDIATE DESIGN+DOCUMENTATION") == 180.0
    assert stage_labels.get("FINAL DESIGN+DOCUMENTATION+BOM") == 80.0

    assert any("DATA REVIEW REQUIRED" in w for w in result.warnings)
    assert any("240" in w and "320" in w for w in result.warnings)

    # Never fabricate a payment from Balance Due — extract only.
    assert result.balance_due.value == "6000.00"
    assert result.document_type == "invoice"
    assert result.document_type_confidence >= 80

    classification = classify_finance_document(text=text, filename=INVOICE_PDF.name)
    assert classification.document_type == "invoice"


def test_classification_does_not_rely_on_filename_alone():
    qt_text = extract_pdf_text(QUOTE_PDF.read_bytes())
    inv_text = extract_pdf_text(INVOICE_PDF.read_bytes())

    qt = classify_finance_document(text=qt_text, filename="scan.pdf")
    inv = classify_finance_document(text=inv_text, filename="scan.pdf")
    assert qt.document_type == "quote"
    assert inv.document_type == "invoice"
