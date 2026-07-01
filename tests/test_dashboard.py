from decimal import Decimal


def test_dashboard_summary(client, auth_headers):
    response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_projects"] == 1
    assert body["total_milestones"] == 7
    assert Decimal(str(body["total_quoted_hours"])) == Decimal("120.00")


def test_dashboard_workload(client, auth_headers):
    response = client.get("/api/v1/dashboard/workload", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 2
    roles = {row["role"] for row in body}
    assert "Design Leader" in roles
    assert "Designer" in roles


def test_dashboard_project(client, auth_headers):
    project_id = client.project_id
    response = client.get(f"/api/v1/dashboard/project/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["code"] == "TEST-001"
    assert body["milestone_summary"]["remaining"] == 7
    assert Decimal(str(body["hours"]["quoted"])) == Decimal("120.00")


def test_dashboard_granular_endpoints(client, auth_headers):
    endpoints = [
        "/api/v1/dashboard/kpis",
        "/api/v1/dashboard/attention-projects",
        "/api/v1/dashboard/recent-activity",
        "/api/v1/dashboard/my-tasks",
        "/api/v1/dashboard/overview",
    ]
    for path in endpoints:
        response = client.get(path, headers=auth_headers)
        assert response.status_code == 200, path

    kpis = client.get("/api/v1/dashboard/kpis", headers=auth_headers).json()
    assert "np_hours_this_month" in kpis
    assert "billable_hours_this_month" in kpis

    activity = client.get("/api/v1/dashboard/recent-activity", headers=auth_headers).json()
    assert len(activity) <= 15


def test_np_code_seed_includes_c506(client, auth_headers):
    response = client.get("/api/v1/lookups/non-productive-codes", headers=auth_headers)
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()}
    assert "C506" in codes
    assert "C500" in codes
    assert "EST001" in codes


def test_np_reports_endpoints(client, auth_headers):
    paths = [
        "/api/v1/reports/non-productive-hours",
        "/api/v1/reports/np-hours-by-designer",
        "/api/v1/reports/monthly-np-trends",
        "/api/v1/reports/billable-vs-non-billable",
        "/api/v1/reports/top-np-activities",
    ]
    for path in paths:
        response = client.get(path, headers=auth_headers)
        assert response.status_code == 200, path
