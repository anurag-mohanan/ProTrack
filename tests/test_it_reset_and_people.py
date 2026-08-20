"""IT reset preview + people list from employees."""

from __future__ import annotations


def test_it_reset_preview_preserves_master_counts(client):
    response = client.get(
        "/api/v1/it/data-management/reset-preview",
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "to_delete" in body
    assert "will_not_delete" in body
    assert body["confirm_phrase"] == "RESET IT DATA"
    assert body["will_not_delete"]["employees_users"] > 0
    assert body["will_not_delete"]["projects"] > 0


def test_it_people_lists_active_employees(client):
    response = client.get(
        "/api/v1/it/people",
        headers=client.auth_headers,
        params={"status": "active", "page_size": 50},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    items = body.get("items") or body.get("data") or []
    assert body.get("total", len(items)) >= 1
    row = items[0]
    assert "user_id" in row
    assert "full_name" in row
    assert "employment_status" in row


def test_computer_availability_on_dashboard(client):
    response = client.get("/api/v1/it/dashboard", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "total_computers" in body
    assert "open_computers" in body
    assert "employees_without_computer" in body
