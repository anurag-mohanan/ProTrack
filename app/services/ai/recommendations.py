"""Recommendation primitives for resources and assignments."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus
from app.models.models import Project, Role, User
from app.schemas.ai import AiInsight, ResourceOptimizationResult, ResourceRecommendation
from app.services.ai.base import AiContext, AiProvider, round_hours
from app.services.ai.context import get_designer_utilization
from app.services.ai.pattern_recognition import pattern_matcher


class Recommender(AiProvider):
    name = "recommendations"

    def resource_insights(self, ctx: AiContext) -> list[AiInsight]:
        insights: list[AiInsight] = []
        util_rows = get_designer_utilization(ctx)

        overloaded = [r for r in util_rows if r["utilization"] >= 95]
        for row in overloaded[:2]:
            person = row["user"]
            name = f"{person.first_name} {person.last_name}".strip()
            insights.append(
                AiInsight(
                    id=f"resource-overload-{person.id}",
                    module="dashboard_insights",
                    category="resource",
                    severity="warning",
                    title=f"{name} will exceed capacity this week",
                    detail=f"Already {row['hours']:.1f} hours scheduled ({row['utilization']:.0f}% utilization).",
                    href="/workload",
                    confidence=91,
                    entity_type="user",
                    entity_id=person.id,
                )
            )

        available = [r for r in util_rows if r["utilization"] < 70]
        for row in available[:2]:
            person = row["user"]
            name = f"{person.first_name} {person.last_name}".strip()
            insights.append(
                AiInsight(
                    id=f"resource-available-{person.id}",
                    module="dashboard_insights",
                    category="resource",
                    severity="info",
                    title=f"{name} has available capacity",
                    detail=f"{row['available_hours']:.0f} hours free this week ({row['utilization']:.0f}% utilized).",
                    href="/resource-planning",
                    confidence=85,
                    entity_type="user",
                    entity_id=person.id,
                )
            )

        from app.services.ai.context import get_customer_workload_share

        workload = get_customer_workload_share(ctx)
        if workload:
            top = workload[0]
            if top["share_percent"] >= 30:
                insights.append(
                    AiInsight(
                        id=f"resource-customer-{top['customer_id']}",
                        module="dashboard_insights",
                        category="resource",
                        severity="info",
                        title=f"{top['customer_name']} represents {top['share_percent']}% of engineering workload",
                        detail="Consider balancing workload across customers for delivery resilience.",
                        href="/reports?tab=customer-summary",
                        confidence=87,
                    )
                )

        return insights

    def optimize_resources(
        self,
        ctx: AiContext,
        *,
        project_id: UUID | None = None,
    ) -> ResourceOptimizationResult:
        project = ctx.db.get(Project, project_id) if project_id else None
        util_rows = get_designer_utilization(ctx)

        def build_recs(role_filter: str, role_label: str) -> list[ResourceRecommendation]:
            recs: list[ResourceRecommendation] = []
            for row in util_rows:
                person: User = row["user"]
                role_name = ctx.db.scalar(
                    select(Role.name).where(Role.id == person.role_id)
                )
                if role_filter == "designer" and role_name not in (
                    "Senior Designer", "Designer", "Junior Designer"
                ):
                    continue
                if role_filter == "surfacer" and role_name != "Surfacer":
                    continue
                if role_filter == "leader" and role_name != "Design Leader":
                    continue

                similar_count = 0
                if project:
                    similar = pattern_matcher.find_similar(ctx, project, limit=10)
                    similar_count = sum(
                        1
                        for s in similar
                        if ctx.db.scalar(
                            select(func.count())
                            .select_from(Project)
                            .where(
                                Project.id == s.project_id,
                                (Project.designer_id == person.id)
                                | (Project.surfacer_id == person.id)
                                | (Project.design_leader_id == person.id),
                            )
                        )
                    )

                util_penalty = max(0, row["utilization"] - 50) * 0.5
                avail_bonus = row["available_hours"] * 0.8
                exp_bonus = similar_count * 5
                score = avail_bonus - util_penalty + exp_bonus

                reasoning_parts = [
                    f"Current utilization {row['utilization']:.0f}%",
                    f"{row['available_hours']:.0f} hours available",
                ]
                if similar_count:
                    reasoning_parts.append(f"{similar_count} similar project(s) completed")

                recs.append(
                    ResourceRecommendation(
                        role=role_label,
                        user_id=person.id,
                        user_name=f"{person.first_name} {person.last_name}".strip(),
                        score=round(score, 1),
                        utilization_percent=row["utilization"],
                        available_hours=row["available_hours"],
                        reasoning=f"Assign to {person.first_name}: " + "; ".join(reasoning_parts) + ".",
                        similar_project_count=similar_count,
                    )
                )
            recs.sort(key=lambda r: r.score, reverse=True)
            return recs[:5]

        return ResourceOptimizationResult(
            project_id=project_id,
            designers=build_recs("designer", "Designer"),
            surfacers=build_recs("surfacer", "Surfacer"),
            design_leaders=build_recs("leader", "Design Leader"),
        )


recommender = Recommender()
