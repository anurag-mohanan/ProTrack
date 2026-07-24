"""Employee training schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrainingCourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None = None
    owner_department: str | None = None
    estimated_minutes: int = 30
    external_url: str | None = None
    is_required_for_onboarding: bool = False
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TrainingCourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    owner_department: str | None = None
    estimated_minutes: int = Field(default=30, ge=1, le=480)
    external_url: str | None = None
    is_required_for_onboarding: bool = False
    sort_order: int = 100


class TrainingAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    user_id: UUID
    status: str
    due_date: date | None = None
    assigned_by_id: UUID | None = None
    completed_at: datetime | None = None
    completed_by_id: UUID | None = None
    notes: str | None = None
    onboarding_checklist_id: UUID | None = None
    course_title: str | None = None
    course_code: str | None = None
    estimated_minutes: int | None = None
    external_url: str | None = None
    is_required_for_onboarding: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TrainingAssignRequest(BaseModel):
    course_id: UUID
    user_ids: list[UUID] = Field(min_length=1)
    due_date: date | None = None
