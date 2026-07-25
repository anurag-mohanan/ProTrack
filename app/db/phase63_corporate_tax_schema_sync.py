"""Phase 63 — company corporate tax % for Overview / Team P&L after-tax net."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.finance import CompanyFinanceSettings


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase63_corporate_tax_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "company_finance_settings", "corporate_tax_percent"):
                connection.execute(
                    text(
                        "ALTER TABLE company_finance_settings "
                        "ADD COLUMN corporate_tax_percent NUMERIC(8, 2) NOT NULL DEFAULT 30"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE company_finance_settings "
                    "ADD COLUMN IF NOT EXISTS corporate_tax_percent "
                    "NUMERIC(8, 2) NOT NULL DEFAULT 30"
                )
            )

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        rows = session.scalars(select(CompanyFinanceSettings)).all()
        for row in rows:
            if getattr(row, "corporate_tax_percent", None) is None:
                row.corporate_tax_percent = Decimal("30")
        if not rows:
            session.add(
                CompanyFinanceSettings(
                    base_currency="INR",
                    display_name="Company Default",
                    corporate_tax_percent=Decimal("30"),
                    is_active=True,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
