"""Compensation change requests — 2-level approval and apply-forward."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import ProTrackValidationError
from app.models.finance import EmployeeCostProfile
from app.models.models import Role, User
from app.services import compensation_change_service as comp
from app.services import user_change_service
from tests.conftest import IDS


def _director(session) -> User:
    role = session.scalar(select(Role).where(Role.name == "Director of Engineering"))
    if role is None:
        role = Role(
            id=uuid.uuid4(), name="Director of Engineering", description="Director"
        )
        session.add(role)
        session.flush()
    user = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=f"director.{uuid.uuid4().hex[:6]}@prosohm.com",
        password_hash="x",
        first_name="Dee",
        last_name="Rector",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _employee_with_salary(session, monthly: Decimal) -> User:
    user = User(
        id=uuid.uuid4(),
        role_id=IDS["role_designer"],
        email=f"emp.{uuid.uuid4().hex[:6]}@prosohm.com",
        password_hash="x",
        first_name="Emp",
        last_name="Loyee",
        is_active=True,
        requires_salary=True,
    )
    session.add(user)
    session.flush()
    session.add(
        EmployeeCostProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            currency_code="INR",
            monthly_salary=monthly,
            hourly_cost=Decimal("0"),
            base_monthly_salary_inr=monthly,
            base_hourly_cost_inr=Decimal("0"),
            fx_rate=Decimal("1"),
            effective_from=date.today(),
            is_active=True,
        )
    )
    session.flush()
    return user


def test_hike_two_level_approval_applies_salary(session):
    admin = session.get(User, IDS["user_admin"])
    em = session.get(User, IDS["user_pm"])
    director = _director(session)
    employee = _employee_with_salary(session, Decimal("100000"))

    request = comp.create_request(
        session,
        employee=employee,
        actor=em,
        request_type="hike",
        hike_pct=Decimal("10"),
        effective_date=date.today(),
        justification="Strong year",
    )
    assert request.stage == comp.STAGE_SUGGESTED
    assert request.proposed_monthly_salary == Decimal("110000.00")

    comp.advance_request(session, request=request, action="approve-l1", actor=admin)
    assert request.stage == comp.STAGE_L1_APPROVED

    comp.advance_request(session, request=request, action="approve-l2", actor=director)
    assert request.stage == comp.STAGE_APPLIED

    session.commit()
    profile = session.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == employee.id)
    )
    assert profile.monthly_salary == Decimal("110000.00")


def test_unauthorized_l1_is_rejected(session):
    em = session.get(User, IDS["user_pm"])
    designer = session.get(User, IDS["user_binil"])
    employee = _employee_with_salary(session, Decimal("80000"))

    request = comp.create_request(
        session,
        employee=employee,
        actor=em,
        request_type="hike",
        hike_pct=Decimal("5"),
        effective_date=date.today(),
    )
    with pytest.raises(ProTrackValidationError):
        comp.advance_request(session, request=request, action="approve-l1", actor=designer)


def test_future_dated_hike_applies_on_sweep(session):
    admin = session.get(User, IDS["user_admin"])
    em = session.get(User, IDS["user_pm"])
    director = _director(session)
    employee = _employee_with_salary(session, Decimal("100000"))
    future = date.today() + timedelta(days=5)

    request = comp.create_request(
        session,
        employee=employee,
        actor=em,
        request_type="hike",
        hike_pct=Decimal("20"),
        effective_date=future,
    )
    comp.advance_request(session, request=request, action="approve-l1", actor=admin)
    comp.advance_request(session, request=request, action="approve-l2", actor=director)
    assert request.stage == comp.STAGE_L2_APPROVED

    session.commit()
    profile = session.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == employee.id)
    )
    assert profile.monthly_salary == Decimal("100000.00")

    applied = user_change_service.apply_due_compensation(session, as_of=future)
    session.commit()
    assert applied >= 1
    session.refresh(request)
    assert request.stage == comp.STAGE_APPLIED
    profile = session.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == employee.id)
    )
    assert profile.monthly_salary == Decimal("120000.00")
