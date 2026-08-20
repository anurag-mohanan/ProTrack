"""Phase 83 — Sequential IT Data Import batches + durable lineage columns."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import ITImportBatch, ITMigrationException


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


def ensure_phase83_it_data_import_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[ITImportBatch.__table__, ITMigrationException.__table__],
    )

    lineage = [
        ("import_batch_id", "CHAR(36)"),
        ("source_system", "VARCHAR(120)"),
        ("source_record_id", "VARCHAR(80)"),
        ("source_row", "INTEGER"),
    ]
    for col, ddl in lineage:
        _add_column(engine, "assets", col, ddl)

    for table, cols in [
        ("computers", [("import_batch_id", "CHAR(36)"), ("source_system", "VARCHAR(120)")]),
        (
            "inventory_items",
            [
                ("import_batch_id", "CHAR(36)"),
                ("source_system", "VARCHAR(120)"),
                ("source_record_id", "VARCHAR(80)"),
            ],
        ),
        ("it_suppliers", [("import_batch_id", "CHAR(36)"), ("source_system", "VARCHAR(120)")]),
        ("it_user_accounts", [("import_batch_id", "CHAR(36)"), ("source_system", "VARCHAR(120)")]),
        (
            "software_license_pools",
            [("import_batch_id", "CHAR(36)"), ("source_system", "VARCHAR(120)")],
        ),
        ("software_assignments", [("import_batch_id", "CHAR(36)")]),
        ("ip_addresses", [("import_batch_id", "CHAR(36)")]),
    ]:
        for col, ddl in cols:
            _add_column(engine, table, col, ddl)
