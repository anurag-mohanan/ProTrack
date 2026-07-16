"""Phase 33 — Overhead role backfill onto Corporate / Management (legacy Management alias)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.fixed_resource_eligibility import role_is_management_overhead_default
from app.core.permissions import get_role_name
from app.db.phase23_finance_team_scope_schema_sync import (
    CORPORATE_TEAM_NAME,
    LEGACY_CORPORATE_TEAM_NAMES,
    ensure_corporate_shared_services_team,
)
from app.models.enums import TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import Team, TeamMember, User, WorkingModel
from app.services.finance.commercial_fee_rules import billing_mode_for_strategy

# Kept for imports/tests — now aliases the unified overhead home.
MANAGEMENT_TEAM_NAME = CORPORATE_TEAM_NAME
LEGACY_MANAGEMENT_TEAM_NAME = "Management"
_OVERHEAD_HOME_NAMES = frozenset(LEGACY_CORPORATE_TEAM_NAMES | {LEGACY_MANAGEMENT_TEAM_NAME})


def ensure_management_team(session: Session) -> Team:
    """Alias: overhead people home is Corporate / Management (no separate Management team)."""
    return ensure_corporate_shared_services_team(session)


def is_management_team(team: Team | None) -> bool:
    return is_overhead_home_team(team)


def is_overhead_home_team(team: Team | None) -> bool:
    return bool(team and team.name in _OVERHEAD_HOME_NAMES)


def ensure_phase33_management_team_foundation(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        home = ensure_corporate_shared_services_team(session)

        overheads = session.scalar(
            select(WorkingModel).where(
                WorkingModel.strategy_key == WorkingModelCode.overheads,
                WorkingModel.is_active.is_(True),
            )
        )
        if overheads is None:
            overheads = session.scalar(
                select(WorkingModel).where(
                    WorkingModel.code == "overheads",
                    WorkingModel.is_active.is_(True),
                )
            )

        active_terms = list(
            session.scalars(
                select(TeamCommercialTerms).where(
                    TeamCommercialTerms.team_id == home.id,
                    TeamCommercialTerms.is_active.is_(True),
                )
            ).all()
        )
        if not active_terms and overheads is not None:
            session.add(
                TeamCommercialTerms(
                    team_id=home.id,
                    working_model_id=overheads.id,
                    billing_mode=billing_mode_for_strategy(WorkingModelCode.overheads),
                    customer_fee_amount=Decimal("0"),
                    currency_code="INR",
                    base_fee_inr=Decimal("0"),
                    fx_rate=Decimal("1"),
                    billing_period=TeamBillingPeriod.monthly,
                    effective_from=date(2020, 4, 1),
                    notes="Seeded: Corporate / Management overheads — no customer fee",
                    customer_pays_software=False,
                    customer_pays_hardware=False,
                    is_active=True,
                )
            )
        else:
            for term in active_terms:
                if overheads is not None:
                    term.working_model_id = overheads.id
                term.billing_mode = billing_mode_for_strategy(WorkingModelCode.overheads)
                term.customer_fee_amount = Decimal("0")
                term.base_fee_inr = Decimal("0")

        users = session.scalars(select(User).where(User.is_active.is_(True))).all()
        for user in users:
            role = get_role_name(session, user)
            if not role_is_management_overhead_default(role):
                continue
            memberships = list(
                session.scalars(
                    select(TeamMember).where(TeamMember.user_id == user.id)
                ).all()
            )
            already = next((m for m in memberships if m.team_id == home.id), None)
            if already is None:
                for m in memberships:
                    if m.is_primary:
                        m.is_primary = False
                session.add(
                    TeamMember(
                        team_id=home.id,
                        user_id=user.id,
                        is_primary=True,
                        is_billable_headcount=False,
                    )
                )
            else:
                already.is_primary = True
                already.is_billable_headcount = False
                for m in memberships:
                    if m.id != already.id and m.is_primary:
                        m.is_primary = False
            user.team_id = home.id

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
