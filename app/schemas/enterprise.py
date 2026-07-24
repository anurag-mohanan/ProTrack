"""R4 enterprise schemas — documents, learning plans, legal entities."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LegalEntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    currency_code: str
    is_default: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LegalEntityCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    currency_code: str = Field(default="INR", max_length=3)
    is_default: bool = False
    is_active: bool = True


class DocumentAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID
    title: str | None = None
    filename: str
    content_type: str | None = None
    size_bytes: int
    storage_backend: str
    storage_key: str
    checksum: str | None = None
    uploaded_by_id: UUID | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LearningPlanItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    stream_skill_id: UUID
    skill_name: str | None = None
    current_proficiency: str | None = None
    target_proficiency: str
    status: str
    due_date: date | None = None
    notes: str | None = None
    sort_order: int = 0


class LearningPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    status: str
    created_by_id: UUID | None = None
    items: list[LearningPlanItemRead] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LearningPlanCreateFromGaps(BaseModel):
    user_id: UUID
    title: str | None = None
    target_proficiency: str = "proficient"


class LearningPlanItemStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)


class SkillGapRead(BaseModel):
    stream_skill_id: UUID
    skill_name: str
    current_proficiency: str
    target_proficiency: str
