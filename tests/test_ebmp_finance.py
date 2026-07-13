"""EBMP Financial Planning + module ACL smoke tests."""

from decimal import Decimal
from io import BytesIO

from app.core.access_control import MODULE_FINANCIAL_PLANNING, resolve_user_modules
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.models.models import User
from app.services.finance.kpi_strategies import finance_kpi_registry
from app.models.enums import WorkingModelCode
from tests.conftest import DEFAULT_PASSWORD, IDS


def _auth(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_em_has_financial_planning_module(session):
    user = session.get(User, IDS["user_pm"])
    assert user is not None
    role = get_role_name(session, user)
    modules = resolve_user_modules(user, role)
    assert MODULE_FINANCIAL_PLANNING in modules
    assert user_has_module_action(user, role, MODULE_FINANCIAL_PLANNING, MODULE_ACTION_VIEW)


def test_designer_forbidden_from_finance_dashboard(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/finance/dashboard", headers=headers)
    assert response.status_code == 403


def test_admin_finance_dashboard(client, auth_headers):
    response = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "INR"
    assert "revenue" in body
    assert "ai_placeholders" in body
    assert len(body["ai_placeholders"]) >= 1


def test_cost_centres_seeded(client, auth_headers):
    response = client.get("/api/v1/finance/cost-centres", headers=auth_headers)
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()}
    assert "EMP_SALARY" in codes
    assert "SW_LICENSES" in codes


def test_quote_csv_import(client, auth_headers):
    csv_content = (
        "Customer,Tool Number,Quoted Hours,Estimated Cost,Quoted Revenue,Currency,Version,Revision\n"
        "Prosohm Test Customer,QUOTE-T-1,40,1000,2500,USD,1,A\n"
    ).encode("utf-8")
    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        files={"file": ("quotes.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported_count"] == 1

    quotes = client.get("/api/v1/finance/quotes", headers=auth_headers)
    assert quotes.status_code == 200
    tools = {row["tool_number"] for row in quotes.json()}
    assert "QUOTE-T-1" in tools


def test_budget_create_and_approve(client, auth_headers):
    create = client.post(
        "/api/v1/finance/budgets",
        headers=auth_headers,
        json={
            "name": "Team A FY26",
            "scope_type": "team",
            "currency_code": "INR",
            "allocated": "100000",
            "spent": "25000",
            "forecast": "90000",
            "fiscal_year": 2026,
        },
    )
    assert create.status_code == 201, create.text
    budget_id = create.json()["id"]
    assert create.json()["approval_status"] == "draft"

    approve = client.patch(
        f"/api/v1/finance/budgets/{budget_id}/status",
        headers=auth_headers,
        json={"approval_status": "approved"},
    )
    assert approve.status_code == 200
    assert approve.json()["approval_status"] == "approved"


def test_finance_kpi_strategies_registered():
    for key in (
        WorkingModelCode.project_based,
        WorkingModelCode.time_materials,
        WorkingModelCode.retainer,
        WorkingModelCode.overheads,
    ):
        strategy = finance_kpi_registry.get(key)
        result = strategy.calculate(
            {
                "quoted_hours": Decimal("100"),
                "actual_hours": Decimal("80"),
                "revenue": Decimal("10000"),
                "actual_cost": Decimal("6000"),
                "billable_hours": Decimal("70"),
                "recovery_percent": Decimal("90"),
                "reserved_capacity": Decimal("160"),
                "consumed_capacity": Decimal("120"),
            }
        )
        assert result["strategy"] == key.value


def test_analytics_catalog_admin(client, auth_headers):
    response = client.get("/api/v1/analytics/catalog", headers=auth_headers)
    assert response.status_code == 200, response.text
    categories = {row["category"] for row in response.json().get("categories", [])}
    assert "Financial Reports" in categories
    assert "HR Reports" in categories


def test_analytics_catalog_designer_empty_or_forbidden(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/analytics/catalog", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json().get("categories", []) == []


def test_hr_dashboard_requires_module(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/hr/dashboard", headers=headers)
    assert response.status_code == 403


def test_admin_hr_dashboard_includes_timesheet_attention(client, auth_headers):
    response = client.get("/api/v1/hr/dashboard", headers=auth_headers)
    # Admin may lack human_resources module by role defaults - grant via all modules
    # Admin has ALL_MODULES including human_resources
    assert response.status_code == 200, response.text
    body = response.json()
    assert "timesheet_attention" in body
    assert "users" in body
    assert "pending_timesheets" in body


def test_primary_team_optional(session):
    from app.models.enums import TeamRelationshipType
    from app.services.user_team_service import UserTeamAssignmentInput, sync_user_team_assignments
    import uuid
    from app.models.models import Team

    team = Team(id=uuid.uuid4(), name="Optional Primary Team", is_active=True)
    session.add(team)
    session.flush()
    user = session.get(User, IDS["user_binil"])
    assert user is not None
    sync_user_team_assignments(
        session,
        user.id,
        assignments=[
            UserTeamAssignmentInput(
                team_id=team.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=False,
            )
        ],
    )
    session.commit()
    session.refresh(user)
    assert user.team_id is None


def test_em_defaults_include_financial_planning():
    from app.core.access_control import MODULE_FINANCIAL_PLANNING, default_modules_for_role

    modules = default_modules_for_role("Engineering Manager")
    assert MODULE_FINANCIAL_PLANNING in modules
    assert MODULE_FINANCIAL_PLANNING not in default_modules_for_role("Design Leader")
    assert MODULE_FINANCIAL_PLANNING not in default_modules_for_role("Designer")
