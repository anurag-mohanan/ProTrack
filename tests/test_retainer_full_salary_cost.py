"""Retainer teams charge full monthly CTC into team operating cost."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import TeamBillingMode, TeamBillingPeriod, WorkingModelCode
from app.models.finance import EmployeeCostProfile, TeamCommercialTerms
from app.models.models import Team, TeamMember, User, WorkingModel
from app.services.finance.dashboard_service import _salary_for_team
from app.services.finance.employment_cost import primary_team_salary_factor
from tests.conftest import IDS


def test_retainer_team_salary_uses_full_ctc_not_day_proration(session):
    as_of = date(2026, 7, 24)
    team = Team(id=uuid.uuid4(), name="Retainer Full Salary Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_full_sal_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer",
        is_active=True,
        is_archived=False,
    )
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.requires_salary = True
    designer.is_active = True
    designer.joining_date = date(2020, 1, 1)
    session.add_all([team, model])
    session.flush()
    # Mid-month primary home → day factor would be partial without retainer rule.
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
            effective_from=date(2026, 7, 5),
        )
    )
    session.add(
        TeamCommercialTerms(
            team_id=team.id,
            working_model_id=model.id,
            billing_mode=TeamBillingMode.subscription,
            customer_fee_amount=Decimal("3000"),
            currency_code="USD",
            base_fee_inr=Decimal("250500"),
            billing_period=TeamBillingPeriod.monthly,
            effective_from=date(2026, 7, 1),
            is_active=True,
        )
    )
    session.add(
        EmployeeCostProfile(
            user_id=designer.id,
            monthly_salary=Decimal("80000"),
            hourly_cost=Decimal("0"),
            base_monthly_salary_inr=Decimal("80000"),
            base_hourly_cost_inr=Decimal("0"),
            currency_code="INR",
            effective_from=date(2020, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    day_factor = primary_team_salary_factor(
        session, user_id=designer.id, team_id=team.id, as_of=as_of
    )
    assert day_factor < Decimal("1")
    assert day_factor > Decimal("0")

    salary = _salary_for_team(session, team.id, as_of=as_of)
    assert salary == Decimal("80000.00")


def test_project_based_team_salary_still_day_prorates(session):
    as_of = date(2026, 7, 24)
    team = Team(id=uuid.uuid4(), name="Quote Salary Prorate Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"pb_sal_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.project_based,
        name="Project Based",
        is_active=True,
        is_archived=False,
    )
    designer = session.get(User, IDS["user_senior_designer"])
    assert designer is not None
    designer.requires_salary = True
    designer.is_active = True
    designer.joining_date = date(2020, 1, 1)
    session.add_all([team, model])
    session.flush()
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
            effective_from=date(2026, 7, 5),
        )
    )
    session.add(
        TeamCommercialTerms(
            team_id=team.id,
            working_model_id=model.id,
            billing_mode=TeamBillingMode.project_based,
            customer_fee_amount=Decimal("0"),
            currency_code="INR",
            base_fee_inr=Decimal("0"),
            billing_period=TeamBillingPeriod.one_time,
            effective_from=date(2026, 7, 1),
            is_active=True,
        )
    )
    session.add(
        EmployeeCostProfile(
            user_id=designer.id,
            monthly_salary=Decimal("62000"),
            hourly_cost=Decimal("0"),
            base_monthly_salary_inr=Decimal("62000"),
            base_hourly_cost_inr=Decimal("0"),
            currency_code="INR",
            effective_from=date(2020, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    day_factor = primary_team_salary_factor(
        session, user_id=designer.id, team_id=team.id, as_of=as_of
    )
    expected = (Decimal("62000") * day_factor).quantize(Decimal("0.01"))
    salary = _salary_for_team(session, team.id, as_of=as_of)
    assert salary == expected
    assert salary < Decimal("62000")
