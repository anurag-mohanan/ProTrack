"""Day-prorated retainer / subscription customer billing."""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import TeamBillingMode, TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import Team, TeamMember, User, WorkingModel
from app.services.finance.retainer_fee import (
    billable_team_month_factor,
    prorated_retainer_amount_for_term,
    team_retainer_fee_monthly,
)
from tests.conftest import IDS


def test_mid_month_resource_prorates_retainer_fee(session):
    """Resource added on the 23rd → bill only balance days of the month."""
    as_of = date(2026, 7, 31)
    days_in_month = calendar.monthrange(2026, 7)[1]
    assert days_in_month == 31
    start = date(2026, 7, 23)

    team = Team(id=uuid.uuid4(), name="Prorate Retainer Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_prorate_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Prorate",
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
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
            effective_from=start,
        )
    )
    session.add(
        TeamCommercialTerms(
            team_id=team.id,
            working_model_id=model.id,
            billing_mode=TeamBillingMode.subscription,
            customer_fee_amount=Decimal("31000"),
            currency_code="INR",
            base_fee_inr=Decimal("31000"),
            billing_period=TeamBillingPeriod.monthly,
            effective_from=date(2026, 7, 1),
            is_active=True,
        )
    )
    session.commit()

    factor = billable_team_month_factor(
        session, user_id=designer.id, team_id=team.id, as_of=as_of
    )
    # 23..31 inclusive = 9 days
    assert factor == (Decimal("9") / Decimal("31")).quantize(Decimal("0.0001"))

    fee = team_retainer_fee_monthly(session, team_id=team.id, as_of=as_of)
    expected = (Decimal("31000") * factor).quantize(Decimal("0.01"))
    assert fee == expected


def test_full_month_resource_bills_full_retainer(session):
    as_of = date(2026, 7, 15)
    team = Team(id=uuid.uuid4(), name="Full Month Retainer Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_full_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Full",
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
            effective_from=date(2026, 1, 1),
        )
    )
    term = TeamCommercialTerms(
        team_id=team.id,
        working_model_id=model.id,
        billing_mode=TeamBillingMode.subscription,
        customer_fee_amount=Decimal("10000"),
        currency_code="INR",
        base_fee_inr=Decimal("10000"),
        billing_period=TeamBillingPeriod.monthly,
        effective_from=date(2026, 1, 1),
        is_active=True,
    )
    session.add(term)
    session.commit()

    assert billable_team_month_factor(
        session, user_id=designer.id, team_id=team.id, as_of=as_of
    ) == Decimal("1")
    assert prorated_retainer_amount_for_term(session, term, as_of=as_of) == Decimal("10000.00")
