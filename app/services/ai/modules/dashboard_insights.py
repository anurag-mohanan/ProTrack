"""Dashboard insights module — dynamic AI Operations Assistant."""

from __future__ import annotations

from typing import Any

from app.schemas.ai import AiInsight
from app.services.ai.base import AiContext, AiModule, confidence_from_sample_size
from app.services.ai.context import (
    get_active_projects,
    get_open_engineering_changes,
    get_stale_milestones,
)
from app.services.ai.pattern_recognition import pattern_matcher
from app.services.ai.recommendations import recommender
from app.services.ai.risk_analysis import risk_analyzer


class DashboardInsightsModule(AiModule):
    name = "dashboard_insights"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[AiInsight]:
        limit = int(kwargs.get("limit", 10))
        insights: list[AiInsight] = []

        insights.extend(risk_analyzer.build_insights(ctx))
        insights.extend(recommender.resource_insights(ctx))

        stale = get_stale_milestones(ctx, days=7)
        if stale:
            insights.append(
                AiInsight(
                    id="stale-milestones",
                    module=self.name,
                    category="planning",
                    severity="warning",
                    title=f"{stale} milestone{'s' if stale != 1 else ''} not updated in 7 days",
                    detail="Review milestone progress and update statuses.",
                    href="/projects",
                    confidence=86,
                )
            )

        open_ecs = get_open_engineering_changes(ctx)
        if open_ecs:
            insights.append(
                AiInsight(
                    id="open-engineering-changes",
                    module=self.name,
                    category="planning",
                    severity="info",
                    title=f"{open_ecs} open engineering change{'s' if open_ecs != 1 else ''}",
                    detail="Projects require Design Leader review for open ECs.",
                    href="/projects",
                    confidence=90,
                )
            )

        # Quoting insight for newest unquoted active project
        active = sorted(
            get_active_projects(ctx),
            key=lambda p: p.created_at or ctx.today,
            reverse=True,
        )
        quote_candidate = next(
            (p for p in active if float(p.quoted_hours or 0) <= 0),
            None,
        )
        if quote_candidate:
            similar = pattern_matcher.find_similar(ctx, quote_candidate, limit=3)
            if similar:
                avg = sum(s.actual_hours for s in similar) / len(similar)
                low = max(1, round(avg * 0.95))
                high = max(low + 5, round(avg * 1.08))
                insights.append(
                    AiInsight(
                        id=f"quote-{quote_candidate.id}",
                        module=self.name,
                        category="quoting",
                        severity="info",
                        title=f"Tool {quote_candidate.tool_number} is similar to {similar[0].tool_number}",
                        detail=(
                            f"Historical average was {round(avg)} hours. "
                            f"Recommended quote: {low}–{high} hours."
                        ),
                        href=f"/projects/{quote_candidate.id}",
                        confidence=confidence_from_sample_size(len(similar)),
                        entity_type="project",
                        entity_id=quote_candidate.id,
                        metadata={"similar_tools": [s.tool_number for s in similar]},
                    )
                )

        # Deduplicate by id, sort by severity
        severity_order = {"error": 0, "warning": 1, "info": 2}
        seen: set[str] = set()
        unique: list[AiInsight] = []
        for insight in sorted(insights, key=lambda i: severity_order.get(i.severity, 3)):
            if insight.id in seen:
                continue
            seen.add(insight.id)
            unique.append(insight)

        return unique[:limit]
