"""Quote invoicing reminders and is_invoiced flag."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.enums import NotificationType
from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Notification, User
from app.services.finance.quote_invoicing_notifier import (
    list_quotes_due_for_invoicing_reminder,
    notify_uninvoiced_quotes,
)


def _seed_quote(session, *, tool_number: str, created_at: datetime, is_invoiced: bool = False):
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
        quoted_date=created_at.date(),
        is_invoiced=is_invoiced,
        invoiced_date=created_at.date() if is_invoiced else None,
        is_active=True,
    )
    quote.created_at = created_at
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
            fx_date=created_at.date(),
        )
    )
    session.flush()
    return quote


def test_invoicing_reminder_schedule(session):
    today = date(2026, 7, 17)
    anchor = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)  # 15 days ago
    quote = _seed_quote(session, tool_number="REM-15", created_at=anchor)
    session.commit()

    due = list_quotes_due_for_invoicing_reminder(session, today=today)
    assert [row.id for row in due] == [quote.id]

    day16 = date(2026, 7, 18)
    assert list_quotes_due_for_invoicing_reminder(session, today=day16) == []

    day20 = date(2026, 7, 22)
    due20 = list_quotes_due_for_invoicing_reminder(session, today=day20)
    assert [row.id for row in due20] == [quote.id]


def test_invoicing_reminder_notifies_once_per_day(session):
    today = date(2026, 7, 17)
    anchor = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
    quote = _seed_quote(session, tool_number="REM-NOTIFY", created_at=anchor)
    session.commit()

    count, ids = notify_uninvoiced_quotes(session, today=today)
    assert count == 1
    assert ids == [quote.id]
    session.commit()

    notifications = session.scalars(
        select(Notification).where(
            Notification.entity_id == quote.id,
            Notification.notification_type == NotificationType.quote_not_invoiced,
        )
    ).all()
    assert len(notifications) >= 1

    count2, ids2 = notify_uninvoiced_quotes(session, today=today)
    assert count2 == 0
    assert ids2 == []


def test_is_invoiced_yes_no_and_revenue_date(client, auth_headers, session):
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
            "tool_number": "INV-FLAG-1",
            "quoted_revenue": "1200.00",
            "external_quote_number": "QT-INV-FLAG",
            "currency_code": "USD",
            "create_project": False,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
    match = next((q for q in listed.json() if q["id"] == quote_id), None)
    assert match is not None
    assert match.get("is_invoiced") is False

    invoiced = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_invoiced": True, "invoiced_date": "2026-07-10"},
    )
    assert invoiced.status_code == 200, invoiced.text
    body = invoiced.json()
    assert body["is_invoiced"] is True
    assert body["invoiced_date"] == "2026-07-10"

    cleared = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_invoiced": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["is_invoiced"] is False
    assert cleared.json().get("invoiced_date") in (None, "")


def test_uninvoiced_quote_excluded_from_dashboard_revenue(client, auth_headers, session):
    """Revenue counts only when is_invoiced with invoiced_date in period."""
    import uuid as _uuid
    from datetime import date as _date

    from app.models.finance import Quote as QuoteModel, QuoteRevision as QuoteRevisionModel
    from app.models.models import Customer as CustomerModel, Project, Stream, Team

    team = Team(id=_uuid.uuid4(), name="Uninvoiced Team", is_active=True)
    customer = CustomerModel(id=_uuid.uuid4(), name="Uninvoiced Customer", is_active=True)
    stream = Stream(id=_uuid.uuid4(), name="Uninvoiced Stream", is_active=True)
    project = Project(
        id=_uuid.uuid4(),
        tool_number="UNINV-001",
        part_description="Pending invoice",
        customer_id=customer.id,
        stream_id=stream.id,
        team_id=team.id,
    )
    quote = QuoteModel(
        id=_uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        project_id=project.id,
        tool_number="UNINV-001",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        quoted_date=_date.today(),
        is_invoiced=False,
        is_active=True,
    )
    session.add_all(
        [
            team,
            customer,
            stream,
            project,
            quote,
            QuoteRevisionModel(
                quote_id=quote.id,
                version=1,
                revision="A",
                quoted_revenue=Decimal("50000"),
                estimated_cost=Decimal("10000"),
                base_quoted_revenue_inr=Decimal("50000"),
                base_estimated_cost_inr=Decimal("10000"),
                fx_rate=Decimal("1"),
                fx_date=_date.today(),
            ),
        ]
    )
    session.commit()

    dash = client.get(f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    labels = {row["label"] for row in dash.json()["revenue_by_customer"]}
    assert "Uninvoiced Customer" not in labels
