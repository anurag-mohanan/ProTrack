"""Map working-model strategy to team commercial billing mode + fee rules."""

from __future__ import annotations

from app.models.enums import TeamBillingMode, TeamBillingPeriod, WorkingModelCode


def billing_mode_for_strategy(strategy: WorkingModelCode | str | None) -> TeamBillingMode:
    key = strategy.value if isinstance(strategy, WorkingModelCode) else str(strategy or "")
    if key == WorkingModelCode.retainer.value:
        return TeamBillingMode.subscription
    if key == WorkingModelCode.time_materials.value:
        return TeamBillingMode.time_materials
    if key == WorkingModelCode.overheads.value:
        return TeamBillingMode.fixed_price
    return TeamBillingMode.project_based


def uses_flat_customer_fee(strategy: WorkingModelCode | str | None) -> bool:
    """Retainer stores rate-per-resource; others do not prompt for a team customer fee."""
    key = strategy.value if isinstance(strategy, WorkingModelCode) else str(strategy or "")
    return key == WorkingModelCode.retainer.value


def default_period_for_strategy(strategy: WorkingModelCode | str | None) -> TeamBillingPeriod:
    key = strategy.value if isinstance(strategy, WorkingModelCode) else str(strategy or "")
    if key == WorkingModelCode.project_based.value:
        return TeamBillingPeriod.one_time
    return TeamBillingPeriod.monthly
