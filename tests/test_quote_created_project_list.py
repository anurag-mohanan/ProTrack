"""Reproduce: quote-created project must list/load in Projects API."""

from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.models import Customer, Project


def test_quote_created_project_lists_and_reads(client, auth_headers, session):
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    session.commit()

    tool = "QUOTE-LIST-REPRO-1"
    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": tool,
            "quoted_revenue": "100.00",
            "external_quote_number": "QT-REPRO-1",
            "currency_code": "USD",
            "quoted_hours": "40.00",
            "create_project": True,
        },
    )
    assert created.status_code == 200, created.text
    item = created.json()["items"][0]
    assert item["project_linked"] is True or item.get("project_created") is True

    project = session.scalar(
        select(Project).where(Project.tool_number == tool, Project.is_deleted.is_(False))
    )
    assert project is not None
    assert project.part_description == ""
    assert Decimal(str(project.quoted_hours or 0)) == Decimal("0")
    assert project.due_date is None
    assert project.notes is None
    project_id = str(project.id)

    listed = client.get("/api/v1/projects?limit=500", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    match = next((p for p in items if p["tool_number"] == tool), None)
    assert match is not None, f"quote project missing from list: {listed.text[:500]}"

    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text

    # Workspace page loads command-center (Projects → open project)
    cc = client.get(
        f"/api/v1/projects/{project_id}/command-center", headers=auth_headers
    )
    assert cc.status_code == 200, cc.text
    assert cc.json()["project"]["tool_number"] == tool

    dash = client.get(f"/api/v1/projects/{project_id}/detail", headers=auth_headers)
    assert dash.status_code == 200, dash.text

    # Should be updatable from Projects section
    patched = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={
            "part_description": "Filled from Projects",
            "quoted_hours": "12.5",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["part_description"] == "Filled from Projects"
