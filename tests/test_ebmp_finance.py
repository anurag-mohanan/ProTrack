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


def test_expense_paid_by_customer_is_pass_through(client, auth_headers):
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers)
    assert centres.status_code == 200
    centre_id = centres.json()[0]["id"]

    before = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    before_opex = float(before["cost"]["prosohm_opex"])
    before_pass = float(before["pass_through_opex_inr"])

    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "name": "Customer NX seat",
            "amount": "5000",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "customer",
            "is_recurring": True,
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["paid_by"] == "customer"

    after = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(after["cost"]["prosohm_opex"]) == before_opex
    assert float(after["pass_through_opex_inr"]) == before_pass + 5000.0


def test_expense_renewal_window_and_notify(client, auth_headers):
    from datetime import date, timedelta

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    centre_id = centres[0]["id"]
    renewal = (date.today() + timedelta(days=5)).isoformat()

    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "name": "NX Mach 3",
            "vendor_name": "Siemens",
            "amount": "120000",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "prosohm",
            "is_recurring": True,
            "next_renewal_date": renewal,
            "notify_before_days": 7,
            "notify_enabled": True,
        },
    )
    assert create.status_code == 201, create.text

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    names = {row["name"] for row in dash["upcoming_renewals"]}
    assert "NX Mach 3" in names

    notify = client.post("/api/v1/finance/renewals/notify", headers=auth_headers)
    assert notify.status_code == 200, notify.text
    assert notify.json()["notified_count"] >= 1

    again = client.post("/api/v1/finance/renewals/notify", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["notified_count"] == 0


def test_employee_cost_roster_lists_all_active_users(client, auth_headers):
    roster = client.get("/api/v1/finance/employee-costs/roster", headers=auth_headers)
    assert roster.status_code == 200, roster.text
    rows = roster.json()
    assert len(rows) >= 3
    emails = {row["email"] for row in rows}
    assert "admin@prosohm.com" in emails or any("admin" in e for e in emails)

    target = next(row for row in rows if row["email"] == "binil@prosohm.com")
    save = client.post(
        "/api/v1/finance/employee-costs",
        headers=auth_headers,
        json={
            "user_id": target["user_id"],
            "monthly_salary": "75000",
            "hourly_cost": "450",
            "currency_code": "INR",
            "effective_from": "2026-04-01",
        },
    )
    assert save.status_code == 201, save.text
    refreshed = client.get("/api/v1/finance/employee-costs/roster", headers=auth_headers).json()
    updated = next(row for row in refreshed if row["user_id"] == target["user_id"])
    assert updated["has_profile"] is True
    assert float(updated["monthly_salary"]) == 75000.0


def test_team_commercial_terms_in_dashboard(client, auth_headers, session):
    import uuid
    from datetime import date

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name="Finance Rebuild Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"retainer_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Sub",
        is_active=True,
    )
    session.add(team)
    session.add(model)
    session.commit()

    create = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "billing_mode": "subscription",
            "customer_fee_amount": "120000",
            "currency_code": "INR",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
        },
    )
    assert create.status_code == 201, create.text

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(dash["team_commercial_fee_monthly_inr"]) >= 120000.0


def test_designer_forbidden_from_roster(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/finance/employee-costs/roster", headers=headers)
    assert response.status_code == 403


def test_retainer_strategy_includes_customer_fee():
    strategy = finance_kpi_registry.get(WorkingModelCode.retainer)
    result = strategy.calculate(
        {
            "reserved_capacity": Decimal("160"),
            "consumed_capacity": Decimal("80"),
            "customer_fee": Decimal("50000"),
        }
    )
    assert result["customer_fee"] == Decimal("50000")
    assert result["effective_hourly_rate"] == Decimal("625.00")
