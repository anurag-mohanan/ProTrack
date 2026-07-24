"""Regression tests for finance calculation correctness (P&L-critical)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import ensure_corporate_shared_services_team
from app.models.enums import CostFrequency, CostNature, ExpensePaidBy
from app.models.finance import CostCentre, EmployeeCostProfile, Expense, Quote, QuoteRevision
from app.models.models import Customer, Team, TeamMember, User
from app.services.finance.dashboard_service import (
    _expense_sum,
    _quote_revenue_cost,
    _salary_for_team,
)
from app.services.finance.employment_cost import expense_month_factor, primary_team_salary_factor


def test_expense_month_factor_mid_month_end_after_as_of():
    """Leave-style: expense ended mid-month still prorates when as_of is later in month."""
    expense = SimpleNamespace(
        is_active=True,
        end_date=date(2026, 7, 15),
        start_date=date(2026, 4, 1),
        purchase_date=date(2026, 4, 1),
    )
    factor = expense_month_factor(expense, as_of=date(2026, 7, 24))
    assert factor == (Decimal(15) / Decimal(31)).quantize(Decimal("0.0001"))


def test_expense_month_factor_mid_month_start():
    expense = SimpleNamespace(
        is_active=True,
        end_date=None,
        start_date=date(2026, 7, 16),
        purchase_date=date(2026, 7, 16),
    )
    factor = expense_month_factor(expense, as_of=date(2026, 7, 24))
    assert factor == (Decimal(16) / Decimal(31)).quantize(Decimal("0.0001"))


def test_company_quote_revenue_uses_current_revision_only(session):
    team = Team(id=uuid.uuid4(), name="Quote Fix Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Quote Fix Customer",
        code=f"QF{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"QF-{uuid.uuid4().hex[:6]}",
        currency_code="INR",
        current_version=2,
        current_revision="A",
        is_active=True,
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=1,
            revision="A",
            base_quoted_revenue_inr=Decimal("100000"),
            base_estimated_cost_inr=Decimal("40000"),
            quoted_revenue=Decimal("100000"),
            estimated_cost=Decimal("40000"),
            fx_date=date(2026, 7, 1),
        )
    )
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=2,
            revision="A",
            base_quoted_revenue_inr=Decimal("50000"),
            base_estimated_cost_inr=Decimal("20000"),
            quoted_revenue=Decimal("50000"),
            estimated_cost=Decimal("20000"),
            fx_date=date(2026, 7, 1),
        )
    )
    session.commit()

    revenue, cost = _quote_revenue_cost(session, team_id=None)
    assert revenue == Decimal("50000.00")
    assert cost == Decimal("20000.00")


def test_prior_fy_recurring_opex_still_in_monthly_sum(session):
    home = ensure_corporate_shared_services_team(session)
    centre = session.scalar(select(CostCentre).limit(1))
    assert centre is not None
    session.add(
        Expense(
            id=uuid.uuid4(),
            cost_centre_id=centre.id,
            team_id=home.id,
            name="Prior FY rent still active",
            nature=CostNature.opex,
            frequency=CostFrequency.monthly,
            currency_code="INR",
            amount=Decimal("10000"),
            base_amount_inr=Decimal("10000"),
            fx_rate=Decimal("1"),
            fx_date=date(2025, 5, 1),
            purchase_date=date(2025, 5, 1),
            start_date=date(2025, 5, 1),
            paid_by=ExpensePaidBy.prosohm,
            is_active=True,
            is_recurring=True,
        )
    )
    session.commit()
    total = _expense_sum(
        session,
        team_id=home.id,
        paid_by=ExpensePaidBy.prosohm,
        nature=CostNature.opex,
        fy_start=date(2026, 4, 1),
        as_of=date(2026, 7, 15),
    )
    assert total >= Decimal("10000.00")


def test_sole_home_salary_not_double_counted(session):
    from tests.conftest import IDS

    team_a = Team(id=uuid.uuid4(), name="Sole A", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Sole B", is_active=True)
    session.add_all([team_a, team_b])
    user = session.get(User, IDS["user_binil"])
    assert user is not None
    user.requires_salary = True
    user.joining_date = date(2025, 1, 1)
    user.is_active = True
    # Clear existing memberships for a clean sole-home case
    for row in session.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all():
        session.delete(row)
    session.flush()
    session.add(
        TeamMember(
            id=uuid.uuid4(),
            team_id=team_a.id,
            user_id=user.id,
            is_primary=False,
            is_billable_headcount=True,
            effective_from=date(2025, 1, 1),
        )
    )
    session.add(
        TeamMember(
            id=uuid.uuid4(),
            team_id=team_b.id,
            user_id=user.id,
            is_primary=False,
            is_billable_headcount=True,
            effective_from=date(2025, 6, 1),
        )
    )
    profile = session.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == user.id)
    )
    if profile is None:
        session.add(
            EmployeeCostProfile(
                id=uuid.uuid4(),
                user_id=user.id,
                currency_code="INR",
                monthly_salary=Decimal("31000"),
                base_monthly_salary_inr=Decimal("31000"),
                hourly_cost=Decimal("0"),
                base_hourly_cost_inr=Decimal("0"),
                fx_rate=Decimal("1"),
                effective_from=date(2025, 1, 1),
                is_active=True,
            )
        )
    else:
        profile.base_monthly_salary_inr = Decimal("31000")
        profile.monthly_salary = Decimal("31000")
        profile.is_active = True
    session.commit()

    as_of = date(2026, 7, 15)
    sal_a = _salary_for_team(session, team_a.id, as_of=as_of)
    sal_b = _salary_for_team(session, team_b.id, as_of=as_of)
    assert sal_a == Decimal("31000.00")
    assert sal_b == Decimal("0.00")
    fa = primary_team_salary_factor(session, user_id=user.id, team_id=team_a.id, as_of=as_of)
    fb = primary_team_salary_factor(session, user_id=user.id, team_id=team_b.id, as_of=as_of)
    assert fa == Decimal("1")
    assert fb == Decimal("0")
