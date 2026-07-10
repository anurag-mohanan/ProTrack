"""Central orchestrator for working-model KPI strategies."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import ProjectHealth, ProjectRiskType
from app.models.models import Project, WorkingModel
from app.services.project_calculation_service import ProjectHours, calculate_hours
from app.services.working_model.base import WorkingModelContext, WorkingModelKpiResult
from app.services.working_model.registry import (
    WorkingModelStrategyRegistry,
    build_default_registry,
)
from app.services.working_model.resolver import resolve_working_model_for_project


class WorkingModelEngine:
    def __init__(
        self,
        db: Session,
        registry: WorkingModelStrategyRegistry | None = None,
    ) -> None:
        self.db = db
        self.registry = registry or build_default_registry()

    def resolve_model(self, project: Project) -> WorkingModel | None:
        return resolve_working_model_for_project(self.db, project=project)

    def build_context(
        self,
        project: Project,
        *,
        hours: ProjectHours | None = None,
        today: date | None = None,
        working_model: WorkingModel | None = None,
    ) -> WorkingModelContext | None:
        model = working_model or self.resolve_model(project)
        if model is None:
            return None
        return WorkingModelContext(
            db=self.db,
            project=project,
            hours=hours or calculate_hours(self.db, project),
            working_model=model,
            today=today or date.today(),
        )

    def calculate_kpis(
        self,
        project: Project,
        *,
        hours: ProjectHours | None = None,
        today: date | None = None,
    ) -> WorkingModelKpiResult | None:
        ctx = self.build_context(project, hours=hours, today=today)
        if ctx is None:
            return None
        strategy = self.registry.get(ctx.working_model.strategy_key)
        return strategy.calculate_kpis(ctx)

    def evaluate_health(
        self,
        project: Project,
        *,
        hours: ProjectHours | None = None,
        today: date | None = None,
    ) -> ProjectHealth | None:
        ctx = self.build_context(project, hours=hours, today=today)
        if ctx is None:
            return None
        strategy = self.registry.get(ctx.working_model.strategy_key)
        return strategy.evaluate_health_adjustment(ctx)

    def should_flag_hours_over_quote(
        self,
        project: Project,
        hours: ProjectHours,
    ) -> bool:
        ctx = self.build_context(project, hours=hours)
        if ctx is None:
            return hours.quoted > 0 and hours.actual > hours.quoted
        strategy = self.registry.get(ctx.working_model.strategy_key)
        return strategy.should_flag_hours_over_quote(ctx)

    def applicable_risk_types(self, project: Project) -> set[ProjectRiskType]:
        ctx = self.build_context(project)
        if ctx is None:
            return set(ProjectRiskType)
        strategy = self.registry.get(ctx.working_model.strategy_key)
        return strategy.applicable_risk_types()
