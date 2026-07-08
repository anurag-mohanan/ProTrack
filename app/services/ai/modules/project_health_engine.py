"""Automatic project health engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.models import Project
from app.schemas.ai import ProjectHealthAnalysis
from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import get_active_projects
from app.services.ai.scoring import scorer
from app.services.project_calculation_service import recalculate_project


class ProjectHealthEngineModule(AiModule):
    name = "project_health_engine"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[ProjectHealthAnalysis] | ProjectHealthAnalysis:
        project_id = kwargs.get("project_id")
        persist = bool(kwargs.get("persist", False))

        if project_id:
            project = ctx.db.get(Project, UUID(str(project_id)))
            if project is None:
                raise ValueError("Project not found")
            if persist:
                recalculate_project(ctx.db, project.id)
                ctx.db.refresh(project)
            return scorer.project_health_score(ctx, project)

        return [scorer.project_health_score(ctx, p) for p in get_active_projects(ctx)[:50]]
