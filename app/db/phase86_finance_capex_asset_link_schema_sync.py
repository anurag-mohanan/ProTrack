"""Phase 86 — CapEx expense ↔ IT asset link + finance control-center helpers."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase86_finance_capex_asset_link_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "expenses", "asset_id"):
                connection.execute(text("ALTER TABLE expenses ADD COLUMN asset_id CHAR(36)"))
        else:
            connection.execute(
                text(
                    "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS asset_id UUID "
                    "REFERENCES assets(id)"
                )
            )
