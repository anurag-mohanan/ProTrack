"""Working model strategy base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import ProjectHealth, ProjectRiskType, WorkingModelCode
from app.models.models import Project, WorkingModel
from app.services.project_calculation_service import ProjectHours


@dataclass(frozen=True)
class WorkingModelContext:
    db: Session
    project: Project
    hours: ProjectHours
    working_model: WorkingModel
    today: date


@dataclass(frozen=True)
class WorkingModelKpiResult:
    working_model_id: UUID
    working_model_code: str
    working_model_name: str
    strategy_key: WorkingModelCode
    show_quoted_variance: bool = True
    show_over_budget_indicators: bool = True
    quoted_hours: Decimal | None = None
    actual_hours: Decimal = Decimal("0")
    remaining_hours: Decimal | None = None
    variance: Decimal | None = None
    variance_percent: Decimal | None = None
    budget_consumption_percent: Decimal | None = None
    model_metrics: dict[str, Decimal | int | str | None] = field(default_factory=dict)


class WorkingModelStrategy(ABC):
    strategy_key: WorkingModelCode

    @abstractmethod
    def calculate_kpis(self, ctx: WorkingModelContext) -> WorkingModelKpiResult:
        raise NotImplementedError

    @abstractmethod
    def evaluate_health_adjustment(
        self, ctx: WorkingModelContext
    ) -> ProjectHealth | None:
        """Return a health override, or None to defer to shared rules."""

    def should_flag_hours_over_quote(self, ctx: WorkingModelContext) -> bool:
        return (
            ctx.hours.quoted > 0 and ctx.hours.actual > ctx.hours.quoted
        )

    def applicable_risk_types(self) -> set[ProjectRiskType]:
        return {
            ProjectRiskType.overdue,
            ProjectRiskType.hours_over_quote,
            ProjectRiskType.milestone_delay,
            ProjectRiskType.missing_approvals,
            ProjectRiskType.designer_overloaded,
        }
