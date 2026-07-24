"""Quote payment tracking and follow-up reminders (30 days, then weekly)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.enums import NotificationType
from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Notification
from app.services.finance.quote_payment_notifier import (
    list_quotes_due_for_payment_reminder,
    next_payment_follow_up_date,
    notify_unpaid_quotes,
    payment_follow_up_due,
)


def _seed_invoiced_quote(
    session,
    *,
    tool_number: str,
    invoiced_date: date,
    is_paid: bool = False,
):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=tool_number,
        currency_code="USD",
        current_version=1,
        current_revision="A",
        quoted_date=invoiced_date,
        is_invoiced=True,
        invoiced_date=invoiced_date,
        is_paid=is_paid,
        paid_date=invoiced_date if is_paid else None,
        is_active=True,
    )
    quote.created_at = datetime(
        invoiced_date.year, invoiced_date.month, invoiced_date.day, 10, 0, tzinfo=timezone.utc
    )
    session.add(quote)
    session.add(
        QuoteRevision(
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_revenue=Decimal("1000"),
            estimated_cost=Decimal("500"),
            base_quoted_revenue_inr=Decimal("83000"),
            base_estimated_cost_inr=Decimal("41500"),
            fx_rate=Decimal("83"),
            fx_date=invoiced_date,
        )
    )
    session.flush()
    return quote


def test_payment_follow_up_schedule(session):
    invoiced = date(2026, 6, 17)
    quote = _seed_invoiced_quote(session, tool_number="PAY-30", invoiced_date=invoiced)
    session.commit()

    day29 = date(2026, 7, 16)
    assert payment_follow_up_due(session, quote, today=day29) is False
    assert next_payment_follow_up_date(session, quote, today=day29) == date(2026, 7, 17)
    assert list_quotes_due_for_payment_reminder(session, today=day29) == []

    day30 = date(2026, 7, 17)
    assert payment_follow_up_due(session, quote, today=day30) is True
    assert [row.id for row in list_quotes_due_for_payment_reminder(session, today=day30)] == [
        quote.id
    ]

    day31 = date(2026, 7, 18)
    assert list_quotes_due_for_payment_reminder(session, today=day31) == []

    day37 = date(2026, 7, 24)
    assert [row.id for row in list_quotes_due_for_payment_reminder(session, today=day37)] == [
        quote.id
    ]


def test_payment_reminder_skips_paid(session):
    invoiced = date(2026, 6, 17)
    quote = _seed_invoiced_quote(
        session, tool_number="PAY-PAID", invoiced_date=invoiced, is_paid=True
    )
    session.commit()
    today = date(2026, 7, 17)
    assert payment_follow_up_due(session, quote, today=today) is False
    assert list_quotes_due_for_payment_reminder(session, today=today) == []


def test_payment_reminder_notifies_once_per_day(session):
    invoiced = date(2026, 6, 17)
    quote = _seed_invoiced_quote(session, tool_number="PAY-NOTIFY", invoiced_date=invoiced)
    session.commit()
    today = date(2026, 7, 17)

    count, ids = notify_unpaid_quotes(session, today=today)
    assert count == 1
    assert ids == [quote.id]
    session.commit()

    notifications = session.scalars(
        select(Notification).where(
            Notification.entity_id == quote.id,
            Notification.notification_type == NotificationType.quote_payment_follow_up,
        )
    ).all()
    assert len(notifications) >= 1

    count2, ids2 = notify_unpaid_quotes(session, today=today)
    assert count2 == 0
    assert ids2 == []


def test_quote_po_and_payment_via_api(client, auth_headers, session):
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
            "tool_number": "PO-PAY-1",
            "quoted_revenue": "2500.00",
            "external_quote_number": "QT-PO-PAY",
            "currency_code": "USD",
            "create_project": False,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    patched = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={
            "customer_po_number": "PO-7788",
            "is_invoiced": True,
            "invoiced_date": "2026-06-01",
            "is_paid": False,
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["customer_po_number"] == "PO-7788"
    assert body["is_invoiced"] is True
    assert body["is_paid"] is False
    assert body["payment_follow_up_on"] is not None

    paid = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_paid": True, "paid_date": "2026-07-01"},
    )
    assert paid.status_code == 200, paid.text
    paid_body = paid.json()
    assert paid_body["is_paid"] is True
    assert paid_body["paid_date"] == "2026-07-01"
    assert paid_body["payment_follow_up_due"] is False
    assert paid_body["payment_follow_up_on"] is None
