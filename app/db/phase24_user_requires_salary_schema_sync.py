"""Phase 24 — users.requires_salary for Finance People costs eligibility."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.permissions import ADMIN, PLANNING_BOARD, normalize_role_name


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _backfill_requires_salary(engine: Engine) -> None:
    """One-time seed: Admin / Planning Board → salary not required."""
    with engine.begin() as connection:
        roles = connection.execute(text("SELECT id, name FROM roles")).fetchall()
        exempt_ids = [
            row[0]
            for row in roles
            if normalize_role_name(row[1] or "") in {ADMIN, PLANNING_BOARD}
        ]
        if not exempt_ids:
            return
        placeholders = ", ".join(f":r{i}" for i in range(len(exempt_ids)))
        params = {f"r{i}": rid for i, rid in enumerate(exempt_ids)}
        connection.execute(
            text(
                f"UPDATE users SET requires_salary = 0 "
                f"WHERE role_id IN ({placeholders})"
            ),
            params,
        )


def ensure_phase24_user_requires_salary_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    column_added = False
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "users", "requires_salary"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN requires_salary "
                        "BOOLEAN NOT NULL DEFAULT 1"
                    )
                )
            column_added = True
    else:
        with engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'requires_salary'
                    """
                )
            ).fetchone()
            if result is None:
                connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN requires_salary "
                        "BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
                column_added = True
    if column_added:
        _backfill_requires_salary(engine)
