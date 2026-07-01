import pytest


def test_phase7_settings_endpoints(client, auth_headers):
    company = client.get("/api/v1/settings/company", headers=auth_headers)
    assert company.status_code == 200
    assert company.json()["company_name"]

    departments = client.get("/api/v1/settings/departments", headers=auth_headers)
    assert departments.status_code == 200
    assert len(departments.json()) >= 6

    skills = client.get("/api/v1/settings/skills", headers=auth_headers)
    assert skills.status_code == 200
    assert any(row["name"] == "NX" for row in skills.json())

    disciplines = client.get("/api/v1/settings/disciplines", headers=auth_headers)
    assert disciplines.status_code == 200
    assert any("Mold" in row["name"] for row in disciplines.json())

    holidays = client.get("/api/v1/settings/holidays", headers=auth_headers)
    assert holidays.status_code == 200

    paths = client.get("/api/v1/settings/file-paths", headers=auth_headers)
    assert paths.status_code == 200

    notifications = client.get("/api/v1/settings/notifications", headers=auth_headers)
    assert notifications.status_code == 200
    assert notifications.json()["projects_due_enabled"] is True


def test_company_settings_update(client, auth_headers):
    response = client.patch(
        "/api/v1/settings/company",
        headers=auth_headers,
        json={"company_name": "Prosohm Engineering Pvt Ltd", "currency": "INR"},
    )
    assert response.status_code == 200
    assert response.json()["company_name"] == "Prosohm Engineering Pvt Ltd"
