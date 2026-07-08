"""Predictive schedule analysis."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.models import Project
from app.schemas.ai import SchedulePrediction
from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import get_active_projects
from app.services.ai.forecasting import forecaster


class SchedulePredictorModule(AiModule):
    name = "schedule_predictor"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[SchedulePrediction] | SchedulePrediction:
        project_id = kwargs.get("project_id")
        if project_id:
            project = ctx.db.get(Project, UUID(str(project_id)))
            if project is None:
                raise ValueError("Project not found")
            return forecaster.predict_completion(ctx, project)

        return [
            forecaster.predict_completion(ctx, p)
            for p in get_active_projects(ctx)[:30]
        ]
