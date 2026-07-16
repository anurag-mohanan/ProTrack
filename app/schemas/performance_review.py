from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PerformanceReviewItemUpdate(BaseModel):
    id: UUID | None = None
    prompt: str
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    employee_comment: str | None = None
    manager_comment: str | None = None
    sort_order: int = 0


class PerformanceReviewSectionUpdate(BaseModel):
    id: UUID | None = None
    title: str
    description: str | None = None
    sort_order: int = 0
    items: list[PerformanceReviewItemUpdate] = Field(default_factory=list)


class PerformanceReviewCycleCreate(BaseModel):
    title: str
    review_year: int
    start_date: date | None = None
    end_date: date | None = None
    due_date: date | None = None
    status: str = "draft"


class PerformanceReviewCycleRead(PerformanceReviewCycleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by_id: UUID | None = None
    is_active: bool = True


class PerformanceReviewCreate(BaseModel):
    employee_id: UUID
    reviewer_id: UUID | None = None
    team_id: UUID
    cycle_id: UUID | None = None
    period_label: str
    review_date: date | None = None
    due_date: date | None = None
    overall_score: Decimal | None = Field(default=None, ge=0, le=5)
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    status: str = "draft"
    sections: list[PerformanceReviewSectionUpdate] = Field(default_factory=list)


class PerformanceReviewUpdate(BaseModel):
    reviewer_id: UUID | None = None
    team_id: UUID | None = None
    period_label: str | None = None
    review_date: date | None = None
    due_date: date | None = None
    overall_score: Decimal | None = Field(default=None, ge=0, le=5)
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    status: str | None = None
    acknowledged: bool | None = None
    sections: list[PerformanceReviewSectionUpdate] | None = None


class PerformanceReviewItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt: str
    rating: Decimal | None = None
    employee_comment: str | None = None
    manager_comment: str | None = None
    sort_order: int


class PerformanceReviewSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    sort_order: int
    items: list[PerformanceReviewItemRead] = Field(default_factory=list)


class PerformanceReviewRead(BaseModel):
    id: UUID
    cycle_id: UUID | None = None
    cycle_title: str | None = None
    employee_id: UUID
    employee_name: str
    reviewer_id: UUID
    reviewer_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    period_label: str
    status: str
    review_date: date | None = None
    due_date: date | None = None
    overall_score: Decimal | None = None
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    submitted_at: datetime | None = None
    acknowledged_at: datetime | None = None
    sections: list[PerformanceReviewSectionRead] = Field(default_factory=list)
    is_editable: bool = False
    can_acknowledge: bool = False


class PerformanceReviewTeamMemberRead(BaseModel):
    user_id: UUID
    name: str
    email: str
    team_id: UUID
    team_name: str
    review_count: int = 0

