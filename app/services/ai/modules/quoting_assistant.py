"""AI Quoting Assistant."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.crud.project_metrics import build_project_read
from app.models.models import Project
from app.schemas.ai import QuoteHourBreakdown, QuoteRecommendation
from app.services.ai.base import AiContext, AiModule
from app.services.ai.pattern_recognition import pattern_matcher


class QuotingAssistantModule(AiModule):
    name = "quoting_assistant"

    def run(self, ctx: AiContext, **kwargs: Any) -> QuoteRecommendation:
        project_id = kwargs.get("project_id")
        if project_id is None:
            raise ValueError("project_id is required")

        project = ctx.db.get(Project, UUID(str(project_id)))
        if project is None:
            raise ValueError("Project not found")

        read = build_project_read(ctx.db, project)
        similar = pattern_matcher.find_similar(ctx, project, limit=5)
        breakdown, confidence = pattern_matcher.estimate_hours_breakdown(similar)

        rationale = None
        if similar:
            tools = ", ".join(s.tool_number for s in similar[:3])
            rationale = f"Based on similar completed projects: {tools}"

        return QuoteRecommendation(
            project_id=project.id,
            tool_number=project.tool_number,
            customer_name=read.customer_name,
            project_type_name=read.project_type_name,
            suggested=QuoteHourBreakdown(
                design_hours=breakdown["design"],
                surfacing_hours=breakdown["surfacing"],
                checking_hours=breakdown["checking"],
                bom_hours=breakdown["bom"],
                total_hours=breakdown["total"],
            ),
            confidence_percent=confidence,
            similar_projects=similar,
            rationale=rationale,
        )
