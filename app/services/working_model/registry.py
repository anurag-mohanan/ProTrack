"""Strategy registry for working model KPI calculations."""

from app.models.enums import WorkingModelCode
from app.services.working_model.base import WorkingModelStrategy
from app.services.working_model.strategies.project_based import ProjectBasedStrategy
from app.services.working_model.strategies.retainer import RetainerStrategy
from app.services.working_model.strategies.time_materials import TimeMaterialsStrategy


class WorkingModelStrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[WorkingModelCode, WorkingModelStrategy] = {}

    def register(self, strategy: WorkingModelStrategy) -> None:
        self._strategies[strategy.strategy_key] = strategy

    def get(self, strategy_key: WorkingModelCode) -> WorkingModelStrategy:
        strategy = self._strategies.get(strategy_key)
        if strategy is None:
            raise KeyError(f"No working model strategy registered for '{strategy_key.value}'")
        return strategy

    def available_strategy_keys(self) -> list[WorkingModelCode]:
        return list(self._strategies.keys())


def build_default_registry() -> WorkingModelStrategyRegistry:
    registry = WorkingModelStrategyRegistry()
    registry.register(ProjectBasedStrategy())
    registry.register(TimeMaterialsStrategy())
    registry.register(RetainerStrategy())
    return registry
