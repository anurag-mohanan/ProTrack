"""Payment terms + due-date aging + financially closed quote tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Team
from app.services.finance.customer_financial_service import (
    aggregate_customer_financial_summary,
    is_quote_financially_closed,
)
from app.services.finance.payment_terms_service import (
    calculate_due_date,
    normalize_payment_terms,
    payment_timing_status,
    resolve_invoice_payment_terms,
)
from app.services.finance.quote_cash_ledger_service import (
    add_invoice_line,
    add_payment_line,
    calculate_awarded_quote_financial_status,
)
from app.services.finance.receivables_service import build_receivables_aging


def test_normalize_payment_terms_matrix():
    assert normalize_payment_terms("Due on Receipt") == ("Due on Receipt", 0)
    assert normalize_payment_terms("Net 30") == ("Net 30", 30)
    assert normalize_payment_terms("Net 60") == ("Net 60", 60)
    assert normalize_payment_terms("Net 90") == ("Net 90", 90)
    assert normalize_payment_terms("45 Days") == ("Net 45", 45)


def test_calculate_due_dates():
    inv = date(2026, 9, 1)
    assert calculate_due_date(inv, 30) == date(2026, 10, 1)
    assert calculate_due_date(inv, 60) == date(2026, 10, 31)
    assert calculate_due_date(inv, 0) == date(2026, 9, 1)


def test_document_due_date_preserved_with_warning():
    resolved = resolve_invoice_payment_terms(
        document_terms="Net 30",
        document_due_date=date(2026, 10, 5),
        invoice_date=date(2026, 9, 1),
    )
    assert resolved["due_date"] == date(2026, 10, 5)
    assert resolved["payment_terms_days"] == 30
    assert resolved["payment_terms_source"] == "DOCUMENT"
    assert any("Due Date" in w for w in resolved["warnings"])


def test_customer_default_fallback():
    resolved = resolve_invoice_payment_terms(
        document_terms=None,
        document_due_date=None,
        invoice_date=date(2026, 9, 1),
        customer_default_terms="Net 60",
        customer_default_days=60,
    )
    assert resolved["payment_terms_days"] == 60
    assert resolved["payment_terms_source"] == "CUSTOMER_DEFAULT"
    assert resolved["due_date"] == date(2026, 10, 31)
    assert any("Customer default" in w for w in resolved["warnings"])


def test_document_overrides_customer_default():
    resolved = resolve_invoice_payment_terms(
        document_terms="Net 30",
        invoice_date=date(2026, 9, 1),
        customer_default_days=60,
    )
    assert resolved["payment_terms_days"] == 30
    assert resolved["payment_terms_source"] == "DOCUMENT"


def test_payment_timing_not_yet_due_and_overdue():
    today = date(2026, 9, 23)
    ny = payment_timing_status(
        due_date=date(2026, 10, 1),
        outstanding=Decimal("10000"),
        invoiced=Decimal("10000"),
        paid=Decimal("0"),
        today=today,
    )
    assert ny["payment_timing_status"] == "NOT_YET_DUE"
    assert ny["days_overdue"] == 0

    od = payment_timing_status(
        due_date=date(2026, 9, 1),
        outstanding=Decimal("10000"),
        invoiced=Decimal("10000"),
        paid=Decimal("0"),
        today=today,
    )
    assert od["payment_timing_status"] == "OVERDUE"
    assert od["days_overdue"] == 22

    paid = payment_timing_status(
        due_date=date(2026, 9, 1),
        outstanding=Decimal("0"),
        invoiced=Decimal("10000"),
        paid=Decimal("10000"),
        today=today,
    )
    assert paid["payment_timing_status"] == "FULLY_PAID"
    assert paid["days_overdue"] == 0


def _seed(session, *, awarded: Decimal, hours: Decimal = Decimal("180")) -> Quote:
    team = Team(id=uuid.uuid4(), name=f"PT {uuid.uuid4().hex[:6]}", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Terms Customer",
        code=f"TC{uuid.uuid4().hex[:4]}",
        is_active=True,
        default_payment_terms_days=60,
        default_payment_terms="Net 60",
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"TOOL-{uuid.uuid4().hex[:6]}",
        currency_code="USD",
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
            quoted_hours=hours,
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


def test_financially_closed_after_full_invoice_and_payment(session):
    quote = _seed(session, awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("4500"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("180"),
        payment_terms="Net 30",
        payment_terms_days=30,
        payment_terms_source="DOCUMENT",
        due_date=date(2026, 3, 31),
    )
    add_payment_line(session, quote=quote, amount=Decimal("4500"), line_date=date(2026, 3, 20))
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["is_financially_closed"] is True
    assert is_quote_financially_closed(snap) is True


def test_partial_invoice_fully_paid_stays_active(session):
    quote = _seed(session, awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
        due_date=date(2026, 3, 31),
        payment_terms_days=30,
    )
    add_payment_line(session, quote=quote, amount=Decimal("3000"), line_date=date(2026, 3, 15))
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["is_financially_closed"] is False
    assert snap["remaining_to_invoice"] == Decimal("1500")


def test_receivables_ages_by_due_date(session):
    quote = _seed(session, awarded=Decimal("10000"))
    today = date(2026, 9, 23)
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("10000"),
        line_date=date(2026, 9, 1),
        due_date=date(2026, 9, 1),
        payment_terms="Due on Receipt",
        payment_terms_days=0,
        payment_terms_source="DOCUMENT",
    )
    session.commit()
    aging = build_receivables_aging(session, today=today)
    assert aging["overdue"] == Decimal("10000.00")
    assert aging["rows"][0]["days_overdue"] == 22
    assert aging["rows"][0]["payment_timing_status"] == "OVERDUE"


def test_customer_financial_summary(session):
    quote = _seed(session, awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
        due_date=date(2026, 3, 31),
    )
    add_payment_line(session, quote=quote, amount=Decimal("1000"), line_date=date(2026, 3, 10))
    session.commit()
    summary = aggregate_customer_financial_summary(session, customer_id=quote.customer_id)
    assert summary["totals"]["awarded"] == Decimal("4500.00")
    assert summary["totals"]["invoiced"] == Decimal("3000.00")
    assert summary["totals"]["to_be_invoiced"] == Decimal("1500.00")
    assert summary["totals"]["collected"] == Decimal("1000.00")
    assert summary["totals"]["outstanding"] == Decimal("2000.00")
    assert len(summary["quotes"]) == 1


def test_fully_paid_invoice_not_in_overdue(session):
    quote = _seed(session, awarded=Decimal("10000"))
    today = date(2026, 9, 23)
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("10000"),
        line_date=date(2026, 8, 1),
        due_date=date(2026, 9, 1),
        payment_terms_days=30,
    )
    add_payment_line(session, quote=quote, amount=Decimal("10000"), line_date=date(2026, 9, 10))
    session.commit()
    aging = build_receivables_aging(session, today=today)
    assert aging["total_outstanding"] == Decimal("0.00")
    assert aging["overdue"] == Decimal("0.00")
