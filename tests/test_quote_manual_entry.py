"""Manual awarded quote entry (no PDF AI)."""

from decimal import Decimal

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.models import Customer
from sqlalchemy import select


def test_manual_quote_create_types_fields(client, auth_headers, session):
    """Operator types Quote #, Project #, Cost — lands on Quote + revision."""
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    response = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": "2649-MANUAL",
            "quoted_revenue": "5250.00",
            "external_quote_number": "QT-2026-27-005",
            "currency_code": "USD",
            "create_project": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 1
    item = body["items"][0]
    assert item["tool_number"] == "2649-MANUAL"
    assert item["external_quote_number"] == "QT-2026-27-005"
    assert Decimal(str(item["quoted_revenue"])) == Decimal("5250.00")
    assert item["project_linked"] is True

    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
    assert listed.status_code == 200
    match = next(
        (q for q in listed.json() if q["tool_number"] == "2649-MANUAL"), None
    )
    assert match is not None
    assert match["external_quote_number"] == "QT-2026-27-005"
