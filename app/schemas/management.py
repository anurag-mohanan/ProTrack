"""Request bodies for strategic management (objectives, initiatives, actions, reviews)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ObjectiveStatus = Literal["not_started", "on_track", "at_risk", "delayed", "completed", "cancelled"]
Category = Literal["financial", "delivery", "efficiency", "customer", "workforce", "quality", "growth", "other"]
Unit = Literal["currency", "percentage", "count", "hours", "days", "ratio"]
Priority = Literal["low", "medium", "high", "critical"]
InitiativeStatus = Literal["planned", "in_progress", "on_hold", "at_risk", "completed", "cancelled"]
ActionStatus = Literal["open", "in_progress", "blocked", "completed", "cancelled"]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ObjectiveCreate(_Body):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    fy_start_year: int = Field(ge=2000, le=2100)
    period_type: Literal["annual", "quarterly", "monthly"] = "annual"
    period_index: int | None = Field(None, ge=1, le=12)
    category: Category = "other"
    unit: Unit
    direction: Literal["increase", "decrease"] = "increase"
    measurement: Literal["automatic", "manual"] = "manual"
    metric_key: str | None = Field(None, max_length=60)
    metric_params: dict | None = None
    target_value: Decimal
    baseline_value: Decimal | None = None
    baseline_note: str | None = Field(None, max_length=500)
    owner_id: UUID | None = None
    supporting_team_id: UUID | None = None
    start_date: date | None = None
    target_date: date | None = None
    related_kpis: list[str] = Field(default_factory=list, max_length=20)
    related_project_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check(self):
        if self.measurement == "automatic" and not self.metric_key:
            raise ValueError("An automatic objective needs a KPI")
        if self.measurement == "manual" and (self.metric_key or self.metric_params):
            raise ValueError("A manual objective cannot reference an automatic KPI")
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("Target date is before the start date")
        return self


class ObjectiveUpdate(_Body):
    """Descriptive fields and status. Targets, baselines and the KPI change through their own endpoints."""

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    category: Category | None = None
    owner_id: UUID | None = None
    supporting_team_id: UUID | None = None
    start_date: date | None = None
    target_date: date | None = None
    status: ObjectiveStatus | None = None
    status_reason: str | None = Field(None, max_length=2000)
    related_kpis: list[str] | None = Field(None, max_length=20)
    related_project_ids: list[UUID] | None = Field(None, max_length=50)


class TargetChange(_Body):
    target_value: Decimal | None = None
    baseline_value: Decimal | None = None
    baseline_note: str | None = Field(None, max_length=500)
    reason: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def _check(self):
        if self.target_value is None and self.baseline_value is None:
            raise ValueError("Give a new target, a new baseline or both")
        return self


class ApprovalNote(_Body):
    note: str | None = Field(None, max_length=2000)


class MeasurementCreate(_Body):
    value: Decimal
    period_start: date
    period_end: date
    note: str | None = Field(None, max_length=2000)
    evidence: str = Field(min_length=3, max_length=4000)
    supersedes_id: UUID | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.period_end < self.period_start:
            raise ValueError("Period end is before period start")
        return self


class CommentCreate(_Body):
    kind: Literal["comment", "decision"] = "comment"
    text: str = Field(min_length=2, max_length=5000)


class Milestone(_Body):
    title: str = Field(min_length=2, max_length=200)
    due_date: date | None = None
    done: bool = False


class InitiativeCreate(_Body):
    name: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    objective_id: UUID | None = None
    owner_id: UUID | None = None
    start_date: date | None = None
    target_date: date | None = None
    status: InitiativeStatus = "planned"
    progress_percent: int = Field(0, ge=0, le=100)
    priority: Priority = "medium"
    milestones: list[Milestone] = Field(default_factory=list, max_length=50)
    dependencies: str | None = Field(None, max_length=4000)
    risks: str | None = Field(None, max_length=4000)
    notes: str | None = Field(None, max_length=8000)
    related_project_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("Target date is before the start date")
        return self


class InitiativeUpdate(_Body):
    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    objective_id: UUID | None = None
    owner_id: UUID | None = None
    start_date: date | None = None
    target_date: date | None = None
    status: InitiativeStatus | None = None
    status_reason: str | None = Field(None, max_length=2000)
    progress_percent: int | None = Field(None, ge=0, le=100)
    priority: Priority | None = None
    milestones: list[Milestone] | None = Field(None, max_length=50)
    dependencies: str | None = Field(None, max_length=4000)
    risks: str | None = Field(None, max_length=4000)
    notes: str | None = Field(None, max_length=8000)
    related_project_ids: list[UUID] | None = Field(None, max_length=50)


class ActionCreate(_Body):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    review_id: UUID | None = None
    objective_id: UUID | None = None
    initiative_id: UUID | None = None
    project_id: UUID | None = None
    owner_id: UUID
    priority: Priority = "medium"
    due_date: date | None = None


class ActionUpdate(_Body):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    owner_id: UUID | None = None
    priority: Priority | None = None
    due_date: date | None = None
    status: ActionStatus | None = None
    status_reason: str | None = Field(None, max_length=2000)
    completion_evidence: str | None = Field(None, max_length=4000)


class ReviewCreate(_Body):
    review_type: Literal["monthly", "quarterly", "annual"]
    fy_start_year: int = Field(ge=2000, le=2100)
    period_index: int | None = Field(None, ge=1, le=12)
    customer_id: UUID | None = None
    team_id: UUID | None = None


class ReviewUpdate(_Body):
    executive_summary: str | None = Field(None, max_length=20000)
    title: str | None = Field(None, min_length=3, max_length=200)


class DecisionCreate(_Body):
    text: str = Field(min_length=3, max_length=5000)
    action_title: str | None = Field(None, min_length=3, max_length=200)
    action_owner_id: UUID | None = None
    action_due_date: date | None = None
    action_priority: Priority = "medium"

    @model_validator(mode="after")
    def _check(self):
        if self.action_title and not self.action_owner_id:
            raise ValueError("An action from a decision needs an owner")
        return self
