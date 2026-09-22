"""Awarded quote financial status engine — derived from invoices + payments."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision
from app.models.models import Customer, Team
from app.services.finance.quote_cash_ledger_service import (
    STATUS_FULLY_INVOICED_FULLY_PAID,
    STATUS_FULLY_INVOICED_PAYMENT_PENDING,
    STATUS_NOT_INVOICED,
    STATUS_OVER_INVOICED_REQUIRES_REVIEW,
    STATUS_PARTIALLY_INVOICED_PAID,
    STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING,
    add_invoice_line,
    add_payment_line,
    calculate_awarded_quote_financial_status,
    derive_awarded_quote_financial_status,
)


def test_derive_status_matrix():
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("0"),
            paid_amount=Decimal("0"),
        )
        == STATUS_NOT_INVOICED
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("400000"),
            paid_amount=Decimal("400000"),
        )
        == STATUS_PARTIALLY_INVOICED_PAID
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("400000"),
            paid_amount=Decimal("200000"),
        )
        == STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("1000000"),
            paid_amount=Decimal("0"),
        )
        == STATUS_FULLY_INVOICED_PAYMENT_PENDING
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("1000000"),
            paid_amount=Decimal("600000"),
        )
        == STATUS_FULLY_INVOICED_PAYMENT_PENDING
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("1000000"),
            paid_amount=Decimal("1000000"),
        )
        == STATUS_FULLY_INVOICED_FULLY_PAID
    )
    assert (
        derive_awarded_quote_financial_status(
            awarded_amount=Decimal("1000000"),
            invoiced_amount=Decimal("1100000"),
            paid_amount=Decimal("0"),
        )
        == STATUS_OVER_INVOICED_REQUIRES_REVIEW
    )


def _seed_quote(session, *, awarded: Decimal) -> Quote:
    team = Team(id=uuid.uuid4(), name=f"Fin Status {uuid.uuid4().hex[:6]}", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Status Customer",
        code=f"ST{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"TOOL-{uuid.uuid4().hex[:6]}",
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
            quoted_revenue=awarded,
            margin=awarded,
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=awarded,
            fx_rate=Decimal("1"),
            fx_date=date(2026, 1, 1),
        )
    )
    session.commit()
    return quote


def test_calculate_not_invoiced(session):
    quote = _seed_quote(session, awarded=Decimal("1000000"))
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_NOT_INVOICED
    assert snap["remaining_to_invoice"] == Decimal("1000000")
    assert snap["invoice_percentage"] == Decimal("0")
    assert snap["collection_percentage"] == Decimal("0")


def test_calculate_multi_invoice_partial_payment(session):
    quote = _seed_quote(session, awarded=Decimal("1000000"))
    add_invoice_line(
        session, quote=quote, amount=Decimal("300000"), line_date=date(2026, 2, 1)
    )
    add_invoice_line(
        session, quote=quote, amount=Decimal("200000"), line_date=date(2026, 3, 1)
    )
    add_invoice_line(
        session, quote=quote, amount=Decimal("500000"), line_date=date(2026, 4, 1)
    )
    add_payment_line(
        session, quote=quote, amount=Decimal("500000"), line_date=date(2026, 4, 15)
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_FULLY_INVOICED_PAYMENT_PENDING
    assert snap["invoiced_amount"] == Decimal("1000000")
    assert snap["paid_amount"] == Decimal("500000")
    assert snap["outstanding_amount"] == Decimal("500000")
    assert snap["invoice_percentage"] == Decimal("100.00")
    assert snap["collection_percentage"] == Decimal("50.00")


def test_calculate_partially_invoiced_paid(session):
    quote = _seed_quote(session, awarded=Decimal("1000000"))
    add_invoice_line(
        session, quote=quote, amount=Decimal("400000"), line_date=date(2026, 2, 1)
    )
    add_payment_line(
        session, quote=quote, amount=Decimal("400000"), line_date=date(2026, 2, 10)
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_PARTIALLY_INVOICED_PAID
    assert snap["remaining_to_invoice"] == Decimal("600000")
    assert snap["outstanding_amount"] == Decimal("0")


def test_calculate_partially_invoiced_payment_pending(session):
    quote = _seed_quote(session, awarded=Decimal("1000000"))
    add_invoice_line(
        session, quote=quote, amount=Decimal("500000"), line_date=date(2026, 2, 1)
    )
    add_payment_line(
        session, quote=quote, amount=Decimal("300000"), line_date=date(2026, 2, 10)
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING
    assert snap["outstanding_amount"] == Decimal("200000")
    assert snap["remaining_to_invoice"] == Decimal("500000")


def test_invoice_line_stores_enrichment_fields(session):
    quote = _seed_quote(session, awarded=Decimal("100000"))
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("100000"),
        line_date=date(2026, 5, 1),
        invoice_number="INV-ENRICH-1",
        due_date=date(2026, 6, 1),
        tax_amount=Decimal("18000"),
        subtotal_amount=Decimal("82000"),
        content_sha256="abc123",
    )
    session.commit()
    refreshed = session.get(QuoteInvoiceLine, line.id)
    assert refreshed is not None
    assert refreshed.invoice_number == "INV-ENRICH-1"
    assert refreshed.due_date == date(2026, 6, 1)
    assert refreshed.tax_amount == Decimal("18000")
    assert refreshed.content_sha256 == "abc123"
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_FULLY_INVOICED_PAYMENT_PENDING


def test_payment_allocation_to_invoice_line(session):
    quote = _seed_quote(session, awarded=Decimal("50000"))
    inv = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("50000"),
        line_date=date(2026, 5, 1),
        invoice_number="INV-ALLOC",
    )
    pay = add_payment_line(
        session,
        quote=quote,
        amount=Decimal("20000"),
        line_date=date(2026, 5, 5),
        invoice_line_id=inv.id,
    )
    session.commit()
    refreshed = session.get(QuotePaymentLine, pay.id)
    assert refreshed is not None
    assert refreshed.invoice_line_id == inv.id
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["financial_status"] == STATUS_FULLY_INVOICED_PAYMENT_PENDING
    assert snap["outstanding_amount"] == Decimal("30000")
