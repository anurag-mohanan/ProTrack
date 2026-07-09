"""Tests for standardized pagination responses."""

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
    assert isinstance(payload["items"], list)


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
