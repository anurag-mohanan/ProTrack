"""Backward-compatible bridge to the AI insights engine."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.dashboard import EngineeringInsight
from app.services.ai.engine import ai_engine


def generate_engineering_insights(db: Session, *, limit: int = 8) -> list[EngineeringInsight]:
    """Generate insights via the AI engine (replaces inline rule logic)."""
    ai_insights = ai_engine.run("dashboard_insights", db, limit=limit)
    return [
        EngineeringInsight(
            category=insight.category,
            severity=insight.severity,
            title=insight.title,
            detail=insight.detail,
            href=insight.href,
        )
        for insight in ai_insights
    ]
