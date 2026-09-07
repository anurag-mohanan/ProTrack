"""Phase 87 — IT software catalog / license / assignment / requirement columns."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import (
    EmployeeSoftwareRequirement,
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
            if not _sqlite_has_table(engine, table):
                return
            if not _sqlite_has_column(engine, table, name):
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        else:
            pg_ddl = ddl.replace("CHAR(36)", "UUID")
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_ddl}")
            )


def ensure_phase87_it_software_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            SoftwareCatalog.__table__,
            SoftwareLicensePool.__table__,
            SoftwareAssignment.__table__,
            EmployeeSoftwareRequirement.__table__,
        ],
    )

    for col, ddl in [
        ("version", "VARCHAR(80)"),
        ("edition", "VARCHAR(80)"),
        ("category", "VARCHAR(80)"),
        ("code", "VARCHAR(40)"),
    ]:
        _add_column(engine, "software_catalog", col, ddl)

    for col, ddl in [
        ("license_type", "VARCHAR(40)"),
        ("cost", "NUMERIC(12, 2)"),
        ("currency_code", "VARCHAR(3)"),
    ]:
        _add_column(engine, "software_license_pools", col, ddl)

    for col, ddl in [
        ("computer_id", "CHAR(36)"),
        ("asset_id", "CHAR(36)"),
        ("released_date", "DATE"),
    ]:
        _add_column(engine, "software_assignments", col, ddl)
