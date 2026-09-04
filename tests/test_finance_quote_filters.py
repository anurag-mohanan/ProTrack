"""Finance quote list filters — invoice/payment status end-to-end."""

from __future__ import annotations

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.models import Customer
from app.services.finance.quote_filter_service import (
    normalize_invoice_status,
    quote_matches_filters,
)


def _customer(session):
    customer = session.scalar(select(Customer).where(Customer.name == "Prosohm Test Customer"))
    assert customer is not None
    return customer


def _create_quote(client, headers, *, tool: str, revenue: str, team_id: str, customer_id: str):
    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=headers,
        json={
            "team_id": team_id,
            "customer_id": customer_id,
            "tool_number": tool,
            "quoted_revenue": revenue,
            "external_quote_number": f"QT-{tool}",
            "currency_code": "INR",
            "create_project": False,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["items"][0]["quote_id"]


def test_quote_invoice_status_filters(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = _customer(session)
    session.commit()
    team_id = str(team.id)
    customer_id = str(customer.id)

    none_id = _create_quote(
        client, auth_headers, tool="FILT-NONE", revenue="1000", team_id=team_id, customer_id=customer_id
    )
    partial_id = _create_quote(
        client,
        auth_headers,
        tool="FILT-PART",
        revenue="1000",
        team_id=team_id,
        customer_id=customer_id,
    )
    full_id = _create_quote(
        client, auth_headers, tool="FILT-FULL", revenue="1000", team_id=team_id, customer_id=customer_id
    )

    partial = client.post(
        f"/api/v1/finance/quotes/{partial_id}/invoice-lines",
        headers=auth_headers,
        json={"amount": "400.00", "line_date": "2026-06-01"},
    )
    assert partial.status_code == 201, partial.text
    assert partial.json()["invoice_status"] == "partial"

    full = client.post(
        f"/api/v1/finance/quotes/{full_id}/invoice-lines",
        headers=auth_headers,
        json={"amount": "1000.00", "line_date": "2026-06-02"},
    )
    assert full.status_code == 201, full.text
    assert full.json()["invoice_status"] == "full"

    not_invoiced = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&list_filter=not_invoiced",
        headers=auth_headers,
    )
    assert not_invoiced.status_code == 200, not_invoiced.text
    none_ids = {row["id"] for row in not_invoiced.json()}
    assert none_id in none_ids
    assert partial_id not in none_ids
    assert full_id not in none_ids
    assert all(row["invoice_status"] == "none" for row in not_invoiced.json() if row["id"] in {none_id})

    partially = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&list_filter=partially_invoiced",
        headers=auth_headers,
    )
    assert partially.status_code == 200
    part_ids = {row["id"] for row in partially.json()}
    assert partial_id in part_ids
    assert full_id not in part_ids
    assert none_id not in part_ids

    invoiced = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&list_filter=invoiced",
        headers=auth_headers,
    )
    assert invoiced.status_code == 200
    full_ids = {row["id"] for row in invoiced.json()}
    assert full_id in full_ids
    assert partial_id not in full_ids, "Partially invoiced must not match fully-invoiced filter"
    assert none_id not in full_ids

    by_status = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&invoice_status=partial",
        headers=auth_headers,
    )
    assert by_status.status_code == 200
    assert partial_id in {row["id"] for row in by_status.json()}
    assert full_id not in {row["id"] for row in by_status.json()}

    searched = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&q=FILT-PART",
        headers=auth_headers,
    )
    assert searched.status_code == 200
    assert {row["id"] for row in searched.json()} == {partial_id}

    combined = client.get(
        f"/api/v1/finance/quotes?team_id={team_id}&list_filter=invoiced&q=FILT-FULL",
        headers=auth_headers,
    )
    assert combined.status_code == 200
    assert {row["id"] for row in combined.json()} == {full_id}


def test_normalize_invoice_status_aliases():
    assert normalize_invoice_status("not_invoiced") == "none"
    assert normalize_invoice_status("invoiced") == "full"
    assert normalize_invoice_status("partial") == "partial"
    assert quote_matches_filters(
        {"invoice_status": "partial", "balance_due": 10},
        list_filter="invoiced",
    ) is False
    assert quote_matches_filters(
        {"invoice_status": "full", "balance_due": 0},
        list_filter="invoiced",
    ) is True
    assert quote_matches_filters(
        {"invoice_status": "none", "balance_due": 0},
        list_filter="not_invoiced",
    ) is True
