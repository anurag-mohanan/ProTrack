"""Onboarding checklist API schemas (PP-HRD-FO-14)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema

OnboardingItemStatus = Literal[
    "not_started",
    "ready",
    "in_progress",
    "waiting",
    "blocked",
    "completed",
    "not_required",
    "waived",
    "cancelled",
    # Legacy values accepted on input and mapped to not_started / not_required.
    "pending",
    "not_applicable",
]
OnboardingChecklistStatus = Literal["in_progress", "completed", "cancelled"]


class OnboardingChecklistCreate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: str = Field(min_length=2, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_email: Optional[str] = Field(default=None, max_length=255)
    employee_code: Optional[str] = Field(default=None, max_length=40)
    joining_date: Optional[date] = None
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    template_id: Optional[UUID] = None


class OnboardingChecklistUpdate(BlankOptionalFieldsMixin, BaseModel):
    employee_name: Optional[str] = Field(default=None, max_length=200)
    employee_user_id: Optional[UUID] = None
    employee_code: Optional[str] = Field(default=None, max_length=40)
    joining_date: Optional[date] = None
    designation: Optional[str] = Field(default=None, max_length=120)
    department_name: Optional[str] = Field(default=None, max_length=120)
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    status: Optional[OnboardingChecklistStatus] = None


class OnboardingItemStatusUpdate(BaseModel):
    status: OnboardingItemStatus
    completion_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    reason: Optional[str] = Field(default=None, max_length=1000)
    override: bool = False


class OnboardingItemRequestCreate(BaseModel):
    priority: Literal["low", "normal", "medium", "high", "urgent"] = "normal"
    details: Optional[str] = Field(default=None, max_length=2000)


class OnboardingItemUpdate(BlankOptionalFieldsMixin, BaseModel):
    due_date: Optional[date] = None
    owner_user_id: Optional[UUID] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class OnboardingChecklistItemRead(TimestampSchema):
    checklist_id: UUID
    section: str
    sort_order: int
    item_text: str
    responsibility: str
    responsibility_label: str
    status: str
    status_label: str
    owner_user_id: Optional[UUID] = None
    owner_name: Optional[str] = None
    help_ticket_id: Optional[UUID] = None
    help_ticket_number: Optional[str] = None
    request_status: Optional[str] = None
    request_category: Optional[str] = None
    requires_request: bool = False
    completed_by_id: Optional[UUID] = None
    completed_by_name: Optional[str] = None
    completion_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    completion_type: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[date] = None
    is_overdue: bool = False
    status_reason: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    status_changed_by_name: Optional[str] = None
    validation_rule: Optional[str] = None
    attention: list[str] = Field(default_factory=list)
    can_edit: bool = False
    can_waive: bool = False
    can_create_request: bool = False
    is_mine: bool = False
    execution_type: str = "CHECKLIST_ONLY"
    execution_type_label: str = ""
    mandatory: bool = True
    blocks_completion: bool = True
    evidence_required: bool = False
    reversible: bool = True
    confirm_by: Optional[str] = None
    confirm_by_label: Optional[str] = None
    can_approve: bool = False
    evidence_note: Optional[str] = None
    request_status_label: Optional[str] = None
    request_assignee_name: Optional[str] = None
    request_needs_owner: bool = False
    link_broken: bool = False
    allowed_actions: list[str] = Field(default_factory=list)
    can_repair_link: bool = False


class OnboardingRepairResult(BaseModel):
    actions: list[str] = Field(default_factory=list)
    checklist: "OnboardingChecklistDetailRead"


class OnboardingTemplateItemConfig(BaseModel):
    execution_type: Literal[
        "CHECKLIST_ONLY",
        "TICKET_REQUIRED",
        "APPROVAL_REQUIRED",
        "EXTERNAL_DEPENDENCY",
        "OPTIONAL",
        "AUTOMATED",
    ]
    responsibility: Literal["hr", "admin", "manager", "it", "accounts"]
    owner_role: Optional[str] = Field(default=None, max_length=100)
    priority: Optional[Literal["low", "normal", "high", "urgent"]] = None
    due_offset_days: Optional[int] = Field(default=None, ge=-60, le=180)
    evidence_required: bool = False
    confirm_by: Literal["owner", "hr", "manager", "it"] = "owner"
    reversible: bool = True
    mandatory: bool = True
    blocks_completion: bool = True
    ticket_category: Optional[Literal["it", "facility", "admin", "hr", "other"]] = None
    ticket_subcategory: Optional[str] = Field(default=None, max_length=60)
    completion_rule: Literal["resolved", "closed"] = "resolved"


class OnboardingTemplateItemRead(OnboardingTemplateItemConfig):
    section_index: int
    item_index: int
    section: str
    text: str
    responsibility_label: str
    execution_type_label: str
    validation: Optional[str] = None


class OnboardingTemplateConfigRead(BaseModel):
    id: UUID
    code: str
    name: str
    version: int
    items: list[OnboardingTemplateItemRead] = Field(default_factory=list)
    execution_types: dict[str, str] = Field(default_factory=dict)
    confirm_by: dict[str, str] = Field(default_factory=dict)
    completion_rules: dict[str, str] = Field(default_factory=dict)
    ticket_subcategories: dict[str, dict[str, str]] = Field(default_factory=dict)
    responsibilities: dict[str, str] = Field(default_factory=dict)


class OnboardingItemHistoryEvent(BaseModel):
    at: Optional[datetime] = None
    actor_name: Optional[str] = None
    event: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None
    completion_type: Optional[str] = None
    ticket_number: Optional[str] = None
    source: Optional[str] = None


class OnboardingAttentionRow(BaseModel):
    checklist_id: UUID
    item_id: UUID
    employee_name: Optional[str] = None
    item_text: str
    responsibility: str
    status: str
    due_date: Optional[date] = None
    attention: list[str] = Field(default_factory=list)
    ticket_number: Optional[str] = None


class OnboardingAttentionSummary(BaseModel):
    total_tasks: int = 0
    actionable_total: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    items: list[OnboardingAttentionRow] = Field(default_factory=list)


class OnboardingTriggeredTicket(BaseModel):
    responsibility: str
    responsibility_label: str
    ticket_id: UUID
    ticket_number: str
    category: str
    assignee_id: Optional[UUID] = None
    item_count: int = 0


class OnboardingChecklistRead(TimestampSchema):
    template_id: Optional[UUID] = None
    template_code: Optional[str] = None
    template_name: Optional[str] = None
    employee_user_id: Optional[UUID] = None
    employee_name: str
    employee_code: Optional[str] = None
    joining_date: Optional[date] = None
    designation: Optional[str] = None
    department_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    role_id: Optional[UUID] = None
    role_name: Optional[str] = None
    reporting_manager_id: Optional[UUID] = None
    reporting_manager_name: Optional[str] = None
    status: str
    status_label: str
    notes: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    completed_at: Optional[datetime] = None
    is_published: bool = False
    published_at: Optional[datetime] = None
    published_by_id: Optional[UUID] = None
    total_items: int = 0
    completed_items: int = 0
    resolved_items: int = 0
    pending_items: int = 0
    blocked_items: int = 0
    attention_items: int = 0
    overdue_items: int = 0
    completion_percent: int = 0
    can_manage: bool = False
    my_pending_items: int = 0


class OnboardingChecklistDetailRead(OnboardingChecklistRead):
    items: list[OnboardingChecklistItemRead] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    triggered_tickets: list[OnboardingTriggeredTicket] = Field(default_factory=list)
    # Set only when onboarding auto-created the User (not when linking an existing account).
    provisioned_temporary_password: Optional[str] = None


class OnboardingTemplateRead(BaseModel):
    id: UUID
    code: str
    name: str
    version: int
    is_active: bool


OnboardingRepairResult.model_rebuild()
