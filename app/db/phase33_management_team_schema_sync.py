"""Phase 33 — Management team for overhead salaries + role backfill."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.fixed_resource_eligibility import role_is_management_overhead_default
from app.core.permissions import get_role_name
from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME
from app.models.enums import TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import Team, TeamMember, User, WorkingModel
from app.services.finance.commercial_fee_rules import billing_mode_for_strategy

MANAGEMENT_TEAM_NAME = "Management"


def ensure_management_team(session: Session) -> Team:
    team = session.scalar(select(Team).where(Team.name == MANAGEMENT_TEAM_NAME))
    if team is None:
        team = Team(
            name=MANAGEMENT_TEAM_NAME,
            description=(
                "Engineering / design leadership and office administration — "
                "overhead salaries (not customer billable headcount)."
            ),
            is_active=True,
        )
        session.add(team)
        session.flush()
    return team


def is_management_team(team: Team | None) -> bool:
    return bool(team and team.name == MANAGEMENT_TEAM_NAME)


def is_overhead_home_team(team: Team | None) -> bool:
    return bool(team and team.name in {CORPORATE_TEAM_NAME, MANAGEMENT_TEAM_NAME})


def ensure_phase33_management_team_foundation(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        management = ensure_management_team(session)

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
                    TeamCommercialTerms.team_id == management.id,
                    TeamCommercialTerms.is_active.is_(True),
                )
            ).all()
        )
        if not active_terms and overheads is not None:
            session.add(
                TeamCommercialTerms(
                    team_id=management.id,
                    working_model_id=overheads.id,
                    billing_mode=billing_mode_for_strategy(WorkingModelCode.overheads),
                    customer_fee_amount=Decimal("0"),
                    currency_code="INR",
                    base_fee_inr=Decimal("0"),
                    fx_rate=Decimal("1"),
                    billing_period=TeamBillingPeriod.monthly,
                    effective_from=date(2020, 4, 1),
                    notes="Seeded: Management overheads — no customer fee",
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
            already = next((m for m in memberships if m.team_id == management.id), None)
            if already is None:
                for m in memberships:
                    if m.is_primary:
                        m.is_primary = False
                session.add(
                    TeamMember(
                        team_id=management.id,
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
            user.team_id = management.id

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
