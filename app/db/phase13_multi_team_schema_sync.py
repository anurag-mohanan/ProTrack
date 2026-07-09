"""Phase 13 — multi-team user assignments (extends team_members)."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import TeamRelationshipType
from app.models.models import TeamMember, User


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    if not _sqlite_has_column(engine, table, column):
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def _pg_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        )


def ensure_multi_team_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    columns = [
        ("relationship_type", "VARCHAR(50) NOT NULL DEFAULT 'member'"),
        ("is_primary", "BOOLEAN NOT NULL DEFAULT 0"),
    ]
    if dialect == "sqlite":
        for column, definition in columns:
            _sqlite_add_column(engine, "team_members", column, definition)
    elif dialect == "postgresql":
        for column, definition in columns:
            _pg_add_column(engine, "team_members", column, definition)


def _infer_relationship_type(role_within_team: str | None) -> TeamRelationshipType:
    if not role_within_team:
        return TeamRelationshipType.member
    normalized = role_within_team.strip().lower()
    if "engineering manager" in normalized or normalized == "manager":
        return TeamRelationshipType.engineering_manager
    if "leader" in normalized or "lead" in normalized:
        return TeamRelationshipType.team_leader
    if "reviewer" in normalized:
        return TeamRelationshipType.reviewer
    return TeamRelationshipType.member


def _backfill_team_memberships(session: Session) -> None:
    members = session.scalars(select(TeamMember)).all()
    for member in members:
        member.relationship_type = _infer_relationship_type(member.role_within_team)
        if member.role_within_team is None:
            member.role_within_team = member.relationship_type.value.replace("_", " ").title()
    session.flush()

    users = session.scalars(select(User).where(User.team_id.is_not(None))).all()
    for user in users:
        existing = session.scalar(
            select(TeamMember).where(
                TeamMember.user_id == user.id,
                TeamMember.team_id == user.team_id,
            )
        )
        if existing is None:
            session.add(
                TeamMember(
                    team_id=user.team_id,
                    user_id=user.id,
                    relationship_type=TeamRelationshipType.member,
                    is_primary=True,
                    role_within_team="Member",
                )
            )
            continue
        if not existing.is_primary:
            existing.is_primary = True

    for user in users:
        primary = session.scalar(
            select(TeamMember).where(
                TeamMember.user_id == user.id,
                TeamMember.is_primary.is_(True),
            )
        )
        if primary is not None:
            user.team_id = primary.team_id
        session.add(user)
    session.commit()


def ensure_phase13_multi_team_foundation(engine: Engine) -> None:
    ensure_multi_team_columns(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        _backfill_team_memberships(session)
    finally:
        session.close()
