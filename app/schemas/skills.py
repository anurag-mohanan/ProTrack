"""Request bodies for the engineering skills API (responses are built in ``services.skills.views``)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SkillWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    kind: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    discipline_id: UUID | None = None
    customer_id: UUID | None = None
    is_critical: bool = False
    min_verified_coverage: int | None = Field(default=None, ge=1, le=100)
    specialist_level: int | None = Field(default=None, ge=1, le=5)
    reassessment_months: int | None = Field(default=None, ge=1, le=120)
    sort_order: int = 0
    is_active: bool = True


class CategoryRename(BaseModel):
    old: str = Field(min_length=1)
    new: str = Field(min_length=1, max_length=100)


class RelationshipWrite(BaseModel):
    from_skill_id: UUID
    to_skill_id: UUID
    relation_type: str
    note: str | None = None


class ProficiencyLevelWrite(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str | None = None


class DeclarationWrite(BaseModel):
    skill_id: UUID
    declared_level: int = Field(ge=1, le=5)
    years_experience: Decimal | None = Field(default=None, ge=0, le=60)
    last_used_on: date | None = None
    employee_note: str | None = None
    submit_for_verification: bool = False


class AssessmentWrite(BaseModel):
    skill_id: UUID
    decision: Literal["verify", "reject", "request_reassessment"]
    level: int | None = Field(default=None, ge=1, le=5)
    method: Literal["manager_assessment", "independent_assessment"] = "manager_assessment"
    feedback: str | None = None
    confidential_note: str | None = None


class ArchiveWrite(BaseModel):
    reason: str | None = None


class EvidenceWrite(BaseModel):
    project_id: UUID
    note: str | None = None


class PlanWrite(BaseModel):
    user_id: UUID | None = None
    skill_id: UUID
    target_level: int = Field(ge=1, le=5)
    objective: str | None = None
    training_required: bool = False
    training_requirement: str | None = None
    is_knowledge_transfer: bool = False
    mentor_id: UUID | None = None
    target_review_date: date | None = None
    status: Literal["planned", "in_progress", "completed", "cancelled"] = "planned"
    progress_note: str | None = None


class RequirementWrite(BaseModel):
    skill_id: UUID
    min_level: int = Field(ge=1, le=5)
    is_mandatory: bool = True
    note: str | None = None


class RequirementSpecWrite(BaseModel):
    skill_id: UUID
    min_level: int = Field(ge=1, le=5)
    is_mandatory: bool = True


class MatchRequest(BaseModel):
    project_id: UUID | None = None
    requirements: list[RequirementSpecWrite] | None = None
    team_id: UUID | None = None
    start: date | None = None
    granularity: Literal["week", "month"] = "week"
    periods: int = Field(default=4, ge=1, le=26)
