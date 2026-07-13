"""Phase 18 — Finance Annual Plan tables (Apr–Mar workbook reference)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.finance import FinancePlan, FinancePlanLine  # noqa: F401 — register metadata


def ensure_phase18_finance_annual_plan_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            FinancePlan.__table__,
            FinancePlanLine.__table__,
        ],
    )
