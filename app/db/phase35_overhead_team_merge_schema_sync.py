"""Phase 35 — Merge Management + Corporate / Shared Services → Corporate / Management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.phase23_finance_team_scope_schema_sync import (
    CORPORATE_TEAM_NAME,
    LEGACY_CORPORATE_TEAM_NAMES,
    ensure_corporate_shared_services_team,
)
from app.models.finance import Expense, Quote, TeamCommercialTerms
from app.models.models import Customer, Project, ProjectTemplate, Team, TeamMember, User

LEGACY_MANAGEMENT_TEAM_NAME = "Management"


def _reassign_team_id(session: Session, *, from_id, to_id) -> None:
    if from_id == to_id:
        return

    for expense in session.scalars(select(Expense).where(Expense.team_id == from_id)).all():
        expense.team_id = to_id

    for quote in session.scalars(select(Quote).where(Quote.team_id == from_id)).all():
        quote.team_id = to_id

    for project in session.scalars(select(Project).where(Project.team_id == from_id)).all():
        project.team_id = to_id

    for template in session.scalars(
        select(ProjectTemplate).where(ProjectTemplate.default_team_id == from_id)
    ).all():
        template.default_team_id = to_id

    for customer in session.scalars(
        select(Customer).where(Customer.default_team_id == from_id)
    ).all():
        customer.default_team_id = to_id

    for user in session.scalars(select(User).where(User.team_id == from_id)).all():
        user.team_id = to_id

    # Team members: unique (team_id, user_id) — merge carefully.
    target_members = {
        m.user_id: m
        for m in session.scalars(select(TeamMember).where(TeamMember.team_id == to_id)).all()
    }
    for member in list(
        session.scalars(select(TeamMember).where(TeamMember.team_id == from_id)).all()
    ):
        existing = target_members.get(member.user_id)
        if existing is None:
            member.team_id = to_id
            member.is_billable_headcount = False
            target_members[member.user_id] = member
        else:
            if member.is_primary and not existing.is_primary:
                existing.is_primary = True
                # Clear other primaries for this user on other teams if we stole primary
                for other in session.scalars(
                    select(TeamMember).where(
                        TeamMember.user_id == member.user_id,
                        TeamMember.id != existing.id,
                        TeamMember.is_primary.is_(True),
                    )
                ).all():
                    other.is_primary = False
            existing.is_billable_headcount = False
            session.delete(member)

    for term in session.scalars(
        select(TeamCommercialTerms).where(TeamCommercialTerms.team_id == from_id)
    ).all():
        term.is_active = False
        term.notes = (term.notes or "") + " [merged into Corporate / Management]"


def merge_legacy_management_into_overhead_home(session: Session) -> Team:
    """Rename legacy Corporate + absorb Management into Corporate / Management."""
    home = ensure_corporate_shared_services_team(session)

    # Rename any other legacy corporate-named active teams into home (should be rare).
    for legacy_name in LEGACY_CORPORATE_TEAM_NAMES:
        if legacy_name == CORPORATE_TEAM_NAME:
            continue
        legacy = session.scalar(select(Team).where(Team.name == legacy_name))
        if legacy is None or legacy.id == home.id:
            continue
        _reassign_team_id(session, from_id=legacy.id, to_id=home.id)
        legacy.is_active = False
        legacy.description = (legacy.description or "") + " [merged into Corporate / Management]"

    management = session.scalar(
        select(Team).where(Team.name == LEGACY_MANAGEMENT_TEAM_NAME)
    )
    if management is not None and management.id != home.id:
        _reassign_team_id(session, from_id=management.id, to_id=home.id)
        management.is_active = False
        management.description = (
            (management.description or "")
            + " [merged into Corporate / Management — do not reactivate]"
        )

    home.name = CORPORATE_TEAM_NAME
    home.is_active = True
    home.description = (
        "Corporate & management overhead home — leadership salaries and shared HQ OpEx "
        "(not customer billable headcount)."
    )
    for member in session.scalars(
        select(TeamMember).where(TeamMember.team_id == home.id)
    ).all():
        member.is_billable_headcount = False

    session.flush()
    return home


def ensure_phase35_overhead_team_merge_foundation(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        merge_legacy_management_into_overhead_home(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
