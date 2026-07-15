"""Phase 31 — Force management/overhead roles off customer billable headcount."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.fixed_resource_eligibility import (
    default_is_billable_headcount,
    role_is_fixed_resource_default,
)
from app.core.permissions import get_role_name
from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME
from app.models.models import Team, TeamMember, User


def ensure_phase31_overhead_role_billable_backfill(engine: Engine) -> None:
    """Demote non-delivery roles (and Corporate) from retainer/fixed resource count.

    Designer/Surfacer memberships on delivery teams are left unchanged so an admin
    can still exclude a named engineer without the next restart flipping them on.
    """
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        teams = {team.id: team for team in session.scalars(select(Team)).all()}
        changed = False
        for member in session.scalars(select(TeamMember)).all():
            team = teams.get(member.team_id)
            user = session.get(User, member.user_id)
            role_name = get_role_name(session, user) if user else ""
            if team is not None and team.name == CORPORATE_TEAM_NAME:
                if bool(getattr(member, "is_billable_headcount", True)):
                    member.is_billable_headcount = False
                    changed = True
                continue
            if role_is_fixed_resource_default(role_name):
                continue
            # Managers, Planning Board, Office Admin, Design Leaders, EM, etc.
            desired = default_is_billable_headcount(team=team, role_name=role_name)
            if bool(getattr(member, "is_billable_headcount", True)) != desired:
                member.is_billable_headcount = desired
                changed = True
        if changed:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
