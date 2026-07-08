"""AI & Analytics API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, get_db
from app.core.permissions import FULL_ACCESS_ROLES, get_role_name
from app.models.intelligence import LessonLearned
from app.models.models import User
from app.schemas.ai import (
    AiInsight,
    AiOperationsSummary,
    ChatMessage,
    ChatResponse,
    CustomerIntelligence,
    ExecutiveWallData,
    KnowledgeRecord,
    LessonLearnedCreate,
    LessonLearnedRead,
    MorningBrief,
    ProductivityMetrics,
    ProjectHealthAnalysis,
    QuoteRecommendation,
    ResourceOptimizationResult,
    SchedulePrediction,
    TimesheetSuggestion,
)
from app.services.ai.engine import ai_engine

router = APIRouter(prefix="/ai", tags=["ai"])


def _require_manager_access(db: Session, user: User) -> None:
    role = get_role_name(db, user)
    if role not in FULL_ACCESS_ROLES and role not in ("Design Leader", "Project Manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/operations", response_model=AiOperationsSummary)
def get_ai_operations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    name = f"{current_user.first_name} {current_user.last_name}".strip()
    return ai_engine.run_operations_summary(db, actor_name=name)


@router.get("/insights", response_model=list[AiInsight])
def get_ai_insights(
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    return ai_engine.run("dashboard_insights", db, limit=limit)


@router.get("/morning-brief", response_model=MorningBrief)
def get_morning_brief(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    name = f"{current_user.first_name} {current_user.last_name}".strip()
    return ai_engine.run("morning_brief", db, actor_name=name)


@router.get("/quote/{project_id}", response_model=QuoteRecommendation)
def get_quote_recommendation(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_engine.run("quoting_assistant", db, project_id=project_id, use_cache=False)


@router.get("/resources", response_model=ResourceOptimizationResult)
def get_resource_recommendations(
    project_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    return ai_engine.run("resource_optimizer", db, project_id=project_id)


@router.get("/health", response_model=list[ProjectHealthAnalysis])
def get_health_analysis(
    project_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_engine.run("project_health_engine", db, project_id=project_id)


@router.get("/schedule", response_model=list[SchedulePrediction])
def get_schedule_predictions(
    project_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    result = ai_engine.run("schedule_predictor", db, project_id=project_id)
    if isinstance(result, SchedulePrediction):
        return [result]
    return result


@router.get("/customers", response_model=list[CustomerIntelligence])
def get_customer_intelligence(
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    result = ai_engine.run("customer_analytics", db, customer_id=customer_id)
    if isinstance(result, CustomerIntelligence):
        return [result]
    return result


@router.get("/knowledge", response_model=list[KnowledgeRecord])
def search_knowledge_base(
    q: str = Query("", alias="query"),
    customer_id: UUID | None = None,
    project_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_engine.run(
        "knowledge_base",
        db,
        query=q,
        customer_id=customer_id,
        project_type=project_type,
        limit=limit,
        use_cache=False,
    )


@router.post("/lessons", response_model=LessonLearnedRead, status_code=status.HTTP_201_CREATED)
def create_lesson_learned(
    payload: LessonLearnedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = LessonLearned(
        project_id=payload.project_id,
        created_by_id=current_user.id,
        what_went_well=payload.what_went_well,
        problems_encountered=payload.problems_encountered,
        recommendations=payload.recommendations,
        hours_observations=payload.hours_observations,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return LessonLearnedRead(
        id=row.id,
        project_id=row.project_id,
        what_went_well=row.what_went_well,
        problems_encountered=row.problems_encountered,
        recommendations=row.recommendations,
        hours_observations=row.hours_observations,
        created_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        created_at=row.created_at,
    )


@router.get("/productivity", response_model=list[ProductivityMetrics])
def get_productivity_analytics(
    user_id: UUID | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    return ai_engine.run("productivity_analytics", db, user_id=user_id, team_id=team_id)


@router.get("/kpis")
def get_engineering_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    return ai_engine.run("engineering_kpi", db)


@router.get("/timesheet-suggestions", response_model=list[TimesheetSuggestion])
def get_timesheet_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_engine.run("timesheet_suggestions", db, user_id=current_user.id, use_cache=False)


@router.post("/chat", response_model=ChatResponse)
def ai_chat(
    message: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ai_engine.run(
        "chat_assistant",
        db,
        question=message.content,
        use_cache=False,
    )


@router.get("/executive-wall", response_model=ExecutiveWallData)
def get_executive_wall(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manager_access(db, current_user)
    return ai_engine.run("executive_wall", db, cache_ttl=60)
