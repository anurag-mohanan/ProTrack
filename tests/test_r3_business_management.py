"""R3 business management — billing readiness + ERP export smoke tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.finance import Expense, Quote
from app.models.models import Customer, Team
from app.services.finance.billing_readiness_service import (
    quote_billing_gaps,
    quote_billing_ready,
)
from app.services.finance.erp_export_service import build_erp_journal_csv


def test_quote_billing_gaps_for_incomplete_quote():
    quote = Quote(
        id=uuid4(),
        customer_id=uuid4(),
        team_id=None,
        project_id=None,
        tool_number="T-1",
        currency_code="",
        quoted_date=None,
        is_invoiced=True,
        invoiced_date=None,
        current_version=1,
        current_revision="A",
        is_active=True,
    )
    gaps = quote_billing_gaps(quote)
    assert "team" in gaps
    assert "project_link" in gaps
    assert "currency" in gaps
    assert "quoted_date" in gaps
    assert "invoiced_date" in gaps
    assert quote_billing_ready(quote) is False


def test_quote_billing_ready_when_complete():
    quote = Quote(
        id=uuid4(),
        customer_id=uuid4(),
        team_id=uuid4(),
        project_id=uuid4(),
        tool_number="T-2",
        currency_code="INR",
        quoted_date=date(2026, 1, 10),
        is_invoiced=False,
        invoiced_date=None,
        current_version=1,
        current_revision="A",
        is_active=True,
    )
    assert quote_billing_gaps(quote) == []
    assert quote_billing_ready(quote) is True


def test_erp_journal_csv_headers(session):
    csv_body = build_erp_journal_csv(session)
    assert "entry_date" in csv_body.splitlines()[0]
    assert "business_unit" in csv_body.splitlines()[0]
