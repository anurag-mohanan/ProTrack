"""Dated user lifecycle changes — promotions and billing (working-model)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models.enums import WorkingModelCode
from app.models.models import (
    Team,
    TeamMember,
    User,
    UserWorkingModelPeriod,
    WorkingModel,
)
from app.services import user_change_service
from tests.conftest import IDS


def _make_employee(session, role_id) -> User:
    user = User(
        id=uuid.uuid4(),
        role_id=role_id,
        email=f"life.{uuid.uuid4().hex[:8]}@prosohm.com",
        password_hash="x",
        first_name="Life",
        last_name="Cycle",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def test_promotion_applies_immediately_when_effective_today(session):
    employee = _make_employee(session, IDS["role_designer"])
    user_change_service.record_promotion(
        session,
        user=employee,
        new_role_id=IDS["role_senior_designer"],
        new_designation="Senior Designer",
        effective_date=date.today(),
    )
    session.commit()
    session.refresh(employee)
    assert employee.role_id == IDS["role_senior_designer"]
    assert employee.designation == "Senior Designer"


def test_future_promotion_is_pending_until_sweep(session):
    employee = _make_employee(session, IDS["role_designer"])
    tomorrow = date.today() + timedelta(days=1)
    user_change_service.record_promotion(
        session,
        user=employee,
        new_role_id=IDS["role_senior_designer"],
        effective_date=tomorrow,
    )
    session.commit()
    session.refresh(employee)
    assert employee.role_id == IDS["role_designer"]

    applied = user_change_service.apply_due_lifecycle(session, as_of=tomorrow)
    session.commit()
    session.refresh(employee)
    assert applied >= 1
    assert employee.role_id == IDS["role_senior_designer"]


def test_billing_change_records_dated_period(session):
    employee = _make_employee(session, IDS["role_designer"])
    wm = WorkingModel(
        id=uuid.uuid4(),
        code=f"ded-{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.overheads,
        name="Dedicated",
        sort_order=1,
    )
    session.add(wm)
    session.flush()

    user_change_service.record_billing_change(
        session,
        user=employee,
        new_working_model_id=wm.id,
        effective_date=date.today(),
    )
    session.commit()
    session.refresh(employee)
    assert employee.default_working_model_id == wm.id

    period = session.scalar(
        select(UserWorkingModelPeriod).where(
            UserWorkingModelPeriod.user_id == employee.id,
            UserWorkingModelPeriod.effective_to.is_(None),
        )
    )
    assert period is not None
    assert period.working_model_id == wm.id


def test_future_transfer_updates_live_membership_on_sweep(session):
    employee = _make_employee(session, IDS["role_designer"])
    source = Team(id=uuid.uuid4(), name=f"Src {uuid.uuid4().hex[:6]}", colour="#111", is_active=True)
    target = Team(id=uuid.uuid4(), name=f"Tgt {uuid.uuid4().hex[:6]}", colour="#222", is_active=True)
    session.add_all([source, target])
    session.flush()
    session.add(
        TeamMember(
            team_id=source.id,
            user_id=employee.id,
            role_within_team="Designer",
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    employee.team_id = source.id
    session.flush()

    future = date.today() + timedelta(days=3)
    user_change_service.record_transfer(
        session,
        user=employee,
        target_team_id=target.id,
        effective_date=future,
        update_reporting_manager=False,
    )
    session.commit()
    session.refresh(employee)
    # Future-dated: live home stays on source until the effective date.
    assert employee.team_id == source.id

    user_change_service.apply_due_lifecycle(session, as_of=future)
    session.commit()
    session.refresh(employee)
    assert employee.team_id == target.id
    target_member = session.scalar(
        select(TeamMember).where(
            TeamMember.user_id == employee.id,
            TeamMember.team_id == target.id,
        )
    )
    assert target_member is not None and target_member.is_primary is True
