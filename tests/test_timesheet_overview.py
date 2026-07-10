"""Timesheet overview team scoping for leaders and managers."""


def test_timesheet_overview_endpoint(client, auth_headers):
    response = client.get("/api/v1/timesheets/overview", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "teams" in body
    assert "users" in body
    assert isinstance(body["teams"], list)
    assert isinstance(body["users"], list)


def test_timesheet_overview_user_includes_working_hours(client, auth_headers):
    body = client.get("/api/v1/timesheets/overview", headers=auth_headers).json()
    assert body["users"]
    assert "working_hours_per_day" in body["users"][0]
