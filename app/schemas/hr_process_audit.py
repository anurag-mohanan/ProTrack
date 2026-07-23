"""HR Process Audit schemas."""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

AuditFlag = Literal[
    "incomplete_onboarding",
    "missing_exit",
    "orphan_placement",
    "exit_done_still_active",
]


class ProcessAuditItem(BaseModel):
    flag: AuditFlag
    severity: Literal["high", "medium", "low"] = "medium"
    title: str
    subject_name: str
    subject_user_id: Optional[UUID] = None
    checklist_id: Optional[UUID] = None
    exit_interview_id: Optional[UUID] = None
    detail: str
    deep_link: str
    anchor_date: Optional[str] = None


class ProcessAuditRead(BaseModel):
    as_of: str
    sla_days: int
    total: int
    counts: dict[str, int] = Field(default_factory=dict)
    items: list[ProcessAuditItem] = Field(default_factory=list)
