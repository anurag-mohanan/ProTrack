"""Phase 28 — Team member billable headcount + Corporate overheads commercial."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.phase23_finance_team_scope_schema_sync import (
    CORPORATE_TEAM_NAME,
    ensure_corporate_shared_services_team,
)
from app.models.enums import TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import Team, TeamMember, WorkingModel
from app.services.finance.commercial_fee_rules import billing_mode_for_strategy


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase28_team_member_billable_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "team_members", "is_billable_headcount"):
                connection.execute(
                    text(
                        "ALTER TABLE team_members ADD COLUMN is_billable_headcount "
                        "BOOLEAN NOT NULL DEFAULT 1"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE team_members ADD COLUMN IF NOT EXISTS is_billable_headcount "
                    "BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        corporate = ensure_corporate_shared_services_team(session)
        corporate.description = (
            "Management / overhead — HQ and shared services. "
            "Not customer-paid retainer headcount."
        )
        from app.models.models import TeamMember

        for member in session.scalars(
            select(TeamMember).where(TeamMember.team_id == corporate.id)
        ).all():
            member.is_billable_headcount = False

        overheads = session.scalar(
            select(WorkingModel).where(
                WorkingModel.strategy_key == WorkingModelCode.overheads,
                WorkingModel.is_active.is_(True),
            )
        )
        if overheads is None:
            overheads = WorkingModel(
                code="overheads",
                name="Overheads / Management",
                strategy_key=WorkingModelCode.overheads,
                description="Management and shared overhead — not customer delivery billing.",
                sort_order=3,
                is_active=True,
                is_archived=False,
            )
            session.add(overheads)
            session.flush()

        active_terms = session.scalars(
            select(TeamCommercialTerms).where(
                TeamCommercialTerms.team_id == corporate.id,
                TeamCommercialTerms.is_active.is_(True),
            )
        ).all()
        if not active_terms:
            session.add(
                TeamCommercialTerms(
                    team_id=corporate.id,
                    working_model_id=overheads.id,
                    billing_mode=billing_mode_for_strategy(WorkingModelCode.overheads),
                    customer_fee_amount=Decimal("0"),
                    currency_code="INR",
                    base_fee_inr=Decimal("0"),
                    fx_rate=Decimal("1"),
                    billing_period=TeamBillingPeriod.monthly,
                    effective_from=date(2020, 4, 1),
                    notes="Seeded: Corporate management / overheads — no customer fee",
                    customer_pays_software=False,
                    customer_pays_hardware=False,
                    is_active=True,
                )
            )
        else:
            for term in active_terms:
                term.working_model_id = overheads.id
                term.billing_mode = billing_mode_for_strategy(WorkingModelCode.overheads)
                term.customer_fee_amount = Decimal("0")
                term.base_fee_inr = Decimal("0")

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_corporate_team(team: Team | None) -> bool:
    from app.db.phase23_finance_team_scope_schema_sync import LEGACY_CORPORATE_TEAM_NAMES

    return bool(
        team
        and team.name in LEGACY_CORPORATE_TEAM_NAMES | {"Management"}
    )
