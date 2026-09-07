"""Phase 93 — Computer network interfaces (multi-NIC) + IP history interface_id."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import ComputerNetworkInterface


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


def ensure_phase93_it_computer_nics_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[ComputerNetworkInterface.__table__],
    )
    _add_column(engine, "ip_assignment_history", "interface_id", "CHAR(36)")
