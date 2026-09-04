"""Phase 85 — Finance treasury: loans, OD, investments, cash position."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.finance import (  # noqa: F401 — register metadata
    FinanceCashPosition,
    FinanceInvestment,
    FinanceInvestmentIncome,
    FinanceLoan,
    FinanceLoanRepayment,
    FinanceOdInterestCharge,
    FinanceOverdraftFacility,
)


def ensure_phase85_finance_treasury_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            FinanceLoan.__table__,
            FinanceLoanRepayment.__table__,
            FinanceOverdraftFacility.__table__,
            FinanceOdInterestCharge.__table__,
            FinanceInvestment.__table__,
            FinanceInvestmentIncome.__table__,
            FinanceCashPosition.__table__,
        ],
    )
