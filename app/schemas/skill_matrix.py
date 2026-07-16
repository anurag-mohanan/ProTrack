from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class SkillProficiencyScaleItem(BaseModel):
    value: str
    label: str
    short_label: str
    tone: str
    guidance: str


class StreamSkillColumn(BaseModel):
    id: UUID
    name: str
    sort_order: int = 0


class SkillMatrixPersonRead(BaseModel):
    user_id: UUID
    name: str
    role: str | None = None
    primary_tool: str | None = None
    work_function: str | None = None
    stream_id: UUID | None = None
    stream_name: str | None = None
    company_experience: str | None = None
    industry_experience: str | None = None
    joining_date: date | None = None
    first_job_date: date | None = None
    ratings: dict[str, str | None] = Field(default_factory=dict)


class SkillMatrixRead(BaseModel):
    team_id: UUID
    stream_id: UUID | None = None
    stream_name: str | None = None
    title: str
    proficiency_scale: list[SkillProficiencyScaleItem] = Field(default_factory=list)
    skills: list[StreamSkillColumn] = Field(default_factory=list)
    people: list[SkillMatrixPersonRead] = Field(default_factory=list)


class SkillRatingUpsertItem(BaseModel):
    user_id: UUID
    stream_skill_id: UUID
    proficiency: str | None = None
    notes: str | None = None


class SkillMatrixUpsertRequest(BaseModel):
    ratings: list[SkillRatingUpsertItem] = Field(default_factory=list)


class SkillMatrixUpsertResponse(BaseModel):
    updated_count: int
    matrix: SkillMatrixRead
