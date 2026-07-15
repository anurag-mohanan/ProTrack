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


def test_quote_csv_import(client, auth_headers, session):
    from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team

    team = ensure_corporate_shared_services_team(session)
    session.commit()
    csv_content = (
        "Customer,Tool Number,Quoted Hours,Estimated Cost,Quoted Revenue,Currency,Version,Revision\n"
        "Prosohm Test Customer,QUOTE-T-1,40,1000,2500,USD,1,A\n"
    ).encode("utf-8")
    response = client.post(
        "/api/v1/finance/quotes/import",
        headers=auth_headers,
        data={"team_id": str(team.id)},
        files={"file": ("quotes.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported_count"] == 1

    quotes = client.get(
        f"/api/v1/finance/quotes?team_id={team.id}", headers=auth_headers
    )
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


def _corporate_team_id(client, auth_headers, session) -> str:
    from app.db.phase23_finance_team_scope_schema_sync import (
        CORPORATE_TEAM_NAME,
        ensure_corporate_shared_services_team,
    )

    team = ensure_corporate_shared_services_team(session)
    session.commit()
    assert team.name == CORPORATE_TEAM_NAME
    return str(team.id)


def test_expense_paid_by_customer_is_pass_through(client, auth_headers, session):
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers)
    assert centres.status_code == 200
    centre_id = centres.json()[0]["id"]
    team_id = _corporate_team_id(client, auth_headers, session)

    before = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    before_opex = float(before["cost"]["prosohm_opex"])
    before_pass = float(before["pass_through_opex_inr"])

    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": team_id,
            "name": "Customer NX seat",
            "amount": "5000",
            "purchase_date": "2026-07-01",
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


def test_expense_without_team_rejected(client, auth_headers):
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "name": "No team expense",
            "amount": "100",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
        },
    )
    # Missing required team_id → request validation (422) or business rule (400)
    assert create.status_code in (400, 422)


def test_expense_renewal_window_and_notify(client, auth_headers, session):
    from datetime import date, timedelta

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    centre_id = centres[0]["id"]
    team_id = _corporate_team_id(client, auth_headers, session)
    renewal = (date.today() + timedelta(days=5)).isoformat()

    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centre_id,
            "team_id": team_id,
            "name": "NX Mach 3",
            "vendor_name": "Siemens",
            "amount": "120000",
            "purchase_date": "2026-07-01",
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


def test_who_pays_software_default_from_team_commercial(client, auth_headers, session):
    import uuid
    from datetime import date

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name="Who Pays Team A", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"wm_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer A",
        is_active=True,
    )
    session.add(team)
    session.add(model)
    session.commit()

    terms = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "billing_mode": "subscription",
            "customer_fee_amount": "10000",
            "currency_code": "INR",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
            "customer_pays_software": True,
            "customer_pays_hardware": False,
        },
    )
    assert terms.status_code == 201, terms.text

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    sw = next(row for row in centres if row["code"] == "SW_LICENSES")
    default = client.get(
        f"/api/v1/finance/expenses/paid-by-default?team_id={team.id}&cost_centre_id={sw['id']}",
        headers=auth_headers,
    )
    assert default.status_code == 200
    assert default.json()["paid_by"] == "customer"

    before = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": sw["id"],
            "team_id": str(team.id),
            "name": "NX for Team A",
            "amount": "8000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["paid_by"] == "customer"

    after = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    assert float(after["pass_through_opex_inr"]) == float(before["pass_through_opex_inr"]) + 8000.0
    assert float(after["cost"]["prosohm_opex"]) == float(before["cost"]["prosohm_opex"])


def test_employee_cost_roster_lists_salary_required_users(client, auth_headers):
    roster = client.get("/api/v1/finance/employee-costs/roster", headers=auth_headers)
    assert roster.status_code == 200, roster.text
    rows = roster.json()
    assert len(rows) >= 1
    emails = {row["email"] for row in rows}
    assert "admin@prosohm.com" not in emails
    assert "binil@prosohm.com" in emails

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


def test_salary_exempt_admin_hidden_and_post_rejected(client, auth_headers, session):
    from app.models.finance import EmployeeCostProfile
    from decimal import Decimal
    from datetime import date

    roster = client.get("/api/v1/finance/employee-costs/roster", headers=auth_headers).json()
    assert all(row.get("requires_salary", True) for row in roster)
    assert "admin@prosohm.com" not in {row["email"] for row in roster}

    with_exempt = client.get(
        "/api/v1/finance/employee-costs/roster?include_exempt=true",
        headers=auth_headers,
    ).json()
    admin_row = next(row for row in with_exempt if row["email"] == "admin@prosohm.com")
    assert admin_row["requires_salary"] is False

    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    assert admin.requires_salary is False

    # Stale profile must not roll into Overview salary
    session.add(
        EmployeeCostProfile(
            user_id=admin.id,
            monthly_salary=Decimal("99999"),
            hourly_cost=Decimal("0"),
            currency_code="INR",
            base_monthly_salary_inr=Decimal("99999"),
            base_hourly_cost_inr=Decimal("0"),
            fx_rate=Decimal("1"),
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    before = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    salary_before = float(before["salary_cost_inr"])

    reject = client.post(
        "/api/v1/finance/employee-costs",
        headers=auth_headers,
        json={
            "user_id": str(admin.id),
            "monthly_salary": "5000",
            "hourly_cost": "10",
            "currency_code": "INR",
            "effective_from": "2026-04-01",
        },
    )
    assert reject.status_code == 400

    after = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(after["salary_cost_inr"]) == salary_before


def test_planning_board_default_requires_salary_false(session):
    from app.core.salary_eligibility import default_requires_salary_for_role

    assert default_requires_salary_for_role("Planning Board") is False
    assert default_requires_salary_for_role("Admin") is False
    assert default_requires_salary_for_role("Designer") is True

    board = session.get(User, IDS["user_planning_board"])
    assert board is not None
    assert board.requires_salary is False


def test_team_commercial_terms_in_dashboard(client, auth_headers, session):
    import uuid
    from datetime import date

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, TeamMember, User, WorkingModel

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
    # One salary-required member so rate × headcount feeds Overview
    member = session.get(User, IDS["user_binil"])
    assert member is not None
    member.requires_salary = True
    session.add(
        TeamMember(team_id=team.id, user_id=member.id, is_primary=True)
    )
    session.commit()

    create = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "customer_fee_amount": "120000",
            "currency_code": "INR",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["billing_mode"] == "subscription"

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(dash["team_commercial_fee_monthly_inr"]) >= 120000.0


def test_non_billable_member_excluded_from_retainer_fee(client, auth_headers, session):
    import uuid
    from datetime import date

    from sqlalchemy import select

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, TeamMember, User, WorkingModel

    team = Team(id=uuid.uuid4(), name="Billable Headcount Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"retainer_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Billable Test",
        is_active=True,
        is_archived=False,
    )
    session.add(team)
    session.add(model)
    billable = session.get(User, IDS["user_binil"])
    manager = session.get(User, IDS["user_planning_board"])
    assert billable is not None and manager is not None
    billable.requires_salary = True
    manager.requires_salary = True  # salary-required but not customer-billable on this team
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=billable.id,
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=manager.id,
            is_primary=False,
            is_billable_headcount=False,
        )
    )
    session.commit()

    create = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "customer_fee_amount": "10000",
            "currency_code": "INR",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["resource_count"] == 1
    assert float(body["monthly_fee_signal_inr"]) == 10000.0

    membership = session.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team.id, TeamMember.user_id == manager.id
        )
    )
    assert membership is not None
    patched = client.patch(
        f"/api/v1/teams/{team.id}/members/{membership.id}",
        headers=auth_headers,
        json={"is_billable_headcount": True},
    )
    assert patched.status_code == 200, patched.text
    listed = client.get(
        f"/api/v1/finance/team-commercial?team_id={team.id}", headers=auth_headers
    ).json()
    assert listed[0]["resource_count"] == 2


def test_team_commercial_usd_with_fy_start_effective_date(client, auth_headers, session):
    """USD terms dated at FY start must convert even when live FX was seeded mid-year."""
    import uuid
    from decimal import Decimal

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name="USD FY Commercial Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"retainer_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer USD",
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
            "customer_fee_amount": "2000",
            "currency_code": "USD",
            "billing_period": "monthly",
            "effective_from": "2026-04-01",
            "customer_pays_software": True,
            "customer_pays_hardware": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["currency_code"] == "USD"
    assert Decimal(str(body["base_fee_inr"])) == Decimal("167000.00")  # 2000 * 83.50
    assert Decimal(str(body["fx_rate"])) == Decimal("83.50")


def test_expense_patch_and_soft_delete(client, auth_headers, session):
    team_id = _corporate_team_id(client, auth_headers, session)
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": team_id,
            "name": "Editable license",
            "amount": "1000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
            "paid_by": "prosohm",
        },
    )
    assert create.status_code == 201, create.text
    expense_id = create.json()["id"]

    patched = client.patch(
        f"/api/v1/finance/expenses/{expense_id}",
        headers=auth_headers,
        json={"amount": "2500",
            "purchase_date": "2026-07-01", "name": "Editable license v2"},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["amount"]) == 2500.0
    assert patched.json()["name"] == "Editable license v2"

    deleted = client.delete(f"/api/v1/finance/expenses/{expense_id}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get("/api/v1/finance/expenses", headers=auth_headers).json()
    assert expense_id not in {row["id"] for row in listed}

    again = client.patch(
        f"/api/v1/finance/expenses/{expense_id}",
        headers=auth_headers,
        json={"amount": "1"},
    )
    assert again.status_code == 404


def test_project_based_team_commercial_hides_fee_in_overview(client, auth_headers, session):
    import uuid
    from datetime import date

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name="PB Fee Hidden", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"pb_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.project_based,
        name="Project Based",
        is_active=True,
    )
    session.add(team)
    session.add(model)
    session.commit()

    before = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    create = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "customer_fee_amount": "999999",
            "currency_code": "INR",
            "billing_period": "annual",
            "effective_from": date.today().isoformat(),
        },
    )
    assert create.status_code == 201, create.text
    assert float(create.json()["customer_fee_amount"]) == 0.0

    after = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    assert float(after["team_commercial_fee_monthly_inr"]) == float(
        before["team_commercial_fee_monthly_inr"]
    )


def test_designer_forbidden_from_roster(client):
    headers = _auth(client, "binil@prosohm.com")
    response = client.get("/api/v1/finance/employee-costs/roster", headers=headers)
    assert response.status_code == 403


def test_who_pays_software_defaults_prosohm_when_flags_false(client, auth_headers, session):
    import uuid
    from datetime import date

    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name="Who Pays Team B", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"wm_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer B",
        is_active=True,
    )
    session.add(team)
    session.add(model)
    session.commit()

    terms = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "billing_mode": "subscription",
            "customer_fee_amount": "5000",
            "currency_code": "INR",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
            "customer_pays_software": False,
            "customer_pays_hardware": False,
        },
    )
    assert terms.status_code == 201, terms.text

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    sw = next(row for row in centres if row["code"] == "SW_LICENSES")
    default = client.get(
        f"/api/v1/finance/expenses/paid-by-default?team_id={team.id}&cost_centre_id={sw['id']}",
        headers=auth_headers,
    )
    assert default.status_code == 200
    assert default.json()["paid_by"] == "prosohm"

    before = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": sw["id"],
            "team_id": str(team.id),
            "name": "NX for Team B",
            "amount": "9000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "yearly",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["paid_by"] == "prosohm"

    after = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    assert float(after["cost"]["prosohm_opex"]) == float(before["cost"]["prosohm_opex"]) + 9000.0
    assert float(after["pass_through_opex_inr"]) == float(before["pass_through_opex_inr"])


def test_dashboard_and_expenses_filter_by_team(client, auth_headers, session):
    import uuid

    from app.models.models import Team

    team_a = Team(id=uuid.uuid4(), name="Filter Team A", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Filter Team B", is_active=True)
    session.add(team_a)
    session.add(team_b)
    session.commit()

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    centre_id = centres[0]["id"]

    for team, name, amount in (
        (team_a, "A-only expense", "111"),
        (team_b, "B-only expense", "222"),
    ):
        created = client.post(
            "/api/v1/finance/expenses",
            headers=auth_headers,
            json={
                "cost_centre_id": centre_id,
                "team_id": str(team.id),
                "name": name,
                "amount": amount,
                "purchase_date": "2026-07-01",
                "currency_code": "INR",
                "nature": "opex",
                "frequency": "one_time",
                "paid_by": "prosohm",
            },
        )
        assert created.status_code == 201, created.text

    list_a = client.get(
        f"/api/v1/finance/expenses?team_id={team_a.id}", headers=auth_headers
    ).json()
    names_a = {row["name"] for row in list_a}
    assert "A-only expense" in names_a
    assert "B-only expense" not in names_a

    dash_a = client.get(
        f"/api/v1/finance/dashboard?team_id={team_a.id}", headers=auth_headers
    ).json()
    dash_all = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert dash_a.get("selected_team_id") in (str(team_a.id), team_a.id)
    assert float(dash_all["cost"]["prosohm_opex"]) >= float(dash_a["cost"]["prosohm_opex"])
    team_ids = {row["team_id"] for row in dash_all.get("by_team") or []}
    assert str(team_a.id) in team_ids or any(str(team_a.id) == tid for tid in team_ids)


def test_corporate_expense_not_on_other_team_dashboard(client, auth_headers, session):
    import uuid

    from app.models.models import Team

    corporate_id = _corporate_team_id(client, auth_headers, session)
    other = Team(id=uuid.uuid4(), name="Tooling Isolate", is_active=True)
    session.add(other)
    session.commit()

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": corporate_id,
            "name": "Shared HQ rent",
            "amount": "3333",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "monthly",
            "paid_by": "prosohm",
        },
    )
    assert create.status_code == 201, create.text

    other_expenses = client.get(
        f"/api/v1/finance/expenses?team_id={other.id}", headers=auth_headers
    ).json()
    assert "Shared HQ rent" not in {row["name"] for row in other_expenses}

    corp_expenses = client.get(
        f"/api/v1/finance/expenses?team_id={corporate_id}", headers=auth_headers
    ).json()
    assert "Shared HQ rent" in {row["name"] for row in corp_expenses}


def test_customer_default_currency(client, auth_headers, session):
    import uuid

    from app.models.models import Customer

    customer = Customer(
        id=uuid.uuid4(),
        name="USD Customer Co",
        code=f"USD{uuid.uuid4().hex[:4]}",
        is_active=True,
        default_currency_code="USD",
    )
    session.add(customer)
    session.commit()

    listed = client.get("/api/v1/customers?limit=200", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    items = rows.get("items", rows) if isinstance(rows, dict) else rows
    match = next((row for row in items if row["id"] == str(customer.id)), None)
    assert match is not None
    assert match.get("default_currency_code") == "USD"


def test_expense_requires_purchase_date(client, auth_headers, session):
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    team_id = _corporate_team_id(client, auth_headers, session)
    create = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": team_id,
            "name": "No purchase date",
            "amount": "50",
            "currency_code": "INR",
        },
    )
    assert create.status_code == 422


def test_prior_fy_expense_excluded_from_overview(client, auth_headers, session):
    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    team_id = _corporate_team_id(client, auth_headers, session)
    before = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    before_opex = float(before["cost"]["prosohm_opex"])
    assert before.get("planning_fy_start") == "2026-04-01"

    prior = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": team_id,
            "name": "Prior FY hardware",
            "amount": "7777",
            "purchase_date": "2025-03-15",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "one_time",
            "paid_by": "prosohm",
        },
    )
    assert prior.status_code == 201, prior.text
    assert prior.json()["prior_fy_excluded_from_overview"] is True

    after_prior = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(after_prior["cost"]["prosohm_opex"]) == before_opex

    current = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": centres[0]["id"],
            "team_id": team_id,
            "name": "Current FY software",
            "amount": "1111",
            "purchase_date": "2026-05-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "one_time",
            "paid_by": "prosohm",
        },
    )
    assert current.status_code == 201, current.text
    assert current.json()["prior_fy_excluded_from_overview"] is False

    after = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    assert float(after["cost"]["prosohm_opex"]) == before_opex + 1111.0

    fy_only = client.get(
        "/api/v1/finance/expenses?current_fy_only=true", headers=auth_headers
    ).json()
    names = {row["name"] for row in fy_only}
    assert "Current FY software" in names
    assert "Prior FY hardware" not in names


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
