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


def test_quote_invoiced_date_set_and_clear(client, auth_headers, session):
    """Invoiced yes/no and date; revenue date set when marked invoiced."""
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
            "tool_number": "INV-DATE-1",
            "quoted_revenue": "900.00",
            "external_quote_number": "QT-INV-1",
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
    assert match.get("invoiced_date") in (None, "")

    invoiced = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_invoiced": True, "invoiced_date": "2026-07-15"},
    )
    assert invoiced.status_code == 200, invoiced.text
    assert invoiced.json()["is_invoiced"] is True
    assert invoiced.json()["invoiced_date"] == "2026-07-15"

    cleared = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_invoiced": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json().get("is_invoiced") is False
    assert cleared.json().get("invoiced_date") in (None, "")


def test_quote_edit_and_soft_delete(client, auth_headers, session):
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
            "tool_number": "EDIT-DEL-1",
            "quoted_revenue": "1000.00",
            "external_quote_number": "QT-EDIT-1",
            "currency_code": "USD",
            "create_project": True,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    updated = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={
            "external_quote_number": "QT-EDIT-2",
            "quoted_revenue": "1500.00",
            "tool_number": "EDIT-DEL-1",
            "customer_id": str(customer.id),
            "team_id": str(team.id),
            "currency_code": "USD",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["external_quote_number"] == "QT-EDIT-2"
    assert Decimal(str(updated.json()["quoted_revenue"])) == Decimal("1500.00")

    deleted = client.delete(
        f"/api/v1/finance/quotes/{quote_id}", headers=auth_headers
    )
    assert deleted.status_code == 204, deleted.text

    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
    assert listed.status_code == 200
    assert all(q["id"] != quote_id for q in listed.json())
