"""Resource optimizer module."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.schemas.ai import ResourceOptimizationResult
from app.services.ai.base import AiContext, AiModule
from app.services.ai.recommendations import recommender


class ResourceOptimizerModule(AiModule):
    name = "resource_optimizer"

    def run(self, ctx: AiContext, **kwargs: Any) -> ResourceOptimizationResult:
        project_id = kwargs.get("project_id")
        pid = UUID(str(project_id)) if project_id else None
        return recommender.optimize_resources(ctx, project_id=pid)
