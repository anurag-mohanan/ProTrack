"""Phase 50 — Security hardening foundation schema.

Adds authentication-hardening columns to ``users`` (password change tracking,
lockout expiry, JWT ``token_version`` for stateless revocation, plus future-ready
MFA/SSO columns), audit-enrichment columns to ``activities`` (IP, user agent,
outcome, module), and two new tables: ``password_history`` (block password
reuse) and ``login_sessions`` (active-device visibility / remote termination).

All changes are additive and idempotent, following the established phaseNN
pattern. ``Base.metadata.create_all`` handles the new tables on fresh databases;
this module only needs to add columns to existing tables.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _table_exists(engine: Engine, table_name: str) -> bool:
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": table_name},
            ).fetchone()
        return row is not None
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT to_regclass(:n)"), {"n": table_name}
        ).fetchone()
    return bool(row and row[0])


def _add_column_sqlite(connection, table: str, column: str, ddl: str, engine: Engine) -> None:
    if _table_exists(engine, table) and not _sqlite_has_column(engine, table, column):
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


# (column_name, sqlite_ddl, postgres_ddl)
_USER_COLUMNS = [
    ("password_changed_at", "DATETIME NULL", "TIMESTAMP NULL"),
    ("locked_until", "DATETIME NULL", "TIMESTAMP NULL"),
    ("token_version", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ("mfa_enabled", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("mfa_secret", "TEXT NULL", "TEXT NULL"),
    ("mfa_method", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
    ("sso_subject", "VARCHAR(255) NULL", "VARCHAR(255) NULL"),
]

_ACTIVITY_COLUMNS = [
    ("ip_address", "VARCHAR(45) NULL", "VARCHAR(45) NULL"),
    ("user_agent", "VARCHAR(255) NULL", "VARCHAR(255) NULL"),
    ("outcome", "VARCHAR(16) NULL", "VARCHAR(16) NULL"),
    ("module", "VARCHAR(50) NULL", "VARCHAR(50) NULL"),
]


def ensure_phase50_security_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for column, ddl, _pg in _USER_COLUMNS:
                _add_column_sqlite(connection, "users", column, ddl, engine)
            for column, ddl, _pg in _ACTIVITY_COLUMNS:
                _add_column_sqlite(connection, "activities", column, ddl, engine)
        else:
            for column, _sq, pg in _USER_COLUMNS:
                connection.execute(
                    text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {pg}")
                )
            for column, _sq, pg in _ACTIVITY_COLUMNS:
                connection.execute(
                    text(f"ALTER TABLE activities ADD COLUMN IF NOT EXISTS {column} {pg}")
                )


def ensure_phase50_security_tables(engine: Engine) -> None:
    """Create the new security tables if they don't already exist.

    Relies on the ORM metadata so column types stay consistent across dialects.
    """
    from app.models.models import LoginSession, PasswordHistory

    for model in (PasswordHistory, LoginSession):
        model.__table__.create(bind=engine, checkfirst=True)


def ensure_phase50_security_foundation(engine: Engine) -> None:
    ensure_phase50_security_columns(engine)
    ensure_phase50_security_tables(engine)
