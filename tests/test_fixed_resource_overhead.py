"""Fixed resource (engineers) vs management overhead role defaults."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.core.fixed_resource_eligibility import (
    default_is_billable_headcount,
    role_is_fixed_resource_default,
    role_is_management_overhead_default,
)
from app.db.phase31_overhead_role_billable_backfill import (
    ensure_phase31_overhead_role_billable_backfill,
)
from app.models.enums import WorkingModelCode
from app.models.finance import EmployeeCostProfile
from app.models.models import Team, TeamMember, User, WorkingModel
from tests.conftest import IDS


def test_role_fixed_resource_defaults():
    assert role_is_fixed_resource_default("Designer")
    assert role_is_fixed_resource_default("Surfacer")
    assert role_is_management_overhead_default("Design Leader")
    assert role_is_management_overhead_default("Engineering Manager")
    assert role_is_management_overhead_default("Planning Board")
    assert role_is_management_overhead_default("Office Administrator")
    team = Team(name="Sybridge-Sale", is_active=True)
    assert default_is_billable_headcount(team=team, role_name="Designer") is True
    assert default_is_billable_headcount(team=team, role_name="Design Leader") is False
    corp = Team(name="Corporate / Management", is_active=True)
    assert default_is_billable_headcount(team=corp, role_name="Designer") is False


def test_add_design_leader_defaults_non_billable(client, auth_headers, session):
    team = Team(id=uuid.uuid4(), name="Fixed Resource Team A", is_active=True)
    session.add(team)
    session.commit()
    leader = session.get(User, IDS["user_anurag"])  # Design Leader
    designer = session.get(User, IDS["user_binil"])
    assert leader is not None and designer is not None

    r1 = client.post(
        f"/api/v1/teams/{team.id}/members",
        headers=auth_headers,
        json={"user_id": str(leader.id)},
    )
    assert r1.status_code in (200, 201), r1.text
    assert r1.json()["is_billable_headcount"] is False

    r2 = client.post(
        f"/api/v1/teams/{team.id}/members",
        headers=auth_headers,
        json={"user_id": str(designer.id)},
    )
    assert r2.status_code in (200, 201), r2.text
    assert r2.json()["is_billable_headcount"] is True

    listed = client.get("/api/v1/teams", headers=auth_headers).json()
    items = listed["items"] if isinstance(listed, dict) and "items" in listed else listed
    row = next(t for t in items if t["id"] == str(team.id))
    assert row["member_count"] == 2
    assert row["billable_member_count"] == 1


def test_phase31_backfill_demotes_managers(session, test_engine):
    team = Team(id=uuid.uuid4(), name="Backfill Team", is_active=True)
    leader = session.get(User, IDS["user_anurag"])
    designer = session.get(User, IDS["user_binil"])
    assert leader and designer
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=leader.id,
            is_primary=True,
            is_billable_headcount=True,  # incorrect legacy
        )
    )
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=False,
            is_billable_headcount=True,
        )
    )
    session.commit()

    ensure_phase31_overhead_role_billable_backfill(test_engine)
    session.expire_all()
    mgr = (
        session.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == leader.id)
        .one()
    )
    des = (
        session.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == designer.id)
        .one()
    )
    assert mgr.is_billable_headcount is False
    assert des.is_billable_headcount is True


def test_delivery_team_salary_excludes_non_billable_primary(client, auth_headers, session):
    from app.services.finance.dashboard_service import _user_ids_for_team

    team = Team(id=uuid.uuid4(), name="Salary Scope Team", is_active=True)
    designer = session.get(User, IDS["user_binil"])
    leader = session.get(User, IDS["user_anurag"])
    assert designer and leader
    designer.requires_salary = True
    leader.requires_salary = True
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=leader.id,
            is_primary=True,  # still non-billable → excluded from delivery salary
            is_billable_headcount=False,
        )
    )
    session.add(
        EmployeeCostProfile(
            user_id=designer.id,
            base_monthly_salary_inr=Decimal("50000"),
            currency_code="INR",
            effective_from=date(2020, 1, 1),
            is_active=True,
        )
    )
    session.add(
        EmployeeCostProfile(
            user_id=leader.id,
            base_monthly_salary_inr=Decimal("90000"),
            currency_code="INR",
            effective_from=date(2020, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    ids = _user_ids_for_team(session, team.id)
    assert designer.id in ids
    assert leader.id not in ids

    from app.services.finance.dashboard_service import _salary_for_team

    salary = _salary_for_team(session, team.id, as_of=date(2026, 7, 15))
    assert float(salary) == 50000.0


def test_team_salary_includes_non_primary_billable_when_no_primary_home(
    client, auth_headers, session
):
    """People costs must hit team net profit even when is_primary was never set."""
    from app.services.finance.dashboard_service import (
        _salary_for_team,
        _team_rollups,
        _user_ids_for_team,
    )

    team = Team(id=uuid.uuid4(), name="No Primary Salary Team", is_active=True)
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.requires_salary = True
    designer.is_active = True
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=False,
            is_billable_headcount=True,
        )
    )
    session.add(
        EmployeeCostProfile(
            user_id=designer.id,
            monthly_salary=Decimal("60000"),
            hourly_cost=Decimal("0"),
            base_monthly_salary_inr=Decimal("60000"),
            base_hourly_cost_inr=Decimal("0"),
            currency_code="INR",
            effective_from=date(2020, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    # Clear any other primary memberships for this user so sole-home rule applies.
    for row in (
        session.query(TeamMember)
        .filter(TeamMember.user_id == designer.id, TeamMember.is_primary.is_(True))
        .all()
    ):
        row.is_primary = False
    session.commit()

    assert designer.id in _user_ids_for_team(session, team.id)
    salary = _salary_for_team(session, team.id, as_of=date(2026, 7, 15))
    assert float(salary) == 60000.0

    rollup = _team_rollups(
        session,
        team,
        today=date(2026, 7, 15),
        quote_revenue=Decimal("100000"),
        quote_estimated_cost=Decimal("10000"),
    )
    # Net = (100000 - 10000) - (60000 + opex) → salary must reduce net vs gross
    assert float(rollup["salary_cost_inr"]) == 60000.0
    assert float(rollup["gross_profit_inr"]) == 90000.0
    assert float(rollup["net_profit_inr"]) == float(rollup["gross_profit_inr"]) - float(
        rollup["monthly_operating_cost_inr"]
    )
    assert float(rollup["monthly_operating_cost_inr"]) >= 60000.0
    assert float(rollup["net_margin_percent"]) < float(rollup["gross_margin_percent"])


def test_team_assigned_software_opex_and_hardware_capex_hit_pnl(
    client, auth_headers, session
):
    """Software OpEx + hardware CapEx assigned to a team reduce that team's net profit."""
    from app.services.finance.dashboard_service import _team_rollups

    team = Team(id=uuid.uuid4(), name="Spend Assigned Team", is_active=True)
    session.add(team)
    session.commit()

    centres = client.get("/api/v1/finance/cost-centres", headers=auth_headers).json()
    sw = next(row for row in centres if row["code"] == "SW_LICENSES")
    hw = next(row for row in centres if row["code"] == "HARDWARE")

    soft = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": sw["id"],
            "team_id": str(team.id),
            "name": "NX for Spend Team",
            "amount": "12000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "opex",
            "frequency": "monthly",
            "paid_by": "prosohm",
        },
    )
    assert soft.status_code == 201, soft.text

    hard = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": hw["id"],
            "team_id": str(team.id),
            "name": "Workstations batch",
            "amount": "50000",
            "purchase_date": "2026-07-01",
            "currency_code": "INR",
            "nature": "capex",
            "frequency": "one_time",
            "paid_by": "prosohm",
        },
    )
    assert hard.status_code == 201, hard.text

    rollup = _team_rollups(
        session,
        team,
        today=date(2026, 7, 15),
        quote_revenue=Decimal("200000"),
        quote_estimated_cost=Decimal("20000"),
    )
    assert float(rollup["prosohm_opex_inr"]) >= 12000.0
    assert float(rollup["prosohm_capex_inr"]) >= 50000.0
    assert float(rollup["monthly_operating_cost_inr"]) >= 62000.0
    assert float(rollup["gross_profit_inr"]) == 180000.0
    assert float(rollup["net_profit_inr"]) == float(rollup["gross_profit_inr"]) - float(
        rollup["monthly_operating_cost_inr"]
    )
    assert float(rollup["net_profit_inr"]) < float(rollup["gross_profit_inr"])

    dash_team = client.get(
        f"/api/v1/finance/dashboard?team_id={team.id}", headers=auth_headers
    ).json()
    assert float(dash_team["cost"]["prosohm_opex"]) >= 12000.0
    assert float(dash_team["cost"]["capex"]) >= 50000.0

    dash_all = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    by_team = {row["team_id"]: row for row in dash_all.get("by_team") or []}
    row = by_team.get(str(team.id))
    assert row is not None
    assert float(row["prosohm_opex_inr"]) >= 12000.0
    assert float(row.get("prosohm_capex_inr") or 0) >= 50000.0


def test_retainer_counts_only_fixed_resource_roles(client, auth_headers, session):
    team = Team(id=uuid.uuid4(), name="Retainer Role Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_role_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Role Test",
        is_active=True,
        is_archived=False,
    )
    designer = session.get(User, IDS["user_binil"])
    leader = session.get(User, IDS["user_anurag"])
    assert designer and leader
    designer.requires_salary = True
    leader.requires_salary = True
    session.add(team)
    session.add(model)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=leader.id,
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
            "effective_from": date.today().replace(day=1).isoformat(),
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["resource_count"] == 1
    assert float(create.json()["monthly_fee_signal_inr"]) == 10000.0
