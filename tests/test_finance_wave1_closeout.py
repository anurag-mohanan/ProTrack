"""Wave 1 Finance closeout: receivables aging, CapEx asset link, quote PDF import."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.finance import CostCentre, Quote
from app.models.it_operations import AssetType
from app.models.models import Customer, Team, User
from app.services.finance.quote_pdf_import_service import (
    confirm_quote_pdf_import,
    extract_quote_pdf,
)
from tests.conftest import IDS
from tests.test_prosohm_quote_pdf_import import GOLDEN_QT_TEXT


def _invoiced_quote_id(
    client,
    auth_headers,
    team_id,
    customer_id,
    *,
    tool_number: str,
    amount: str,
    invoice_days_ago: int,
) -> str:
    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team_id),
            "customer_id": str(customer_id),
            "tool_number": tool_number,
            "quoted_revenue": amount,
            "currency_code": "INR",
            "create_project": False,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    invoiced = client.post(
        f"/api/v1/finance/quotes/{quote_id}/invoice-lines",
        headers=auth_headers,
        json={
            "amount": amount,
            "line_date": (date.today() - timedelta(days=invoice_days_ago)).isoformat(),
            "notes": f"INV-{tool_number}",
        },
    )
    assert invoiced.status_code == 201, invoiced.text
    return quote_id


def test_receivables_ages_unpaid_invoice_into_bucket(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    quote_id = _invoiced_quote_id(
        client,
        auth_headers,
        team.id,
        customer.id,
        tool_number="AGING-45",
        amount="1000.00",
        invoice_days_ago=45,
    )

    response = client.get(
        f"/api/v1/finance/receivables?team_id={team.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    row = next(r for r in body["rows"] if r["quote_id"] == quote_id)
    assert row["aging_bucket"] == "31_60"
    assert row["days_outstanding"] == 45
    assert Decimal(str(row["outstanding"])) == Decimal("1000.00")
    assert Decimal(str(row["paid_amount"])) == Decimal("0.00")
    assert row["invoice_number"] == "INV-AGING-45"
    assert Decimal(str(body["buckets"]["31_60"])) >= Decimal("1000.00")
    assert Decimal(str(body["total_outstanding"])) >= Decimal("1000.00")


def test_receivables_drops_settled_quote_and_ages_old_invoice(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    settled_id = _invoiced_quote_id(
        client,
        auth_headers,
        team.id,
        customer.id,
        tool_number="AGING-PAID",
        amount="500.00",
        invoice_days_ago=10,
    )
    paid = client.post(
        f"/api/v1/finance/quotes/{settled_id}/payment-lines",
        headers=auth_headers,
        json={
            "amount": "500.00",
            "line_date": date.today().isoformat(),
            "reference": "settled",
        },
    )
    assert paid.status_code == 201, paid.text

    overdue_id = _invoiced_quote_id(
        client,
        auth_headers,
        team.id,
        customer.id,
        tool_number="AGING-120",
        amount="750.00",
        invoice_days_ago=120,
    )

    body = client.get(
        f"/api/v1/finance/receivables?team_id={team.id}",
        headers=auth_headers,
    ).json()

    assert all(r["quote_id"] != settled_id for r in body["rows"])
    overdue = next(r for r in body["rows"] if r["quote_id"] == overdue_id)
    assert overdue["aging_bucket"] == "90_plus"
    assert Decimal(str(body["buckets"]["90_plus"])) >= Decimal("750.00")


def test_capex_expense_keeps_asset_link_on_create_and_get(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    session.commit()
    laptop = session.scalar(select(AssetType).where(AssetType.code == "LAPTOP"))
    assert laptop is not None

    asset = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": str(laptop.id),
            "make": "Dell",
            "model": "Latitude 5440",
            "serial_number": "SN-CAPEX-LINK",
        },
    )
    assert asset.status_code == 201, asset.text
    asset_id = asset.json()["id"]

    centre = session.scalar(select(CostCentre).where(CostCentre.code == "HARDWARE"))
    assert centre is not None

    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": str(centre.id),
            "team_id": str(team.id),
            "name": "Design workstation (CapEx)",
            "amount": "95000",
            "purchase_date": date.today().replace(day=1).isoformat(),
            "currency_code": "INR",
            "nature": "capex",
            "frequency": "one_time",
            "paid_by": "prosohm",
            "asset_id": asset_id,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["asset_id"] == asset_id

    listed = client.get(
        f"/api/v1/finance/expenses?team_id={team.id}",
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json() if r["id"] == created.json()["id"])
    assert row["asset_id"] == asset_id
    assert row["nature"] == "capex"


def test_quote_pdf_extract_previews_then_confirm_creates(session):
    team = Team(id=uuid.uuid4(), name="Wave1 Closeout Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Sybridge Technologies Canada Inc-MIS",
        code=f"SY{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.commit()
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None

    with patch(
        "app.services.finance.quote_pdf_import_service.extract_prosohm_quote_text",
        return_value=GOLDEN_QT_TEXT,
    ):
        extracted = extract_quote_pdf(
            session,
            content=b"%PDF-fake",
            filename="QT-2026-27-001.pdf",
            team_id=team.id,
        )

    assert extracted["fields"]["external_quote_number"]["value"] == "QT-2026-27-001"
    assert session.scalars(select(Quote)).first() is None

    outcome = confirm_quote_pdf_import(
        session,
        team_id=team.id,
        customer_id=customer.id,
        tool_number=extracted["fields"]["tool_number"]["value"],
        quoted_revenue=Decimal("6160.00"),
        external_quote_number=extracted["fields"]["external_quote_number"]["value"],
        currency_code="USD",
        quoted_hours=Decimal("220"),
        quoted_date=date(2026, 4, 10),
        create_project=False,
        import_anyway=False,
        notes=None,
        content=None,
        filename=None,
        content_sha256=None,
        user=admin,
    )
    session.commit()

    quotes = session.scalars(select(Quote)).all()
    assert len(quotes) == 1
    assert quotes[0].id == outcome.quote.id
    assert quotes[0].external_quote_number == "QT-2026-27-001"
    assert quotes[0].tool_number == "17974"
