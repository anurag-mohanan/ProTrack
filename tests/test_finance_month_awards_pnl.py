"""Month Team P&L uses calendar-month awards + retainer, not open quote pipeline."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Team


def test_month_team_pnl_uses_awards_this_month_not_pipeline(client, auth_headers, session):
    team = Team(id=uuid.uuid4(), name="Month Award Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Month Award Customer",
        code=f"MA{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()

    today = date.today()
    prior_month = (today.replace(day=1) - timedelta(days=1)).replace(day=15)

    this_month_quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"MA-THIS-{uuid.uuid4().hex[:5]}",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        quoted_date=today,
        is_invoiced=True,
        invoiced_date=today,
        is_active=True,
    )
    prior_quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"MA-PRIOR-{uuid.uuid4().hex[:5]}",
        currency_code="INR",
        current_version=1,
        current_revision="A",
        quoted_date=prior_month,
        is_invoiced=True,
        invoiced_date=prior_month,
        is_active=True,
    )
    session.add_all([this_month_quote, prior_quote])
    session.flush()
    session.add_all(
        [
            QuoteRevision(
                id=uuid.uuid4(),
                quote_id=this_month_quote.id,
                version=1,
                revision="A",
                quoted_revenue=Decimal("100000"),
                estimated_cost=Decimal("40000"),
                base_quoted_revenue_inr=Decimal("100000"),
                base_estimated_cost_inr=Decimal("40000"),
                fx_date=today,
            ),
            QuoteRevision(
                id=uuid.uuid4(),
                quote_id=prior_quote.id,
                version=1,
                revision="A",
                quoted_revenue=Decimal("900000"),
                estimated_cost=Decimal("300000"),
                base_quoted_revenue_inr=Decimal("900000"),
                base_estimated_cost_inr=Decimal("300000"),
                fx_date=prior_month,
            ),
        ]
    )
    session.commit()

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()

    row = next(r for r in body["by_team"] if r["team_id"] == str(team.id))
    # Pipeline still available for reference, but Month P&L uses this-month awards only.
    assert Decimal(str(row["quote_revenue_inr"])) == Decimal("1000000.00")
    assert Decimal(str(row["month_quote_awards_inr"])) == Decimal("100000.00")
    assert Decimal(str(row["monthly_revenue_signal_inr"])) == Decimal("100000.00")
    assert Decimal(str(row["planning_revenue_signal_inr"])) == Decimal("100000.00")
    assert Decimal(str(row["estimated_cost_inr"])) == Decimal("40000.00")
    assert Decimal(str(row["gross_profit_inr"])) == Decimal("60000.00")

    # Company Overview KPIs also follow calendar-month awards (not full pipeline).
    assert Decimal(str(body["revenue"]["monthly_revenue"])) >= Decimal("100000.00")
    assert Decimal(str(body["revenue"]["quote_pipeline_revenue"])) >= Decimal("1000000.00")
    # Profit KPIs are month-based: this team's month award is included, prior-month is not.
    assert Decimal(str(body["profitability"]["gross_profit"])) < Decimal("1000000.00")
