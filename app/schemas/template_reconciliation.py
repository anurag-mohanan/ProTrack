from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateMilestoneDecision(BaseModel):
    template_milestone_id: UUID
    action: Literal["match", "add"]
    milestone_id: UUID | None = None


class ExistingMilestoneDecision(BaseModel):
    milestone_id: UUID
    action: Literal["retain", "supersede", "archive", "merge"]
    merge_into_id: UUID | None = None


class TemplateReconciliationPreviewRequest(BaseModel):
    template_id: UUID
    template_decisions: list[TemplateMilestoneDecision] = Field(default_factory=list)
    existing_decisions: list[ExistingMilestoneDecision] = Field(default_factory=list)
    apply_template_hours: bool = False
    schedule_new: bool = True

    def template_map(self) -> dict[UUID, tuple[str, UUID | None]]:
        return {d.template_milestone_id: (d.action, d.milestone_id) for d in self.template_decisions}

    def existing_map(self) -> dict[UUID, tuple[str, UUID | None]]:
        return {d.milestone_id: (d.action, d.merge_into_id) for d in self.existing_decisions}


class TemplateReconciliationApplyRequest(TemplateReconciliationPreviewRequest):
    preview_fingerprint: str = Field(min_length=64, max_length=64)
    plan_version: int = Field(ge=0)
    # Client-generated idempotency key; resubmitting the same key returns the first result.
    request_key: str = Field(min_length=8, max_length=64)
    confirm: bool
    acknowledge_estimate_change: bool = False
    reason: str | None = Field(default=None, max_length=1000)
