"""Tests for standardized pagination responses."""

from sqlalchemy import select

from app.models.models import ProjectTemplate
from tests.conftest import login


def _items(response):
    data = response.json()
    if isinstance(data, dict) and "items" in data:
        return data
    return None


def test_users_list_returns_paginated_response(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/users?page=1&page_size=25", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
    assert payload["page"] == 1
    assert payload["page_size"] == 25
    assert payload["total_records"] == payload["total"]
    assert payload["total_pages"] == payload["pages"]
    assert payload["has_next"] is (payload["page"] < payload["pages"])
    assert payload["has_previous"] is False
    assert isinstance(payload["items"], list)


def test_users_list_page_two(client):
    headers = login(client, "admin@prosohm.com")
    first = client.get("/api/v1/users?page=1&page_size=2", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    if first_payload["total"] <= 2:
        return
    second = client.get("/api/v1/users?page=2&page_size=2", headers=headers)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["page"] == 2
    assert second_payload["has_previous"] is True
    first_ids = {row["id"] for row in first_payload["items"]}
    second_ids = {row["id"] for row in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_users_list_search_filter(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/users?search=admin&page=1&page_size=25", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert all("admin" in row["email"].lower() for row in payload["items"])


def test_projects_list_returns_paginated_response(client):
    response = client.get("/api/v1/projects?page=1&page_size=25", headers=client.auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert payload["page_size"] == 25
    assert len(payload["items"]) >= 1


def test_activities_pagination_skip_limit_compat(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/activities?skip=0&limit=25", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_size"] == 25
    assert payload["page"] == 1


def test_customers_factory_pagination(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/customers?page=2&page_size=25", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 25


def test_project_templates_list_paginated(client, session):
    from app.db.project_template_seed import ensure_project_types_and_templates

    ensure_project_types_and_templates(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/project-templates?page=1&page_size=2", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) <= 2
    if payload["total"] > 2:
        page_two = client.get("/api/v1/project-templates?page=2&page_size=2", headers=headers)
        assert page_two.status_code == 200
        assert page_two.json()["page"] == 2
        assert page_two.json()["has_previous"] is True


def test_project_templates_search(client, session):
    from app.db.project_template_seed import ensure_project_types_and_templates

    ensure_project_types_and_templates(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get(
        "/api/v1/project-templates?search=TI%20Automotive&page=1&page_size=25",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert any("TI Automotive" in item["name"] for item in payload["items"])


def test_project_template_reactivate(client, session):
    from app.db.project_template_seed import ensure_project_types_and_templates

    ensure_project_types_and_templates(session)
    headers = login(client, "admin@prosohm.com")
    general = session.scalar(
        select(ProjectTemplate).where(ProjectTemplate.name == "General Mold Design")
    )
    assert general is not None
    deactivate = client.post(
        f"/api/v1/project-templates/{general.id}/deactivate",
        headers=headers,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    reactivate = client.post(
        f"/api/v1/project-templates/{general.id}/reactivate",
        headers=headers,
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True
