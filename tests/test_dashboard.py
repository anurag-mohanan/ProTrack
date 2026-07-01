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


def test_dashboard_overview(client, auth_headers):
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "kpis" in body
    assert "projects_requiring_attention" in body
    assert "my_tasks" in body
    assert "recent_activity" in body
    assert len(body["recent_activity"]) <= 15
    assert len(body["projects_requiring_attention"]) <= 10
    kpis = body["kpis"]
    assert "active_projects" in kpis
    assert "designer_utilization_percent" in kpis
    assert "billable_hours_this_month" in kpis
