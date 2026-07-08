"""AI Engine — central orchestrator for all AI modules."""

from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.ai import AiOperationsSummary
from app.services.ai.base import AiContext, AiModule
from app.services.ai.cache import ai_cache


class AiEngine:
    """Registry and runner for pluggable AI modules."""

    def __init__(self) -> None:
        self._modules: dict[str, AiModule] = {}

    def register(self, module: AiModule) -> None:
        self._modules[module.name] = module

    def run(
        self,
        module_name: str,
        db: Session,
        *,
        use_cache: bool = True,
        cache_ttl: int = 300,
        actor_id: UUID | None = None,
        actor_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        module = self._modules.get(module_name)
        if module is None:
            raise KeyError(f"AI module '{module_name}' is not registered")

        cache_params = {
            "module": module_name,
            "actor_id": str(actor_id) if actor_id else None,
            **{k: str(v) if isinstance(v, UUID) else v for k, v in kwargs.items()},
        }
        if use_cache:
            cached = ai_cache.get("ai_engine", cache_params)
            if cached is not None:
                return cached

        ctx = AiContext(db=db, actor_id=actor_id, actor_name=actor_name)
        result = module.run(ctx, **kwargs)

        if use_cache:
            ai_cache.set("ai_engine", cache_params, result, ttl_seconds=cache_ttl)
        return result

    def run_operations_summary(
        self,
        db: Session,
        *,
        actor_name: str | None = None,
    ) -> AiOperationsSummary:
        insights = self.run("dashboard_insights", db, actor_name=actor_name, limit=10)
        brief = self.run("morning_brief", db, actor_name=actor_name)
        return AiOperationsSummary(insights=insights, morning_brief=brief)


def _register_defaults(engine: AiEngine) -> None:
    from app.services.ai.modules.chat_assistant import ChatAssistantModule
    from app.services.ai.modules.customer_analytics import CustomerAnalyticsModule
    from app.services.ai.modules.dashboard_insights import DashboardInsightsModule
    from app.services.ai.modules.engineering_kpi import EngineeringKpiModule
    from app.services.ai.modules.executive_wall import ExecutiveWallModule
    from app.services.ai.modules.knowledge_base import KnowledgeBaseModule
    from app.services.ai.modules.morning_brief import MorningBriefModule
    from app.services.ai.modules.notification_engine import NotificationEngineModule
    from app.services.ai.modules.productivity_analytics import ProductivityAnalyticsModule
    from app.services.ai.modules.project_health_engine import ProjectHealthEngineModule
    from app.services.ai.modules.quoting_assistant import QuotingAssistantModule
    from app.services.ai.modules.resource_optimizer import ResourceOptimizerModule
    from app.services.ai.modules.schedule_predictor import SchedulePredictorModule
    from app.services.ai.modules.timesheet_suggestions import TimesheetSuggestionsModule

    for mod in (
        DashboardInsightsModule(),
        MorningBriefModule(),
        QuotingAssistantModule(),
        ResourceOptimizerModule(),
        ProjectHealthEngineModule(),
        SchedulePredictorModule(),
        CustomerAnalyticsModule(),
        KnowledgeBaseModule(),
        ProductivityAnalyticsModule(),
        EngineeringKpiModule(),
        NotificationEngineModule(),
        TimesheetSuggestionsModule(),
        ChatAssistantModule(),
        ExecutiveWallModule(),
    ):
        engine.register(mod)


ai_engine = AiEngine()
_register_defaults(ai_engine)
