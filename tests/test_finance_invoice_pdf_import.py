"""Phase 4 — invoice PDF extract → review → confirm."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import uuid

from app.models.finance import Quote, QuoteInvoiceLine, QuoteRevision
from app.models.models import Customer, Team, User
from app.services.finance.invoice_pdf_import_service import (
    confirm_invoice_pdf_import,
    extract_invoice_pdf,
)
from app.services.finance.invoice_pdf_parser import parse_invoice_pdf_text
from sqlalchemy import select
from tests.conftest import IDS, login


SAMPLE_INVOICE_TEXT = """
TAX INVOICE
Invoice No: INV-2026-0042
Invoice Date: 15/07/2026
Due Date: 14/08/2026
Bill To: Sample Customer Industries
Customer Project # TOOL-7788
PO Number: PO-9911
Quote #: QT-2026-27-100
Sub Total 100000.00
GST 18000.00
Grand Total INR 118000.00
"""


def test_parse_invoice_pdf_text_extracts_core_fields():
    result = parse_invoice_pdf_text(SAMPLE_INVOICE_TEXT, filename="INV-2026-0042.pdf")
    assert result.invoice_number.value == "INV-2026-0042"
    assert result.invoice_number.confidence >= 90
    assert result.invoice_date.value == "2026-07-15"
    assert result.amount.value == "118000.00"
    assert result.customer_name.value
    assert result.project_ref.value == "TOOL-7788"
    assert result.text_extractable is True
    assert result.ocr_used is False


def test_parse_does_not_invent_missing_date():
    result = parse_invoice_pdf_text("Invoice No: INV-1\nTotal 5000", filename="x.pdf")
    assert result.invoice_date.value is None
    assert result.invoice_date.needs_review is True
    assert any("Invoice date not detected" in w for w in result.warnings)


def test_extract_and_confirm_creates_invoice_line(session):
    team = Team(id=uuid.uuid4(), name="Inv PDF Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Sample Customer Industries",
        code=f"SC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number="TOOL-7788",
        external_quote_number="QT-2026-27-100",
        currency_code="INR",
        is_active=True,
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_hours=Decimal("10"),
            estimated_cost=Decimal("0"),
            quoted_revenue=Decimal("118000"),
            margin=Decimal("118000"),
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=Decimal("118000"),
            fx_rate=Decimal("1"),
            fx_date=date(2026, 7, 1),
        )
    )
    session.commit()

    with patch(
        "app.services.finance.invoice_pdf_import_service.extract_pdf_text",
        return_value=SAMPLE_INVOICE_TEXT,
    ):
        extracted = extract_invoice_pdf(
            session,
            content=b"%PDF-fake",
            filename="INV-2026-0042.pdf",
            team_id=team.id,
        )
    assert extracted["fields"]["invoice_number"]["value"] == "INV-2026-0042"
    assert extracted["suggested_quote_id"] == str(quote.id)
    assert extracted["ocr_used"] is False

    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    confirm_invoice_pdf_import(
        session,
        quote_id=quote.id,
        amount=Decimal("118000"),
        line_date=date(2026, 7, 15),
        notes=None,
        invoice_number="INV-2026-0042",
        import_anyway=False,
        content=None,
        filename=None,
        content_sha256=extracted["content_sha256"],
        user=admin,
    )
    lines = list(
        session.scalars(select(QuoteInvoiceLine).where(QuoteInvoiceLine.quote_id == quote.id)).all()
    )
    assert len(lines) == 1
    assert lines[0].amount == Decimal("118000.00")
    assert lines[0].line_date == date(2026, 7, 15)
    assert "INV-2026-0042" in (lines[0].notes or "")
    assert "PDF Import" in (lines[0].notes or "")


def test_duplicate_blocked_without_import_anyway(session):
    team = Team(id=uuid.uuid4(), name="Dup Inv Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Dup Customer",
        code=f"DC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number="DUP-1",
        currency_code="INR",
        is_active=True,
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_hours=Decimal("1"),
            estimated_cost=Decimal("0"),
            quoted_revenue=Decimal("5000"),
            margin=Decimal("5000"),
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=Decimal("5000"),
            fx_rate=Decimal("1"),
            fx_date=date(2026, 7, 1),
        )
    )
    session.add(
        QuoteInvoiceLine(
            quote_id=quote.id,
            amount=Decimal("5000"),
            line_date=date(2026, 7, 1),
            notes="Invoice#: INV-DUP-1 | Source: PDF Import",
        )
    )
    session.commit()

    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    from app.core.exceptions import ProTrackValidationError
    import pytest

    with pytest.raises(ProTrackValidationError, match="duplicate"):
        confirm_invoice_pdf_import(
            session,
            quote_id=quote.id,
            amount=Decimal("5000"),
            line_date=date(2026, 7, 1),
            notes=None,
            invoice_number="INV-DUP-1",
            import_anyway=False,
            content=None,
            filename=None,
            content_sha256=None,
            user=admin,
        )


def test_extract_api_endpoint(client):
    headers = login(client, "admin@prosohm.com")
    with patch(
        "app.services.finance.invoice_pdf_import_service.extract_pdf_text",
        return_value=SAMPLE_INVOICE_TEXT,
    ):
        response = client.post(
            "/api/v1/finance/invoices/pdf/extract",
            headers=headers,
            files={"file": ("inv.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fields"]["invoice_number"]["value"] == "INV-2026-0042"
    assert body["source"] == "pdf_import"
