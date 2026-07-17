"""Quote-created shell projects: list/load, edit type, apply template."""

from decimal import Decimal

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.db.project_template_seed import ensure_project_types_and_templates
from app.models.models import Customer, Milestone, Project, ProjectTemplate, ProjectType


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
    assert project.project_type_id is None
    assert project.project_template_id is None
    project_id = str(project.id)

    listed = client.get("/api/v1/projects?limit=500", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    match = next((p for p in items if p["tool_number"] == tool), None)
    assert match is not None, f"quote project missing from list: {listed.text[:500]}"

    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json().get("project_type_id") in (None, "")

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


def test_quote_shell_can_set_type_and_apply_template(client, auth_headers, session):
    """Shell projects from quotes have no type/template; Projects edit must apply both."""
    ensure_project_types_and_templates(session)
    team = ensure_corporate_shared_services_team(session)
    customer = session.scalar(
        select(Customer).where(Customer.name == "Prosohm Test Customer")
    )
    assert customer is not None
    mold_type = session.scalar(select(ProjectType).where(ProjectType.name == "Mold Design"))
    template = session.scalar(
        select(ProjectTemplate).where(ProjectTemplate.name == "General Mold Design")
    )
    assert mold_type is not None and template is not None
    session.commit()

    tool = "QUOTE-TMPL-SHELL-1"
    created = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": tool,
            "quoted_revenue": "200.00",
            "external_quote_number": "QT-TMPL-1",
            "currency_code": "USD",
            "create_project": True,
        },
    )
    assert created.status_code == 200, created.text
    project = session.scalar(
        select(Project).where(Project.tool_number == tool, Project.is_deleted.is_(False))
    )
    assert project is not None
    assert project.project_type_id is None
    project_id = str(project.id)

    # Applying template without type still rejected
    blocked = client.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=auth_headers,
        json={"project_template_id": str(template.id)},
    )
    assert blocked.status_code == 422, blocked.text

    # Set type via Projects edit
    typed = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"project_type_id": str(mold_type.id)},
    )
    assert typed.status_code == 200, typed.text
    assert typed.json()["project_type_id"] == str(mold_type.id)

    # Or apply in one step with project_type_id on a fresh shell
    tool2 = "QUOTE-TMPL-SHELL-2"
    created2 = client.post(
        "/api/v1/finance/quotes/manual",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "customer_id": str(customer.id),
            "tool_number": tool2,
            "quoted_revenue": "250.00",
            "external_quote_number": "QT-TMPL-2",
            "currency_code": "USD",
            "create_project": True,
        },
    )
    assert created2.status_code == 200, created2.text
    project2 = session.scalar(
        select(Project).where(Project.tool_number == tool2, Project.is_deleted.is_(False))
    )
    assert project2 is not None
    project2_id = str(project2.id)

    applied = client.post(
        f"/api/v1/projects/{project2_id}/apply-template",
        headers=auth_headers,
        json={
            "project_type_id": str(mold_type.id),
            "project_template_id": str(template.id),
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["project_type_id"] == str(mold_type.id)
    assert body["project_template_id"] == str(template.id)

    milestones = session.scalars(
        select(Milestone)
        .where(Milestone.project_id == project2.id)
        .order_by(Milestone.sort_order)
    ).all()
    assert len(milestones) > 0
