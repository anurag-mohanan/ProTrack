"""End-to-end proof: real Prosohm PDFs → raw text → structured JSON.

Run: pytest tests/test_finance_document_import_e2e.py -q -s
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.finance.deterministic_prosohm_extractor import (
    extract_deterministic_document,
    normalize_pdf_text,
)
from app.services.finance.document_intelligence_service import get_document_intelligence_service
from app.services.workorder_pdf_extract import extract_pdf_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INVOICE = FIXTURES / "invoices" / "INV-2026-27-051.pdf"
QUOTE = FIXTURES / "quotes" / "QT-2026-27-036.pdf"

pytestmark = pytest.mark.skipif(
    not INVOICE.exists() or not QUOTE.exists(),
    reason="Real Prosohm PDF fixtures missing",
)


def _v(fields: dict, key: str):
    f = fields.get(key) or {}
    return f.get("value") if isinstance(f, dict) else None


def test_step1_invoice_raw_text_contains_required_strings():
    text = extract_pdf_text(INVOICE.read_bytes())
    print("\nSTEP 1 INVOICE native text length:", len(text))
    assert len(text) > 500
    required = [
        "INV-2026-27-051",
        "Invoice Date",
        "17 September 2026",
        "Due on Receipt",
        "20774",
        "Anurag Mohanan",
        "Customer Project",
        "3177",
        "B & B Tool",
        "Steve Faust",
        "240.00",
        "25.00",
        "6,000.00",
        "Balance Due",
    ]
    missing = [s for s in required if s.lower() not in text.lower()]
    assert not missing, f"Raw text missing: {missing}"


def test_step2_quote_raw_text_contains_required_strings():
    text = extract_pdf_text(QUOTE.read_bytes())
    print("\nSTEP 2 QUOTE native text length:", len(text))
    assert len(text) > 400
    required = [
        "QT-2026-27-036",
        "03 September 2026",
        "Anurag Mohanan",
        "Customer Project",
        "2654",
        "Crest Mold",
        "Dave Brooks",
        "180.00",
        "25.00",
        "4,500.00",
    ]
    missing = [s for s in required if s.lower() not in text.lower()]
    assert not missing, f"Raw text missing: {missing}"


def test_step3_deterministic_invoice_structured_json():
    text = extract_pdf_text(INVOICE.read_bytes())
    result = extract_deterministic_document(
        text, filename="INV-2026-27-051.pdf", expected_kind="invoice"
    )
    print("\nSTEP 3 DETERMINISTIC INVOICE")
    print(" type=", result.document_type, result.document_type_confidence)
    for k, hit in result.fields.items():
        print(f"  {k}={hit.value}")
    assert result.document_type == "INVOICE"
    assert result.fields["invoice_number"].value == "INV-2026-27-051"
    assert result.fields["invoice_date"].value == "2026-09-17"
    assert result.fields["due_date"].value == "2026-09-17"
    assert "Due on Receipt" in (result.fields["payment_terms"].value or "")
    assert result.fields["sales_person"].value == "Anurag Mohanan"
    assert result.fields["po_number"].value == "20774"
    assert result.fields["customer_project_number"].value == "3177"
    assert "B & B Tool" in (result.fields["customer_name"].value or "")
    assert "Steve" in (result.fields["billing_attention"].value or "")
    assert Decimal(str(result.fields["quantity"].value)) == Decimal("240")
    assert Decimal(str(result.fields["rate"].value)) == Decimal("25")
    assert Decimal(str(result.fields["total"].value)) == Decimal("6000.00")
    assert Decimal(str(result.fields["balance_due"].value)) == Decimal("6000.00")
    assert len(result.work_breakdown) == 4


def test_step4_deterministic_quote_structured_json():
    text = extract_pdf_text(QUOTE.read_bytes())
    result = extract_deterministic_document(
        text, filename="QT-2026-27-036.pdf", expected_kind="quote"
    )
    print("\nSTEP 4 DETERMINISTIC QUOTE")
    for k, hit in result.fields.items():
        print(f"  {k}={hit.value}")
    assert result.document_type == "QUOTE"
    assert result.fields["quote_number"].value == "QT-2026-27-036"
    assert result.fields["quote_date"].value == "2026-09-03"
    assert result.fields["sales_person"].value == "Anurag Mohanan"
    assert result.fields["customer_project_number"].value == "2654"
    assert result.fields["customer_name"].value == "Crest Mold"
    assert "Dave" in (result.fields["customer_contact"].value or "")
    assert Decimal(str(result.fields["quantity"].value)) == Decimal("180")
    assert Decimal(str(result.fields["rate"].value)) == Decimal("25")
    assert Decimal(str(result.fields["total"].value)) == Decimal("4500.00")
    assert len(result.work_breakdown) == 3


def test_step5_document_intelligence_service_invoice():
    svc = get_document_intelligence_service()
    result = svc.analyze_invoice_document(
        INVOICE.read_bytes(), filename="INV-2026-27-051.pdf"
    )
    print("\nSTEP 5 INTELLIGENCE INVOICE")
    print(" pipeline=", result.get("pipeline"))
    print(" method=", result.get("text_extraction_method"))
    print(" type=", result.get("document_type"), result.get("document_type_confidence"))
    print(" status=", result.get("extraction_status"))
    fields = result["fields"]
    for key in (
        "invoice_number",
        "invoice_date",
        "due_date",
        "payment_terms",
        "sales_person",
        "po_number",
        "customer_project_number",
        "customer_name",
        "quantity",
        "rate",
        "subtotal",
        "tax_amount",
        "amount",
        "balance_due",
    ):
        print(f"  {key}={_v(fields, key)}")
    assert result["pipeline"] == "document_intelligence_v2"
    assert result["document_type"] == "invoice"
    assert result["document_type_confidence"] >= 90
    assert result["extraction_status"] == "READY_FOR_REVIEW"
    assert _v(fields, "invoice_number") == "INV-2026-27-051"
    assert _v(fields, "invoice_date") == "2026-09-17"
    assert _v(fields, "customer_project_number") == "3177"
    assert Decimal(str(_v(fields, "amount"))) == Decimal("6000.00")
    assert Decimal(str(_v(fields, "balance_due"))) == Decimal("6000.00")
    assert len(result["stage_hours"]) == 4


def test_step6_document_intelligence_service_quote():
    svc = get_document_intelligence_service()
    result = svc.analyze_quote_document(
        QUOTE.read_bytes(), filename="QT-2026-27-036_CTM_2654_09-03-2026.pdf"
    )
    print("\nSTEP 6 INTELLIGENCE QUOTE")
    fields = result["fields"]
    for key in (
        "external_quote_number",
        "quoted_date",
        "sales_person",
        "customer_project_number",
        "customer_name",
        "quoted_hours",
        "rate",
        "quoted_revenue",
    ):
        print(f"  {key}={_v(fields, key)}")
    assert result["document_type"] == "quote"
    assert result["extraction_status"] == "READY_FOR_REVIEW"
    assert _v(fields, "external_quote_number") == "QT-2026-27-036"
    assert _v(fields, "customer_project_number") == "2654"
    assert Decimal(str(_v(fields, "quoted_revenue"))) == Decimal("4500.00")
    assert len(result["stage_hours"]) == 3


def test_step7_analyze_api_endpoint(client):
    from tests.conftest import login

    headers = login(client, "admin@prosohm.com")
    with INVOICE.open("rb") as fh:
        response = client.post(
            "/api/v1/finance/document-import/analyze",
            headers=headers,
            data={"document_kind": "invoice"},
            files={"file": ("INV-2026-27-051.pdf", fh, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    print("\nSTEP 7 API analyze invoice")
    print(" pipeline=", body.get("pipeline"))
    print(" type=", body.get("document_type"), body.get("document_type_confidence"))
    print(" fields=", {k: v.get("value") for k, v in body["fields"].items() if v.get("value")})
    assert body["pipeline"] == "document_intelligence_v2"
    assert body["document_type"] == "invoice"
    assert body["fields"]["invoice_number"]["value"] == "INV-2026-27-051"
    assert body["fields"]["invoice_date"]["value"] == "2026-09-17"
    assert body["fields"]["customer_project_number"]["value"] == "3177"
    assert body["fields"]["amount"]["value"] == "6000.00"
    assert body["extraction_status"] == "READY_FOR_REVIEW"


def test_step8_extract_invoice_api_matches_frontend_contract(client):
    from tests.conftest import login

    headers = login(client, "admin@prosohm.com")
    with INVOICE.open("rb") as fh:
        response = client.post(
            "/api/v1/finance/invoices/pdf/extract",
            headers=headers,
            files={"file": ("INV-2026-27-051.pdf", fh, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    print("\nSTEP 8 invoices/pdf/extract response keys:", sorted(body.keys()))
    assert body.get("pipeline") == "document_intelligence_v2"
    assert body["document_type"] == "invoice"
    assert body["document_type_confidence"] >= 90
    assert body["fields"]["invoice_number"]["value"] == "INV-2026-27-051"
    assert body["fields"]["invoice_date"]["value"] == "2026-09-17"
    assert body["fields"]["due_date"]["value"] == "2026-09-17"
    assert body["fields"]["payment_terms"]["value"]
    assert body["fields"]["sales_person"]["value"] == "Anurag Mohanan"
    assert body["fields"]["po_number"]["value"] == "20774"
    assert body["fields"]["customer_project_number"]["value"] == "3177"
    assert body["fields"]["customer_name"]["value"]
    assert body["fields"]["amount"]["value"] == "6000.00"
    assert body["fields"]["balance_due"]["value"] == "6000.00"
    assert body["fields"]["quantity"]["value"]
    assert body["fields"]["rate"]["value"]
    assert len(body["stage_hours"]) == 4
    # Must NOT be the old filename-only / unknown path
    assert "unknown" not in str(body["document_type"]).lower() or body["document_type_confidence"] > 50
    assert "guessed from filename" not in " ".join(body.get("warnings") or []).lower()


def test_normalize_preserves_labels():
    raw = "Invoice\u00a0#\tINV-1\nCustomer  Project  # :  99"
    norm = normalize_pdf_text(raw)
    assert "Invoice #" in norm or "Invoice #" in normalize_pdf_text(raw.replace("\u00a0", " "))
    assert "Customer Project #" in norm
