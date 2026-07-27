"""Phase 64 — persisted finance planning scenarios (what-if worksheets)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.finance import FinancePlanningScenario  # noqa: F401 — register metadata


def ensure_phase64_finance_planning_scenarios_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[FinancePlanningScenario.__table__],
    )
