"""Map working-model strategy to team commercial billing mode + fee rules."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TeamBillingMode, TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import WorkingModel


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


def team_has_active_retainer_terms(db: Session, team_id: UUID) -> bool:
    """True when the team has active retainer / subscription commercial terms.

    Retainer teams charge full monthly salary into team operating cost (seat cost),
    not calendar-day prorated CTC — customer fee may still day-prorate separately.
    """
    rows = db.execute(
        select(WorkingModel.strategy_key)
        .join(TeamCommercialTerms, TeamCommercialTerms.working_model_id == WorkingModel.id)
        .where(
            TeamCommercialTerms.team_id == team_id,
            TeamCommercialTerms.is_active.is_(True),
        )
    ).all()
    for (strategy,) in rows:
        if uses_flat_customer_fee(strategy):
            return True
    return False
