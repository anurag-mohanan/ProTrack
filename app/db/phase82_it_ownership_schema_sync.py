"""Phase 82 — IT ownership, customer returns, inventory, nav preferences."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import (
    AssetCustomerReturn,
    InventoryItem,
    ITSupplier,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)


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


def _add_column(engine: Engine, table: str, name: str, ddl: str) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, table, name):
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        else:
            pg_ddl = ddl.replace("BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE")
            pg_ddl = pg_ddl.replace("BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE")
            pg_ddl = pg_ddl.replace("CHAR(36)", "UUID")
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_ddl}")
            )


def ensure_phase82_it_ownership_foundation(engine: Engine) -> None:
    # Preferences: per-user sidebar section collapse state
    _add_column(engine, "user_preferences", "sidebar_section_state", "TEXT")

    # Suppliers + returns + inventory tables
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ITSupplier.__table__,
            AssetCustomerReturn.__table__,
            InventoryItem.__table__,
            SoftwareCatalog.__table__,
            SoftwareLicensePool.__table__,
            SoftwareAssignment.__table__,
        ],
    )

    # Asset ownership / lifecycle columns
    asset_columns = [
        ("legacy_asset_number", "VARCHAR(40)"),
        ("description", "VARCHAR(255)"),
        ("service_tag", "VARCHAR(100)"),
        ("purchased_by", "VARCHAR(40) NOT NULL DEFAULT 'organization'"),
        ("owner_customer_id", "CHAR(36)"),
        ("customer_used_for_id", "CHAR(36)"),
        ("supplier_id", "CHAR(36)"),
        ("invoice_number", "VARCHAR(80)"),
        ("condition", "VARCHAR(40)"),
    ]
    # Only alter if assets table exists (phase81)
    dialect = engine.dialect.name
    exists = True
    if dialect == "sqlite":
        exists = _sqlite_has_table(engine, "assets")
    if exists:
        for name, ddl in asset_columns:
            _add_column(engine, "assets", name, ddl)

    _add_column(
        engine,
        "it_user_accounts",
        "credential_status",
        "VARCHAR(40) NOT NULL DEFAULT 'active'",
    )
