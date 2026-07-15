"""Last working day proration + Management team overhead."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.db.phase33_management_team_schema_sync import (
    MANAGEMENT_TEAM_NAME,
    ensure_management_team,
)
from app.services.finance.employment_cost import (
    employment_salary_factor,
    expense_month_factor,
    user_counts_for_headcount,
)


def test_employment_salary_factor_mid_month_leave():
    user = SimpleNamespace(
        joining_date=None,
        leaving_date=date(2026, 7, 15),
    )
    # July has 31 days; employed 1..15 → 15/31
    factor = employment_salary_factor(user, as_of=date(2026, 7, 20))
    assert factor == (Decimal(15) / Decimal(31)).quantize(Decimal("0.0001"))
    assert employment_salary_factor(user, as_of=date(2026, 8, 1)) == Decimal("0")
    assert user_counts_for_headcount(user, as_of=date(2026, 7, 15)) is True
    assert user_counts_for_headcount(user, as_of=date(2026, 7, 16)) is False


def test_expense_ends_before_as_of():
    expense = SimpleNamespace(
        is_active=True,
        end_date=date(2026, 6, 30),
        start_date=date(2026, 4, 1),
        purchase_date=date(2026, 4, 1),
    )
    assert expense_month_factor(expense, as_of=date(2026, 7, 1)) == Decimal("0")


def test_management_team_seeded(client, auth_headers, session):
    team = ensure_management_team(session)
    session.commit()
    assert team.name == MANAGEMENT_TEAM_NAME
    teams = client.get("/api/v1/lookups/teams", headers=auth_headers)
    assert teams.status_code == 200
    names = {row["name"] for row in teams.json()}
    assert MANAGEMENT_TEAM_NAME in names


def test_dashboard_overhead_includes_management(client, auth_headers):
    response = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert response.status_code == 200
    overhead = response.json()["overhead"]
    assert overhead.get("management_team_name") == MANAGEMENT_TEAM_NAME
    assert "overhead_management_salary_inr" in overhead
