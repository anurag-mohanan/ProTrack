"""Phase 36 — Team membership periods + effective_from for dated transfers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import TeamMember, TeamMembershipPeriod, User


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchall()
    return bool(rows)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _default_period_start(member: TeamMember, user: User | None) -> date:
    if member.effective_from is not None:
        return member.effective_from
    if user is not None and user.joining_date is not None:
        return user.joining_date
    joined = getattr(member, "joined_at", None)
    if joined is not None:
        return joined.date()
    return date(2020, 4, 1)


def backfill_membership_periods(session: Session) -> None:
    """Seed one open primary period per current primary membership."""
    primaries = session.scalars(
        select(TeamMember).where(TeamMember.is_primary.is_(True))
    ).all()
    for member in primaries:
        existing = session.scalar(
            select(TeamMembershipPeriod.id)
            .where(
                TeamMembershipPeriod.user_id == member.user_id,
                TeamMembershipPeriod.team_id == member.team_id,
                TeamMembershipPeriod.is_primary.is_(True),
                TeamMembershipPeriod.effective_to.is_(None),
            )
            .limit(1)
        )
        if existing is not None:
            continue
        user = session.get(User, member.user_id)
        start = _default_period_start(member, user)
        session.add(
            TeamMembershipPeriod(
                user_id=member.user_id,
                team_id=member.team_id,
                is_primary=True,
                is_billable_headcount=bool(getattr(member, "is_billable_headcount", True)),
                effective_from=start,
                effective_to=None,
                role_within_team=member.role_within_team,
                relationship_type=member.relationship_type,
                notes="Backfilled from live primary membership",
            )
        )
        if member.effective_from is None:
            member.effective_from = start

    # Align open periods that still start at hire date after a dated move.
    reconcile_open_periods_to_member_effective_from(session)


def reconcile_open_periods_to_member_effective_from(session: Session) -> int:
    """Raise open period starts to match TeamMember.effective_from when later.

    Returns the number of periods adjusted.
    """
    adjusted = 0
    members = session.scalars(
        select(TeamMember).where(TeamMember.effective_from.is_not(None))
    ).all()
    for member in members:
        assert member.effective_from is not None
        open_periods = session.scalars(
            select(TeamMembershipPeriod).where(
                TeamMembershipPeriod.user_id == member.user_id,
                TeamMembershipPeriod.team_id == member.team_id,
                TeamMembershipPeriod.effective_to.is_(None),
            )
        ).all()
        for period in open_periods:
            if period.effective_from < member.effective_from:
                period.effective_from = member.effective_from
                adjusted += 1
    return adjusted


def ensure_phase36_team_membership_periods_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_table(engine, "team_membership_periods"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE team_membership_periods (
                            id CHAR(32) NOT NULL PRIMARY KEY,
                            user_id CHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            team_id CHAR(32) NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                            is_primary BOOLEAN NOT NULL DEFAULT 1,
                            is_billable_headcount BOOLEAN NOT NULL DEFAULT 1,
                            effective_from DATE NOT NULL,
                            effective_to DATE,
                            role_within_team VARCHAR(100),
                            relationship_type VARCHAR(50) NOT NULL DEFAULT 'member',
                            notes VARCHAR(255),
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
        if not _sqlite_has_column(engine, "team_members", "effective_from"):
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE team_members ADD COLUMN effective_from DATE")
                )
    else:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS team_membership_periods (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                        is_primary BOOLEAN NOT NULL DEFAULT TRUE,
                        is_billable_headcount BOOLEAN NOT NULL DEFAULT TRUE,
                        effective_from DATE NOT NULL,
                        effective_to DATE,
                        role_within_team VARCHAR(100),
                        relationship_type VARCHAR(50) NOT NULL DEFAULT 'member',
                        notes VARCHAR(255),
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE team_members "
                    "ADD COLUMN IF NOT EXISTS effective_from DATE"
                )
            )

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        backfill_membership_periods(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
