"""Annual Plan sales sync from invoiced quotes (invoiced_date → FY quarter)."""

from decimal import Decimal

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.models import Customer
from sqlalchemy import select


def test_sync_sales_from_awarded_quotes_places_q2(client, auth_headers, session):
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
            "tool_number": "SALES-SYNC-Q2",
            "quoted_revenue": "9000.00",
            "external_quote_number": "QT-SALES-Q2",
            "currency_code": "INR",
            "quoted_date": "2032-08-15",
            "create_project": True,
        },
    )
    assert created.status_code == 200, created.text
    quote_id = created.json()["items"][0]["quote_id"]

    invoiced = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"is_invoiced": True, "invoiced_date": "2032-08-15"},
    )
    assert invoiced.status_code == 200, invoiced.text

    listed = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
    match = next(q for q in listed.json() if q["id"] == quote_id)
    assert match["quoted_date"] == "2032-08-15"

    plan_resp = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY Sales Sync",
            "fiscal_year_start_year": 2032,
            "tax_percent": 30,
            "provision_percent": 0,
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan_id = plan_resp.json()["id"]

    synced = client.post(
        f"/api/v1/finance/plans/{plan_id}/sync-sales-from-quotes",
        headers=auth_headers,
    )
    assert synced.status_code == 200, synced.text
    detail = synced.json()
    award_lines = [
        row
        for row in detail["lines"]
        if row["section"] == "sales" and str(row["code"]).startswith("awarded_")
    ]
    assert len(award_lines) >= 1
    line = next(
        (row for row in award_lines if "QT-SALES-Q2" in row["label"] or "SALES-SYNC-Q2" in row["label"]),
        award_lines[-1],
    )
    assert Decimal(str(line["q2"])) == Decimal("9000.00")
    assert Decimal(str(line["q1"])) == Decimal("0")
    assert Decimal(str(line["q3"])) == Decimal("0")
    assert Decimal(str(line["q4"])) == Decimal("0")


def test_sync_skips_quote_outside_fy(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": "OUTSIDE-FY",
            "quoted_revenue": "5000.00",
            "external_quote_number": "QT-OUT",
            "currency_code": "INR",
            "quoted_date": "2020-05-01",
            "create_project": False,
        },
    )

    plan_resp = client.post(
        "/api/v1/finance/plans",
        headers=auth_headers,
        json={
            "name": "FY Outside Skip",
            "fiscal_year_start_year": 2033,
            "tax_percent": 0,
            "provision_percent": 0,
        },
    )
    plan_id = plan_resp.json()["id"]
    before_sales = [
        row for row in plan_resp.json()["lines"] if row["section"] == "sales"
    ]

    synced = client.post(
        f"/api/v1/finance/plans/{plan_id}/sync-sales-from-quotes",
        headers=auth_headers,
    )
    assert synced.status_code == 200, synced.text
    after_award = [
        row
        for row in synced.json()["lines"]
        if row["section"] == "sales" and "QT-OUT" in row.get("label", "")
    ]
    assert after_award == []
    assert len([r for r in synced.json()["lines"] if r["section"] == "sales"]) >= len(
        before_sales
    )


def test_quote_patch_quoted_date(client, auth_headers, session):
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
            "tool_number": "DATE-PATCH",
            "quoted_revenue": "100.00",
            "currency_code": "INR",
            "quoted_date": "2034-04-10",
            "create_project": False,
        },
    )
    quote_id = created.json()["items"][0]["quote_id"]

    patched = client.patch(
        f"/api/v1/finance/quotes/{quote_id}",
        headers=auth_headers,
        json={"quoted_date": "2034-11-20", "team_id": str(team.id)},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["quoted_date"] == "2034-11-20"
