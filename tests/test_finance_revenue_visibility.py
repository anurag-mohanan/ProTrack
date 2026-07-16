from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Project, Stream, Team, User
from tests.conftest import IDS


def test_dashboard_revenue_by_customer_and_stream(client, auth_headers, session):
    team = Team(id=uuid.uuid4(), name="Revenue Team", is_active=True)
    customer_a = Customer(id=uuid.uuid4(), name="Customer Alpha", is_active=True)
    customer_b = Customer(id=uuid.uuid4(), name="Customer Beta", is_active=True)
    stream_a = Stream(id=uuid.uuid4(), name="BIW", is_active=True)
    stream_b = Stream(id=uuid.uuid4(), name="Plastic", is_active=True)
    project_a = Project(
        id=uuid.uuid4(),
        tool_number="REV-001",
        part_description="Revenue A",
        customer_id=customer_a.id,
        stream_id=stream_a.id,
        team_id=team.id,
    )
    project_b = Project(
        id=uuid.uuid4(),
        tool_number="REV-002",
        part_description="Revenue B",
        customer_id=customer_b.id,
        stream_id=stream_b.id,
        team_id=team.id,
    )
    quote_a = Quote(
        id=uuid.uuid4(),
        customer_id=customer_a.id,
        team_id=team.id,
        project_id=project_a.id,
        tool_number="REV-001",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        is_active=True,
    )
    quote_b = Quote(
        id=uuid.uuid4(),
        customer_id=customer_b.id,
        team_id=team.id,
        project_id=project_b.id,
        tool_number="REV-002",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        is_active=True,
    )
    session.add_all(
        [
            team,
            customer_a,
            customer_b,
            stream_a,
            stream_b,
            project_a,
            project_b,
            quote_a,
            quote_b,
            QuoteRevision(
                quote_id=quote_a.id,
                version=1,
                revision="A",
                quoted_revenue=Decimal("100000"),
                estimated_cost=Decimal("60000"),
                base_quoted_revenue_inr=Decimal("100000"),
                base_estimated_cost_inr=Decimal("60000"),
                fx_rate=Decimal("1"),
                fx_date=date(2026, 7, 1),
            ),
            QuoteRevision(
                quote_id=quote_b.id,
                version=1,
                revision="A",
                quoted_revenue=Decimal("250000"),
                estimated_cost=Decimal("150000"),
                base_quoted_revenue_inr=Decimal("250000"),
                base_estimated_cost_inr=Decimal("150000"),
                fx_rate=Decimal("1"),
                fx_date=date(2026, 7, 1),
            ),
        ]
    )
    session.commit()

    dash = client.get(f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()

    customers = {row["label"]: Decimal(str(row["monthly_revenue_inr"])) for row in body["revenue_by_customer"]}
    streams = {row["label"]: Decimal(str(row["monthly_revenue_inr"])) for row in body["revenue_by_stream"]}
    assert customers["Customer Alpha"] == Decimal("100000")
    assert customers["Customer Beta"] == Decimal("250000")
    assert streams["BIW"] == Decimal("100000")
    assert streams["Plastic"] == Decimal("250000")


def test_employee_cost_roster_can_include_inactive_history(client, auth_headers, session):
    user = session.get(User, IDS["user_junior_designer"])
    assert user is not None
    user.is_active = False
    user.leaving_date = date.today().replace(day=1) - timedelta(days=5)
    session.add(user)
    session.commit()

    current = client.get("/api/v1/finance/employee-costs/roster", headers=auth_headers)
    assert current.status_code == 200, current.text
    current_ids = {row["user_id"] for row in current.json()}
    assert str(user.id) not in current_ids

    historical = client.get(
        "/api/v1/finance/employee-costs/roster?include_inactive=true",
        headers=auth_headers,
    )
    assert historical.status_code == 200, historical.text
    rows = {row["user_id"]: row for row in historical.json()}
    assert str(user.id) in rows
    assert rows[str(user.id)]["is_active"] is False
