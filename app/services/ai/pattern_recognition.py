"""Pattern recognition for similar projects and historical matching."""

from __future__ import annotations

from decimal import Decimal

from app.models.models import Project
from app.schemas.ai import SimilarProjectRef
from app.services.ai.base import AiContext, AiProvider, confidence_from_sample_size, round_hours
from app.services.ai.context import get_completed_projects


class PatternMatcher(AiProvider):
    name = "pattern_recognition"

    def similarity_score(
        self,
        source: Project,
        candidate: Project,
        *,
        customer_weight: float = 0.45,
        type_weight: float = 0.35,
        hours_weight: float = 0.20,
    ) -> float:
        score = 0.0
        if source.customer_id and source.customer_id == candidate.customer_id:
            score += customer_weight
        if source.project_type_id and source.project_type_id == candidate.project_type_id:
            score += type_weight
        source_quoted = float(source.quoted_hours or 0)
        candidate_actual = float(candidate.actual_hours or 0)
        if source_quoted > 0 and candidate_actual > 0:
            ratio = min(source_quoted, candidate_actual) / max(source_quoted, candidate_actual)
            score += hours_weight * ratio
        elif candidate_actual > 0:
            score += hours_weight * 0.5
        return round(score * 100, 1)

    def find_similar(
        self,
        ctx: AiContext,
        project: Project,
        *,
        limit: int = 5,
    ) -> list[SimilarProjectRef]:
        from app.crud.project_metrics import build_project_read

        candidates = get_completed_projects(
            ctx,
            customer_id=project.customer_id,
            project_type_id=project.project_type_id,
            limit=limit * 3,
        )
        if not candidates:
            candidates = get_completed_projects(ctx, limit=limit * 3)

        scored: list[tuple[float, Project]] = []
        for candidate in candidates:
            if candidate.id == project.id:
                continue
            scored.append((self.similarity_score(project, candidate), candidate))
        scored.sort(key=lambda row: row[0], reverse=True)

        results: list[SimilarProjectRef] = []
        for score, candidate in scored[:limit]:
            read = build_project_read(ctx.db, candidate)
            results.append(
                SimilarProjectRef(
                    project_id=candidate.id,
                    tool_number=candidate.tool_number,
                    customer_name=read.customer_name,
                    actual_hours=round_hours(Decimal(str(candidate.actual_hours))),
                    quoted_hours=round_hours(Decimal(str(candidate.quoted_hours))),
                    similarity_score=score,
                )
            )
        return results

    def estimate_hours_breakdown(
        self,
        similar: list[SimilarProjectRef],
    ) -> tuple[dict[str, float], float]:
        if not similar:
            return (
                {"design": 0, "surfacing": 0, "checking": 0, "bom": 0, "total": 0},
                0,
            )
        avg_total = sum(p.actual_hours for p in similar) / len(similar)
        # Industry-typical mold design hour distribution when task-level data unavailable
        design = avg_total * 0.70
        surfacing = avg_total * 0.18
        checking = avg_total * 0.08
        bom = avg_total * 0.04
        confidence = confidence_from_sample_size(len(similar))
        return (
            {
                "design": round(design, 1),
                "surfacing": round(surfacing, 1),
                "checking": round(checking, 1),
                "bom": round(bom, 1),
                "total": round(avg_total, 1),
            },
            confidence,
        )


pattern_matcher = PatternMatcher()
