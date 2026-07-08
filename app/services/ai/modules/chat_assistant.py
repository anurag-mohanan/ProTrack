"""Conversational AI assistant — query router over ProTrack data."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.ai import AiInsight, ChatResponse
from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import get_active_projects, get_customer_workload_share, get_designer_utilization
from app.services.ai.modules.customer_analytics import CustomerAnalyticsModule
from app.services.ai.modules.dashboard_insights import DashboardInsightsModule
from app.services.ai.modules.quoting_assistant import QuotingAssistantModule
from app.services.ai.modules.resource_optimizer import ResourceOptimizerModule
from app.services.ai.risk_analysis import risk_analyzer


class ChatAssistantModule(AiModule):
    name = "chat_assistant"

    def run(self, ctx: AiContext, **kwargs: Any) -> ChatResponse:
        question = (kwargs.get("question") or "").strip()
        if not question:
            return ChatResponse(
                answer="Ask me about projects, workload, customers, quotes, or resource availability.",
            )

        q = question.lower()
        insights: list[AiInsight] = []

        if re.search(r"due this week|due soon|deliver", q):
            due = risk_analyzer.projects_due_soon(ctx)
            tools = ", ".join(p.tool_number for p in due[:8]) or "none"
            return ChatResponse(
                answer=f"{len(due)} project(s) due this week: {tools}.",
                insights=DashboardInsightsModule().run(ctx, limit=3),
                data={"count": len(due), "tools": [p.tool_number for p in due]},
            )

        if re.search(r"available|capacity|who can|assign", q):
            util = get_designer_utilization(ctx)
            available = [r for r in util if r["utilization"] < 75]
            names = ", ".join(
                f"{r['user'].first_name} ({r['available_hours']:.0f}h free)"
                for r in available[:5]
            ) or "No engineers with significant free capacity"
            return ChatResponse(
                answer=f"Available engineers: {names}.",
                data={"available": len(available)},
            )

        if re.search(r"customer|workload|capacity.*month|hours.*month", q):
            workload = get_customer_workload_share(ctx)
            if workload:
                top = workload[0]
                return ChatResponse(
                    answer=(
                        f"{top['customer_name']} consumed the most engineering hours this month "
                        f"({top['share_percent']}% of total, {top['hours']:.0f}h)."
                    ),
                    data={"workload": workload[:5]},
                )
            return ChatResponse(answer="No customer workload data for this month.")

        if re.search(r"estimate|quote|similar", q):
            tool_match = re.search(r"tool\s*(\d+)", q, re.I)
            if tool_match:
                tool_num = tool_match.group(1)
                project = next(
                    (p for p in get_active_projects(ctx) if tool_num in p.tool_number),
                    None,
                )
                if project:
                    quote = QuotingAssistantModule().run(ctx, project_id=project.id)
                    return ChatResponse(
                        answer=(
                            f"Suggested quote for Tool {project.tool_number}: "
                            f"Design {quote.suggested.design_hours}h, "
                            f"Surfacing {quote.suggested.surfacing_hours}h, "
                            f"Total {quote.suggested.total_hours}h "
                            f"(confidence {quote.confidence_percent:.0f}%)."
                        ),
                        data=quote.model_dump(),
                    )
            return ChatResponse(
                answer="Specify a tool number to estimate, e.g. 'Estimate Tool 3175'."
            )

        if re.search(r"compare|previous|historical", q):
            insights = DashboardInsightsModule().run(ctx, limit=5)
            quoting = [i for i in insights if i.category == "quoting"]
            if quoting:
                return ChatResponse(answer=quoting[0].detail or quoting[0].title, insights=quoting)
            return ChatResponse(answer="No similar project comparisons found for active tools.")

        if re.search(r"risk|overdue|late|problem", q):
            insights = DashboardInsightsModule().run(ctx, limit=5)
            summary = "; ".join(i.title for i in insights[:4]) or "No significant risks detected."
            return ChatResponse(answer=summary, insights=insights)

        if re.search(r"utilization|utilisation|busy|overload", q):
            util = get_designer_utilization(ctx)
            overloaded = [r for r in util if r["utilization"] >= 90]
            if overloaded:
                names = ", ".join(
                    f"{r['user'].first_name} ({r['utilization']:.0f}%)"
                    for r in overloaded[:4]
                )
                return ChatResponse(answer=f"High utilization: {names}.")
            avg = sum(r["utilization"] for r in util) / len(util) if util else 0
            return ChatResponse(answer=f"Team average utilization is {avg:.0f}%.")

        # Default: return top insights
        insights = DashboardInsightsModule().run(ctx, limit=5)
        if insights:
            return ChatResponse(
                answer="Here are the top engineering insights: "
                + "; ".join(i.title for i in insights[:3])
                + ".",
                insights=insights,
            )
        return ChatResponse(
            answer="I can help with projects due, resource availability, customer workload, quotes, and risks. Try asking a specific question.",
        )
