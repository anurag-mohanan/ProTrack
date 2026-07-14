"""Schemas for the AI & Analytics framework."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AiInsight(BaseModel):
    """A single AI-generated insight or recommendation."""

    id: str
    module: str
    category: str
    severity: str = "info"
    title: str
    detail: str | None = None
    href: str | None = None
    confidence: float = Field(ge=0, le=100, default=80)
    entity_type: str | None = None
    entity_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class MorningBrief(BaseModel):
    greeting: str
    active_projects: int = 0
    due_this_week: int = 0
    high_risk_projects: int = 0
    engineers_available: int = 0
    utilization_percent: float = 0
    missing_timesheets: int = 0
    over_budget_projects: int = 0
    late_milestones: int = 0
    insights: list[AiInsight] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class QuoteHourBreakdown(BaseModel):
    design_hours: float = 0
    surfacing_hours: float = 0
    checking_hours: float = 0
    bom_hours: float = 0
    total_hours: float = 0


class SimilarProjectRef(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str | None = None
    actual_hours: float = 0
    quoted_hours: float = 0
    similarity_score: float = 0


class QuoteRecommendation(BaseModel):
    project_id: UUID | None = None
    tool_number: str | None = None
    customer_name: str | None = None
    project_type_name: str | None = None
    suggested: QuoteHourBreakdown
    confidence_percent: float = 0
    similar_projects: list[SimilarProjectRef] = Field(default_factory=list)
    rationale: str | None = None


class ResourceRecommendation(BaseModel):
    role: str
    user_id: UUID
    user_name: str
    score: float = 0
    utilization_percent: float = 0
    available_hours: float = 0
    reasoning: str
    similar_project_count: int = 0


class ResourceOptimizationResult(BaseModel):
    project_id: UUID | None = None
    designers: list[ResourceRecommendation] = Field(default_factory=list)
    surfacers: list[ResourceRecommendation] = Field(default_factory=list)
    design_leaders: list[ResourceRecommendation] = Field(default_factory=list)


class ProjectHealthAnalysis(BaseModel):
    project_id: UUID
    tool_number: str
    health: str
    score: float = 0
    factors: list[str] = Field(default_factory=list)
    override_allowed: bool = True
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class SchedulePrediction(BaseModel):
    project_id: UUID
    tool_number: str
    predicted_completion: date | None = None
    target_completion: date | None = None
    confidence_percent: float = 0
    reasons: list[str] = Field(default_factory=list)
    late_milestones: int = 0
    bottleneck: str | None = None


class ProductivityMetrics(BaseModel):
    user_id: UUID | None = None
    user_name: str | None = None
    team_id: UUID | None = None
    team_name: str | None = None
    projects_completed: int = 0
    billable_percent: float = 0
    hours_logged: float = 0
    milestones_completed: int = 0
    average_delay_days: float = 0
    quoted_vs_actual_ratio: float = 0
    engineering_changes: int = 0
    trend: str = "stable"
    achievements: list[str] = Field(default_factory=list)


class KnowledgeRecord(BaseModel):
    id: UUID
    project_id: UUID
    tool_number: str
    customer_name: str | None = None
    project_type_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    quoted_hours: float = 0
    actual_hours: float = 0
    milestone_count: int = 0
    engineering_change_count: int = 0
    mechanism: str | None = None
    keywords: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None


class LessonLearnedRead(BaseModel):
    id: UUID
    project_id: UUID
    tool_number: str | None = None
    what_went_well: str | None = None
    problems_encountered: str | None = None
    recommendations: str | None = None
    hours_observations: str | None = None
    created_by_name: str | None = None
    created_at: datetime


class LessonLearnedCreate(BaseModel):
    project_id: UUID
    what_went_well: str | None = None
    problems_encountered: str | None = None
    recommendations: str | None = None
    hours_observations: str | None = None


class EngineeringChangeAnalytics(BaseModel):
    customer_id: UUID | None = None
    customer_name: str | None = None
    project_id: UUID | None = None
    tool_number: str | None = None
    total_changes: int = 0
    open_changes: int = 0
    hours_added: float = 0
    customer_request_count: int = 0
    internal_change_count: int = 0


class CustomerIntelligence(BaseModel):
    customer_id: UUID
    customer_name: str
    average_project_hours: float = 0
    average_schedule_variance_days: float = 0
    engineering_change_count: int = 0
    on_time_delivery_percent: float = 0
    active_workload_hours: float = 0
    active_project_count: int = 0
    customer_score: float = 0
    trend: str = "stable"


class CapacityForecast(BaseModel):
    horizon_days: int
    total_capacity_hours: float = 0
    projected_utilization_percent: float = 0
    idle_capacity_hours: float = 0
    hiring_recommendation: str | None = None
    peak_period: str | None = None
    customer_demand: list[dict] = Field(default_factory=list)


class TimesheetSuggestion(BaseModel):
    entry_date: date
    project_id: UUID | None = None
    tool_number: str | None = None
    task_type_id: UUID | None = None
    task_name: str | None = None
    suggested_hours: float = 0
    reason: str
    confidence: float = 0


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    insights: list[AiInsight] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)


class WallProjectCard(BaseModel):
    """Compact project card for planning-board / executive wall displays."""

    project_id: UUID | None = None
    tool_number: str
    customer_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    contributor_names: list[str] = Field(default_factory=list)
    team_name: str | None = None
    due_date: date | None = None
    health: str | None = None
    execution_status: str | None = None
    project_stage: str | None = None
    current_milestone: str | None = None
    progress_percent: float = 0
    quoted_hours: float = 0
    actual_hours: float = 0
    variance_hours: float = 0
    variance_percent: float | None = None
    attention_reason: str | None = None


class WallTeamLiveBlock(BaseModel):
    """Live projects rolled up by delivery team for Program Manager monitoring."""

    team_id: UUID | None = None
    team_name: str
    engineering_manager_name: str | None = None
    design_leader_name: str | None = None
    active_count: int = 0
    on_hold_count: int = 0
    red_count: int = 0
    yellow_count: int = 0
    projects: list[WallProjectCard] = Field(default_factory=list)


class ExecutiveWallData(BaseModel):
    active_projects: int = 0
    utilization_percent: float = 0
    late_milestones: int = 0
    current_deliveries: list[dict] = Field(default_factory=list)
    recent_releases: list[dict] = Field(default_factory=list)
    capacity_hours: float = 0
    hours_logged_month: float = 0
    customer_distribution: list[dict] = Field(default_factory=list)
    health_summary: dict = Field(default_factory=dict)
    teams_live: list[WallTeamLiveBlock] = Field(default_factory=list)
    upcoming_deliveries: list[WallProjectCard] = Field(default_factory=list)
    late_deliveries: list[WallProjectCard] = Field(default_factory=list)
    refreshed_at: datetime = Field(default_factory=datetime.utcnow)


class AiOperationsSummary(BaseModel):
    insights: list[AiInsight] = Field(default_factory=list)
    morning_brief: MorningBrief | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
