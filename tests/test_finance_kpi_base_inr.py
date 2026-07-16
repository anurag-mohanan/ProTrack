"""Quote / expense KPI base-INR exposure (FX snapshot on list)."""

from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.models import Customer


def test_usd_quote_list_exposes_base_quoted_revenue_inr(client, auth_headers, session):
    """Booked revenue KPIs must use snapshotted base INR, not raw USD amounts."""
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
            "tool_number": "FX-KPI-USD-1",
            "quoted_revenue": "1000.00",
            "external_quote_number": "QT-FX-KPI-1",
            "currency_code": "USD",
            "quoted_date": "2026-07-01",
            "create_project": True,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    match = next(q for q in listed.json() if q["id"] == quote_id)

    assert match["currency_code"] == "USD"
    assert Decimal(str(match["quoted_revenue"])) == Decimal("1000.00")
    # Seed FX USD→INR = 83.50 (phase27)
    assert Decimal(str(match["base_quoted_revenue_inr"])) == Decimal("83500.00")
    assert Decimal(str(match["fx_rate"])) == Decimal("83.50")
    assert match["fx_date"] is not None

    # Naïve sum of source amounts would be 1000 and wrongly labelled INR;
    # base INR sum for this quote alone must be 83,500.
    assert Decimal(str(match["base_quoted_revenue_inr"])) != Decimal(
        str(match["quoted_revenue"])
    )


def test_expense_list_keeps_base_amount_inr_for_usd(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    assert centres, "cost centres must be seeded"
    centre_id = centres[0]["id"]
    session.commit()

    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": str(team.id),
            "name": "USD FX KPI license",
            "amount": "100",
            "currency_code": "USD",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "prosohm",
            "purchase_date": "2026-07-01",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["currency_code"] == "USD"
    assert Decimal(str(body["base_amount_inr"])) == Decimal("8350.00")

    listed = client.get(
        f"/api/v1/finance/expenses?team_id={team.id}", headers=auth_headers
    ).json()
    match = next(e for e in listed if e["id"] == body["id"])
    assert Decimal(str(match["base_amount_inr"])) == Decimal("8350.00")
