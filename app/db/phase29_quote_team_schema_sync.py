"""Phase 29 — quotes.team_id for awarded quote import (team-scoped)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase29_quote_team_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quotes", "team_id"):
                connection.execute(
                    text("ALTER TABLE quotes ADD COLUMN team_id CHAR(36)")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS team_id UUID "
                    "REFERENCES teams(id)"
                )
            )
