"""Retainer fees convert USD with FX as of the 1st of the month."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import TeamBillingMode, TeamBillingPeriod, WorkingModelCode
from app.models.finance import FxRate, TeamCommercialTerms
from app.models.models import Team, TeamMember, User, WorkingModel
from app.services.finance.retainer_fee import (
    prorated_retainer_amount_for_term,
    retainer_fx_date_for_month,
)
from tests.conftest import IDS


def test_retainer_fx_date_is_month_start():
    assert retainer_fx_date_for_month(date(2026, 7, 24)) == date(2026, 7, 1)


def test_retainer_usd_fee_uses_month_start_fx_not_term_snapshot(session):
    """$3000 × July-1 FX, even if term was saved mid-month at a different rate."""
    as_of = date(2026, 7, 24)
    team = Team(id=uuid.uuid4(), name="Retainer Month FX Team", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_fx_{uuid.uuid4().hex[:6]}",
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
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
            effective_from=date(2026, 1, 1),
        )
    )
    # Term active for the whole month so FX is the only variable under test.
    session.add(
        TeamCommercialTerms(
            team_id=team.id,
            working_model_id=model.id,
            billing_mode=TeamBillingMode.subscription,
            customer_fee_amount=Decimal("3000"),
            currency_code="USD",
            base_fee_inr=Decimal("250500.00"),  # 3000 × 83.50 seed — outdated for July
            fx_rate=Decimal("83.50000000"),
            billing_period=TeamBillingPeriod.monthly,
            effective_from=date(2026, 7, 1),
            is_active=True,
        )
    )
    session.add(
        FxRate(
            from_currency="USD",
            to_currency="INR",
            rate=Decimal("86.25000000"),
            effective_date=date(2026, 7, 1),
            source="test:month-start",
        )
    )
    session.commit()

    term = session.query(TeamCommercialTerms).filter_by(team_id=team.id).one()
    fee = prorated_retainer_amount_for_term(session, term, as_of=as_of)
    assert fee == Decimal("258750.00")  # 3000 × 86.25
