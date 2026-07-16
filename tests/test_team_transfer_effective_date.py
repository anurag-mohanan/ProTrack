"""Dated primary-team transfer — finance proration by calendar days."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.phase36_team_membership_periods_schema_sync import backfill_membership_periods
from app.models.models import Team, TeamMember, User
from app.services.finance.employment_cost import primary_team_salary_factor
from tests.conftest import IDS


def _q_factor(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def test_transfer_effective_date_prorates_july_salary(client, session):
    """Prosohm Eng → Redoe on 20 Jul: 19/31 source, 12/31 target for July."""
    source = Team(id=uuid.uuid4(), name="Prosohm Eng", colour="#1565c0", is_active=True)
    target = Team(id=uuid.uuid4(), name="Redoe", colour="#c62828", is_active=True)
    session.add_all([source, target])
    session.commit()

    user = session.get(User, IDS["user_binil"])
    assert user is not None
    user.team_id = source.id
    user.joining_date = date(2020, 1, 1)
    session.add(
        TeamMember(
            team_id=source.id,
            user_id=user.id,
            role_within_team="Designer",
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.commit()
    backfill_membership_periods(session)
    session.commit()

    member = session.scalar(
        select(TeamMember).where(
            TeamMember.team_id == source.id,
            TeamMember.user_id == user.id,
        )
    )
    assert member is not None

    transfer = client.post(
        f"/api/v1/teams/{source.id}/members/{member.id}/transfer",
        json={
            "target_team_id": str(target.id),
            "effective_from": "2026-07-20",
        },
        headers=client.auth_headers,
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["team_id"] == str(target.id)

    factor_source = primary_team_salary_factor(
        session, user_id=user.id, team_id=source.id, as_of=date(2026, 7, 15)
    )
    factor_target = primary_team_salary_factor(
        session, user_id=user.id, team_id=target.id, as_of=date(2026, 7, 25)
    )
    assert factor_source == _q_factor(Decimal(19) / Decimal(31))
    assert factor_target == _q_factor(Decimal(12) / Decimal(31))


def test_future_dated_transfer_keeps_live_home_until_effective(client, session):
    source = Team(id=uuid.uuid4(), name="Source Future", colour="#111111", is_active=True)
    target = Team(id=uuid.uuid4(), name="Target Future", colour="#222222", is_active=True)
    session.add_all([source, target])
    session.commit()

    user = session.get(User, IDS["user_senior_designer"])
    assert user is not None
    user.team_id = source.id
    session.add(
        TeamMember(
            team_id=source.id,
            user_id=user.id,
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.commit()
    backfill_membership_periods(session)
    session.commit()

    member = session.scalar(
        select(TeamMember).where(
            TeamMember.team_id == source.id,
            TeamMember.user_id == user.id,
        )
    )
    assert member is not None

    future = date.today().replace(year=date.today().year + 1, month=1, day=15)
    transfer = client.post(
        f"/api/v1/teams/{source.id}/members/{member.id}/transfer",
        json={
            "target_team_id": str(target.id),
            "effective_from": future.isoformat(),
        },
        headers=client.auth_headers,
    )
    assert transfer.status_code == 200, transfer.text

    session.refresh(user)
    session.refresh(member)
    assert user.team_id == source.id
    assert member.is_primary is True

    factor_target = primary_team_salary_factor(
        session, user_id=user.id, team_id=target.id, as_of=date.today()
    )
    assert factor_target == Decimal("0")
