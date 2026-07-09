"""Tests for System Health & Operations Center API."""

from tests.conftest import login


def test_operations_center_admin_access(client):
    denied = client.get("/api/v1/system/operations", headers=login(client, "anurag@prosohm.com"))
    assert denied.status_code == 403

    admin_headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/system/operations", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"healthy", "warning", "critical"}
    assert payload["services"]
    assert payload["database"]["connected"] is True


def test_operations_center_engineering_manager_read_only(client):
    em_headers = login(client, "pm@prosohm.com")
    response = client.get("/api/v1/system/operations", headers=em_headers)
    assert response.status_code == 200

    maintenance = client.post(
        "/api/v1/system/operations/maintenance",
        json={"action": "test_database"},
        headers=em_headers,
    )
    assert maintenance.status_code == 403


def test_operations_diagnostics(client):
    admin_headers = login(client, "admin@prosohm.com")
    response = client.post("/api/v1/system/operations/diagnostics", headers=admin_headers)
    assert response.status_code == 200
    report = response.json()
    assert report["results"]
    assert report["overall_status"] in {"healthy", "warning", "critical"}
