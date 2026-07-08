"""Email settings and template tests."""

def test_email_settings_crud(client, auth_headers):
    response = client.patch(
        "/api/v1/settings/email",
        headers=auth_headers,
        json={
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "sender_name": "ProTrack",
            "sender_email": "noreply@example.com",
            "use_tls": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["smtp_host"] == "smtp.example.com"
    assert body["has_password"] is False


def test_email_templates_seeded(client, auth_headers):
    response = client.get("/api/v1/settings/email/templates", headers=auth_headers)
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert "project_assigned" in slugs
    assert "timesheet_reminder" in slugs
    assert "welcome_user" in slugs


def test_notification_settings_include_email_toggle(client, auth_headers):
    response = client.patch(
        "/api/v1/settings/notifications",
        headers=auth_headers,
        json={"email_notifications_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["email_notifications_enabled"] is False


def test_engineering_calendar_endpoint(client, auth_headers):
    response = client.get("/api/v1/calendar/engineering", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
