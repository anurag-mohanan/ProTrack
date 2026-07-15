"""Phase 22 — Finance Rebuild 1: paid_by / renewals on expenses + team commercial terms."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.finance import TeamCommercialTerms  # noqa: F401 — register metadata

_EXPENSE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("paid_by", "VARCHAR(20) DEFAULT 'prosohm'"),
    ("vendor_name", "VARCHAR(200)"),
    ("next_renewal_date", "DATE"),
    ("notify_before_days", "INTEGER DEFAULT 7"),
    ("notify_enabled", "BOOLEAN DEFAULT 1"),
    ("renewal_notified_for", "DATE"),
)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase22_finance_rebuild_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[TeamCommercialTerms.__table__],
    )

    dialect = engine.dialect.name
    if dialect == "sqlite":
        for column_name, ddl in _EXPENSE_COLUMNS:
            if not _sqlite_has_column(engine, "expenses", column_name):
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE expenses ADD COLUMN {column_name} {ddl}"))
        return

    with engine.begin() as connection:
        for column_name, ddl in _EXPENSE_COLUMNS:
            connection.execute(
                text(f"ALTER TABLE expenses ADD COLUMN IF NOT EXISTS {column_name} {ddl}")
            )
