"""Phase 90 — parent/child IT asset relationships for hardware workbook import."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
    return row is not None


def ensure_phase90_it_parent_asset_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "assets"):
                return
            if not _sqlite_has_column(engine, "assets", "parent_asset_id"):
                connection.execute(
                    text("ALTER TABLE assets ADD COLUMN parent_asset_id CHAR(36)")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE assets "
                    "ADD COLUMN IF NOT EXISTS parent_asset_id UUID"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_assets_parent_asset_id "
                    "ON assets (parent_asset_id)"
                )
            )
