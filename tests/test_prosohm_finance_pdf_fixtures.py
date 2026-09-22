"""Acceptance tests for visual document intelligence on Prosohm fixtures."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.finance import InvoicePdfExtractResult, QuotePdfExtractResult
from app.services.finance.document_intelligence_service import get_document_intelligence_service
from app.services.finance.invoice_pdf_import_service import extract_invoice_pdf
from app.services.finance.prosohm_layout_analyzer import analyze_prosohm_layout
from app.services.finance.quote_pdf_import_service import extract_quote_pdf

FIXTURES = Path(__file__).resolve().parent / "fixtures"
QUOTE_PDF = FIXTURES / "quotes" / "QT-2026-27-036.pdf"
INVOICE_PDF = FIXTURES / "invoices" / "INV-2026-27-051.pdf"

pytestmark = pytest.mark.skipif(
    not QUOTE_PDF.exists() or not INVOICE_PDF.exists(),
    reason="Prosohm finance PDF fixtures not present",
)


def test_layout_quote_visual_fields():
    layout = analyze_prosohm_layout(
        QUOTE_PDF.read_bytes(),
        filename="QT-2026-27-036_CTM_2654_09-03-2026.pdf",
    )
    assert layout.document_type == "QUOTE"
    assert layout.document_type_confidence >= 0.9
    assert layout.fields["quote_number"].value == "QT-2026-27-036"
    assert layout.fields["quote_date"].value == "2026-09-03"
    assert layout.fields["sales_person"].value == "Anurag Mohanan"
    assert layout.fields["customer_project_number"].value == "2654"
    assert layout.fields["customer_name"].value == "Crest Mold"
    assert "Dave" in (layout.fields["customer_contact"].value or "")
    assert layout.fields["quantity"].value == "180.0"
    assert layout.fields["rate"].value == "25.0"
    assert Decimal(layout.fields["total"].value) == Decimal("4500.00")
    assert len(layout.work_breakdown) == 3
    assert any("280" in w for w in layout.warnings)


def test_layout_invoice_visual_fields():
    layout = analyze_prosohm_layout(
        INVOICE_PDF.read_bytes(),
        filename="INV-2026-27-051.pdf",
    )
    assert layout.document_type == "INVOICE"
    assert layout.document_type_confidence >= 0.9
    assert layout.fields["invoice_number"].value == "INV-2026-27-051"
    assert layout.fields["invoice_date"].value == "2026-09-17"
    assert layout.fields["due_date"].value == "2026-09-17"
    assert "Due on Receipt" in (layout.fields["payment_terms"].value or "")
    assert layout.fields["sales_person"].value == "Anurag Mohanan"
    assert layout.fields["po_number"].value == "20774"
    assert layout.fields["customer_project_number"].value == "3177"
    assert "B & B Tool" in (layout.fields["customer_name"].value or "")
    assert "Steve" in (layout.fields["billing_attention"].value or "")
    assert layout.fields["quantity"].value == "240.0"
    assert layout.fields["rate"].value == "25.0"
    assert Decimal(layout.fields["total"].value) == Decimal("6000.00")
    assert Decimal(layout.fields["balance_due"].value) == Decimal("6000.00")
    assert Decimal(layout.fields["tax"].value) == Decimal("0.00")
    assert len(layout.work_breakdown) == 4


def test_document_intelligence_invoice_ready(session):
    result = extract_invoice_pdf(
        session,
        content=INVOICE_PDF.read_bytes(),
        filename="INV-2026-27-051.pdf",
    )
    validated = InvoicePdfExtractResult.model_validate(result)
    assert validated.document_type == "invoice"
    assert validated.document_type_confidence >= 90
    assert validated.extraction_status == "READY_FOR_REVIEW"
    assert validated.fields["invoice_number"].value == "INV-2026-27-051"
    assert validated.fields["invoice_date"].value == "2026-09-17"
    assert validated.fields["customer_project_number"].value == "3177"
    assert validated.fields["amount"].value == "6000.00"
    assert validated.fields["balance_due"].value == "6000.00"
    assert validated.fields["po_number"].value == "20774"
    assert validated.fields["sales_person"].value == "Anurag Mohanan"
    assert len(validated.stage_hours) == 4
    assert validated.page_preview_data_url
    assert "visual" in (validated.text_extraction_method or "")


def test_document_intelligence_quote_ready(session):
    result = extract_quote_pdf(
        session,
        content=QUOTE_PDF.read_bytes(),
        filename="QT-2026-27-036_CTM_2654_09-03-2026.pdf",
    )
    validated = QuotePdfExtractResult.model_validate(result)
    assert validated.document_type == "quote"
    assert validated.document_type_confidence >= 90
    assert validated.extraction_status == "READY_FOR_REVIEW"
    assert validated.fields["external_quote_number"].value == "QT-2026-27-036"
    assert validated.fields["quoted_date"].value == "2026-09-03"
    assert validated.fields["customer_project_number"].value == "2654"
    assert validated.fields["customer_name"].value == "Crest Mold"
    assert validated.fields["quoted_revenue"].value == "4500.00"
    assert validated.fields["quoted_hours"].value == "180.0"
    assert validated.fields["rate"].value == "25.0"
    assert len(validated.stage_hours) == 3
    assert validated.page_preview_data_url


def test_intelligence_service_direct():
    svc = get_document_intelligence_service()
    inv = svc.analyze_invoice_document(
        INVOICE_PDF.read_bytes(), filename="INV-2026-27-051.pdf"
    )
    assert inv["extraction_status"] == "READY_FOR_REVIEW"
    assert inv["fields"]["invoice_number"]["value"] == "INV-2026-27-051"
    qt = svc.analyze_quote_document(
        QUOTE_PDF.read_bytes(), filename="QT-2026-27-036.pdf"
    )
    assert qt["extraction_status"] == "READY_FOR_REVIEW"
    assert qt["fields"]["quote_number"]["value"] == "QT-2026-27-036"
