"""Phase 91 — Finance expense ↔ IT software license entitlement bridge."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import SoftwareLicensePool, SoftwareLicenseRenewal


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
            if not _sqlite_has_table(engine, table):
                return
            if not _sqlite_has_column(engine, table, name):
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        else:
            pg_ddl = ddl.replace("CHAR(36)", "UUID")
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_ddl}")
            )


def ensure_phase91_finance_software_bridge_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            SoftwareLicensePool.__table__,
            SoftwareLicenseRenewal.__table__,
        ],
    )

    pool_cols = [
        ("entitlement_code", "VARCHAR(60)"),
        ("commercial_model", "VARCHAR(20)"),
        ("assignment_model", "VARCHAR(40)"),
        ("status", "VARCHAR(20) DEFAULT 'active'"),
        ("purchase_date", "DATE"),
        ("subscription_start_date", "DATE"),
        ("renewal_frequency", "VARCHAR(40)"),
        ("renewal_amount", "NUMERIC(12, 2)"),
        ("auto_renew", "BOOLEAN DEFAULT 0"),
        ("renewal_notice_days", "INTEGER DEFAULT 30"),
        ("amc_required", "BOOLEAN"),
        ("amc_percent", "NUMERIC(7, 2)"),
        ("amc_amount", "NUMERIC(12, 2)"),
        ("amc_amount_overridden", "BOOLEAN DEFAULT 0"),
        ("amc_start_date", "DATE"),
        ("amc_due_date", "DATE"),
        ("amc_vendor", "VARCHAR(200)"),
        ("terminated_at", "DATE"),
        ("termination_reason", "VARCHAR(200)"),
        ("terminated_by_user_id", "CHAR(36)"),
        ("expense_id", "CHAR(36)"),
    ]
    for col, ddl in pool_cols:
        _add_column(engine, "software_license_pools", col, ddl)

    for col, ddl in [
        ("software_id", "CHAR(36)"),
        ("license_pool_id", "CHAR(36)"),
    ]:
        _add_column(engine, "expenses", col, ddl)

    # Backfill status for legacy pools.
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if _sqlite_has_column(engine, "software_license_pools", "status"):
                connection.execute(
                    text(
                        "UPDATE software_license_pools SET status = 'active' "
                        "WHERE status IS NULL OR TRIM(status) = ''"
                    )
                )
        else:
            connection.execute(
                text(
                    "UPDATE software_license_pools SET status = 'active' "
                    "WHERE status IS NULL OR BTRIM(status) = ''"
                )
            )
