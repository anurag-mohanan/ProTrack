"""Phase 23 — Finance team scope: who-pays flags, overhead home team, expense team backfill."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.finance import Expense, TeamCommercialTerms  # noqa: F401
from app.models.models import Team

# Canonical single overhead home (Phase L merge).
CORPORATE_TEAM_NAME = "Corporate / Management"
LEGACY_CORPORATE_TEAM_NAMES = frozenset(
    {
        "Corporate / Management",
        "Corporate / Shared Services",
        "Corporate",
    }
)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_corporate_shared_services_team(session: Session) -> Team:
    """Ensure the single Corporate / Management overhead home exists (renames legacy)."""
    team = session.scalar(select(Team).where(Team.name == CORPORATE_TEAM_NAME))
    if team is None:
        for legacy_name in ("Corporate / Shared Services", "Corporate"):
            legacy = session.scalar(select(Team).where(Team.name == legacy_name))
            if legacy is not None:
                legacy.name = CORPORATE_TEAM_NAME
                legacy.is_active = True
                legacy.description = (
                    "Corporate & management overhead home — leadership salaries and "
                    "shared HQ OpEx (not customer billable headcount)."
                )
                session.flush()
                return legacy
        team = Team(
            name=CORPORATE_TEAM_NAME,
            description=(
                "Corporate & management overhead home — leadership salaries and "
                "shared HQ OpEx (not customer billable headcount)."
            ),
            is_active=True,
        )
        session.add(team)
        session.flush()
        return team
    if not team.is_active:
        team.is_active = True
        session.flush()
    return team


def ensure_phase23_finance_team_scope_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        for column_name, ddl in (
            ("customer_pays_software", "BOOLEAN DEFAULT 0"),
            ("customer_pays_hardware", "BOOLEAN DEFAULT 0"),
        ):
            if not _sqlite_has_column(engine, "team_commercial_terms", column_name):
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE team_commercial_terms ADD COLUMN {column_name} {ddl}")
                    )
    else:
        with engine.begin() as connection:
            for column_name, ddl in (
                ("customer_pays_software", "BOOLEAN DEFAULT 0"),
                ("customer_pays_hardware", "BOOLEAN DEFAULT 0"),
            ):
                connection.execute(
                    text(
                        "ALTER TABLE team_commercial_terms "
                        f"ADD COLUMN IF NOT EXISTS {column_name} {ddl}"
                    )
                )

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        corporate = ensure_corporate_shared_services_team(session)
        orphans = session.scalars(select(Expense).where(Expense.team_id.is_(None))).all()
        for expense in orphans:
            expense.team_id = corporate.id
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
