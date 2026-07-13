"""Finance business-model KPI strategy registry (extends working-model pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.models.enums import WorkingModelCode


class FinanceKpiStrategy(ABC):
    strategy_key: WorkingModelCode

    @abstractmethod
    def calculate(self, context: dict[str, Any]) -> dict[str, Decimal | str]:
        raise NotImplementedError


class ProjectBasedFinanceStrategy(FinanceKpiStrategy):
    strategy_key = WorkingModelCode.project_based

    def calculate(self, context: dict[str, Any]) -> dict[str, Decimal | str]:
        quoted = Decimal(str(context.get("quoted_hours") or 0))
        actual = Decimal(str(context.get("actual_hours") or 0))
        revenue = Decimal(str(context.get("revenue") or 0))
        cost = Decimal(str(context.get("actual_cost") or 0))
        variance = quoted - actual
        margin = revenue - cost
        margin_pct = (margin / revenue * 100) if revenue else Decimal("0")
        return {
            "strategy": self.strategy_key.value,
            "quoted_vs_actual_hours": variance,
            "margin": margin,
            "margin_percent": margin_pct.quantize(Decimal("0.01")),
            "delivery_hours": actual,
            "variance_hours": variance,
        }


class TimeMaterialsFinanceStrategy(FinanceKpiStrategy):
    strategy_key = WorkingModelCode.time_materials

    def calculate(self, context: dict[str, Any]) -> dict[str, Decimal | str]:
        billable = Decimal(str(context.get("billable_hours") or 0))
        revenue = Decimal(str(context.get("revenue") or 0))
        recovery = Decimal(str(context.get("recovery_percent") or 0))
        return {
            "strategy": self.strategy_key.value,
            "billable_hours": billable,
            "revenue": revenue,
            "approval_status": str(context.get("approval_status") or "n/a"),
            "recovery_percent": recovery,
        }


class RetainerFinanceStrategy(FinanceKpiStrategy):
    strategy_key = WorkingModelCode.retainer

    def calculate(self, context: dict[str, Any]) -> dict[str, Decimal | str]:
        reserved = Decimal(str(context.get("reserved_capacity") or 0))
        consumed = Decimal(str(context.get("consumed_capacity") or 0))
        unused = reserved - consumed
        revenue = Decimal(str(context.get("revenue") or 0))
        ehr = (revenue / consumed) if consumed else Decimal("0")
        return {
            "strategy": self.strategy_key.value,
            "reserved_capacity": reserved,
            "consumed_capacity": consumed,
            "unused_capacity": unused,
            "effective_hourly_rate": ehr.quantize(Decimal("0.01")),
            "response_sla": str(context.get("response_sla") or "n/a"),
        }


class FinanceKpiStrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[WorkingModelCode, FinanceKpiStrategy] = {}

    def register(self, strategy: FinanceKpiStrategy) -> None:
        self._strategies[strategy.strategy_key] = strategy

    def get(self, strategy_key: WorkingModelCode) -> FinanceKpiStrategy:
        strategy = self._strategies.get(strategy_key)
        if strategy is None:
            raise KeyError(f"No finance KPI strategy for '{strategy_key.value}'")
        return strategy


def build_finance_kpi_registry() -> FinanceKpiStrategyRegistry:
    registry = FinanceKpiStrategyRegistry()
    registry.register(ProjectBasedFinanceStrategy())
    registry.register(TimeMaterialsFinanceStrategy())
    registry.register(RetainerFinanceStrategy())
    return registry


finance_kpi_registry = build_finance_kpi_registry()
