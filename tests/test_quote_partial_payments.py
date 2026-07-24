"""Partial invoice / multi-payment balance tracking for awarded quotes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.db.phase61_quote_partial_payments_schema_sync import backfill_legacy_quote_cash_lines
from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision
from app.models.models import Customer
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash
from app.services.finance.quote_payment_notifier import payment_follow_up_due


def test_fifty_twentyfive_twentyfive_settles(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": "PARTIAL-100",
            "quoted_revenue": "1000.00",
            "external_quote_number": "QT-PARTIAL",
            "currency_code": "USD",
            "create_project": False,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    inv1 = client.post(
        f"/api/v1/finance/quotes/{quote_id}/invoice-lines",
        headers=auth_headers,
        json={"amount": "500.00", "line_date": "2026-06-01", "notes": "50% advance"},
    )
    assert inv1.status_code == 201, inv1.text
    assert Decimal(str(inv1.json()["balance_due"])) == Decimal("500.00")
    assert inv1.json()["is_invoiced"] is True
    assert inv1.json()["invoice_status"] == "partial"
    assert inv1.json()["is_partially_invoiced"] is True

    inv2 = client.post(
        f"/api/v1/finance/quotes/{quote_id}/invoice-lines",
        headers=auth_headers,
        json={"amount": "500.00", "line_date": "2026-07-01", "notes": "50% balance"},
    )
    assert inv2.status_code == 201, inv2.text
    body = inv2.json()
    assert Decimal(str(body["total_invoiced"])) == Decimal("1000.00")
    assert Decimal(str(body["balance_due"])) == Decimal("1000.00")
    assert body["invoice_status"] == "full"
    assert body["is_partially_invoiced"] is False
    assert body["is_invoiced"] is True

    pay1 = client.post(
        f"/api/v1/finance/quotes/{quote_id}/payment-lines",
        headers=auth_headers,
        json={"amount": "500.00", "line_date": "2026-06-15", "reference": "50%"},
    )
    assert pay1.status_code == 201, pay1.text
    assert Decimal(str(pay1.json()["balance_due"])) == Decimal("500.00")

    pay2 = client.post(
        f"/api/v1/finance/quotes/{quote_id}/payment-lines",
        headers=auth_headers,
        json={"amount": "250.00", "line_date": "2026-07-10", "reference": "25%"},
    )
    assert pay2.status_code == 201, pay2.text
    assert Decimal(str(pay2.json()["balance_due"])) == Decimal("250.00")
    assert pay2.json()["is_paid"] is False
    assert pay2.json()["payment_status"] == "partial"
    assert pay2.json()["is_partially_paid"] is True

    pay3 = client.post(
        f"/api/v1/finance/quotes/{quote_id}/payment-lines",
        headers=auth_headers,
        json={"amount": "250.00", "line_date": "2026-07-20", "reference": "25%"},
    )
    assert pay3.status_code == 201, pay3.text
    settled = pay3.json()
    assert Decimal(str(settled["balance_due"])) == Decimal("0")
    assert settled["is_paid"] is True
    assert settled["payment_status"] == "full"
    assert settled["is_partially_paid"] is False
    assert Decimal(str(settled["total_paid"])) == Decimal("1000.00")


def test_cannot_pay_without_invoice(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": "NO-INV-PAY",
            "quoted_revenue": "800.00",
            "currency_code": "USD",
            "create_project": False,
        },
    )
    quote_id = created.json()["items"][0]["quote_id"]
    blocked = client.post(
        f"/api/v1/finance/quotes/{quote_id}/payment-lines",
        headers=auth_headers,
        json={"amount": "100.00", "line_date": "2026-07-01"},
    )
    assert blocked.status_code == 422
    assert "invoice" in blocked.json()["detail"].lower()


def test_partial_pay_keeps_follow_up(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": "FOLLOW-BAL",
            "quoted_revenue": "400.00",
            "currency_code": "USD",
            "create_project": False,
        },
    )
    quote_id = created.json()["items"][0]["quote_id"]
    client.post(
        f"/api/v1/finance/quotes/{quote_id}/invoice-lines",
        headers=auth_headers,
        json={"amount": "400.00", "line_date": "2026-06-01"},
    )
    client.post(
        f"/api/v1/finance/quotes/{quote_id}/payment-lines",
        headers=auth_headers,
        json={"amount": "100.00", "line_date": "2026-06-10"},
    )
    quote = session.get(Quote, __import__("uuid").UUID(quote_id))
    assert quote is not None
    assert payment_follow_up_due(session, quote, today=date(2026, 7, 10)) is True
    summary = summarize_quote_cash(session, quote)
    assert summary["balance_due"] == Decimal("300.00")


def test_legacy_backfill_creates_lines(session):
    import uuid

    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number="LEGACY-BF",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        is_invoiced=True,
        invoiced_date=date(2026, 5, 1),
        is_paid=True,
        paid_date=date(2026, 5, 20),
        is_active=True,
    )
    session.add(quote)
    session.add(
        QuoteRevision(
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_revenue=Decimal("2000"),
            estimated_cost=Decimal("500"),
            base_quoted_revenue_inr=Decimal("2000"),
            base_estimated_cost_inr=Decimal("500"),
            fx_rate=Decimal("1"),
            fx_date=date(2026, 5, 1),
        )
    )
    session.commit()

    created = backfill_legacy_quote_cash_lines(session)
    assert created >= 2
    inv = session.scalars(
        select(QuoteInvoiceLine).where(QuoteInvoiceLine.quote_id == quote.id)
    ).all()
    pay = session.scalars(
        select(QuotePaymentLine).where(QuotePaymentLine.quote_id == quote.id)
    ).all()
    assert len(inv) == 1
    assert len(pay) == 1
    assert inv[0].amount == Decimal("2000")
    assert pay[0].amount == Decimal("2000")
