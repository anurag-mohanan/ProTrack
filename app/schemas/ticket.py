"""Help-desk / ticketing API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema

TicketCategory = Literal["it", "facility", "admin", "hr", "other"]
TicketPriority = Literal["low", "normal", "medium", "high", "urgent"]
TicketStatus = Literal[
    "new",
    "open",
    "in_progress",
    "pending_requester",
    "pending_internal",
    "pending_vendor",
    "on_hold",
    "resolved",
    "closed",
    "cancelled",
]


class TicketCreate(BlankOptionalFieldsMixin, BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    category: TicketCategory
    subcategory: Optional[str] = Field(default=None, max_length=60)
    priority: TicketPriority = "normal"
    location: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date] = None
    org_department_id: Optional[UUID] = None
    affected_user_id: Optional[UUID] = None
    related_asset_id: Optional[UUID] = None
    related_license_pool_id: Optional[UUID] = None


class TicketUpdate(BlankOptionalFieldsMixin, BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    category: Optional[TicketCategory] = None
    subcategory: Optional[str] = Field(default=None, max_length=60)
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assignee_id: Optional[UUID] = None
    location: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date] = None
    resolution: Optional[str] = None
    work_performed: Optional[str] = None
    reason: Optional[str] = None
    org_department_id: Optional[UUID] = None


class TicketAssignRequest(BaseModel):
    assignee_id: Optional[UUID] = None
    reason: Optional[str] = None


class TicketTransferRequest(BaseModel):
    category: TicketCategory
    subcategory: Optional[str] = Field(default=None, max_length=60)
    assignee_id: Optional[UUID] = None
    reason: str = Field(min_length=1)


class TicketStatusRequest(BaseModel):
    status: TicketStatus
    resolution: Optional[str] = None
    work_performed: Optional[str] = None
    resolution_category: Optional[str] = None
    closure_reason: Optional[str] = None
    reason: Optional[str] = None


class TicketReviewRequest(BaseModel):
    note: str = Field(min_length=1)


class TicketCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    is_internal: bool = False


class TicketCommentRead(TimestampSchema):
    ticket_id: UUID
    author_id: UUID
    author_name: Optional[str] = None
    body: str
    is_internal: bool


class TicketRead(TimestampSchema):
    ticket_number: str
    title: str
    description: Optional[str] = None
    category: str
    category_label: str
    subcategory: Optional[str] = None
    subcategory_label: Optional[str] = None
    family: Optional[str] = None
    priority: str
    priority_label: str = ""
    status: str
    status_label: str
    requester_id: UUID
    requester_name: Optional[str] = None
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    affected_user_id: Optional[UUID] = None
    affected_user_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    location: Optional[str] = None
    due_date: Optional[date] = None
    sla_due_at: Optional[datetime] = None
    is_overdue: bool = False
    resolution: Optional[str] = None
    work_performed: Optional[str] = None
    resolution_category: Optional[str] = None
    closure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    pending_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    source_module: Optional[str] = None
    source_label: Optional[str] = None
    source_record_id: Optional[str] = None
    onboarding_item_id: Optional[UUID] = None
    related_asset_id: Optional[UUID] = None
    related_license_pool_id: Optional[UUID] = None
    related_stock_item_id: Optional[UUID] = None
    assignment_group: Optional[str] = None
    needs_owner: bool = False
    needs_review: bool = False
    review_note: Optional[str] = None
    escalation_level: int = 0
    comment_count: int = 0
    can_manage: bool = False
    allowed_transitions: list[str] = Field(default_factory=list)


class TicketTimelineEvent(BaseModel):
    at: Optional[datetime] = None
    kind: str
    actor_name: Optional[str] = None
    summary: str
    detail: Optional[str] = None
    is_internal: bool = False


class TicketAssignmentRead(BaseModel):
    at: Optional[datetime] = None
    previous_assignee_name: Optional[str] = None
    new_assignee_name: Optional[str] = None
    previous_group: Optional[str] = None
    new_group: Optional[str] = None
    changed_by_name: Optional[str] = None
    change_type: str
    reason: Optional[str] = None


class TicketLinkedTask(BaseModel):
    checklist_id: UUID
    item_id: UUID
    employee_name: Optional[str] = None
    item_text: str
    status: str
    status_label: str
    execution_type: str


class TicketRelatedRecord(BaseModel):
    kind: str
    id: str
    label: str
    href: Optional[str] = None


class TicketNotificationRead(BaseModel):
    at: Optional[datetime] = None
    event_key: str
    user_name: Optional[str] = None
    status: str
    error: Optional[str] = None
    attempts: int = 1


class TicketDetailRead(TicketRead):
    comments: list[TicketCommentRead] = Field(default_factory=list)
    timeline: list[TicketTimelineEvent] = Field(default_factory=list)
    assignment_history: list[TicketAssignmentRead] = Field(default_factory=list)
    linked_tasks: list[TicketLinkedTask] = Field(default_factory=list)
    related_records: list[TicketRelatedRecord] = Field(default_factory=list)
    notifications: list[TicketNotificationRead] = Field(default_factory=list)
    can_comment_internal: bool = False
    provisioning_request_id: Optional[UUID] = None


class TicketPage(BaseModel):
    items: list[TicketRead]
    total: int
    page: int
    page_size: int


class TicketQueueSummary(BaseModel):
    category: Optional[str] = None
    counts: dict[str, int]


class TicketCapabilities(BaseModel):
    is_agent: bool
    can_manage_all: bool
    can_configure: bool
    manageable_categories: list[str]


class TicketCatalog(BaseModel):
    categories: dict[str, str]
    subcategories: dict[str, dict[str, str]]
    families: dict[str, str]
    statuses: dict[str, str]
    status_order: list[str]
    priorities: dict[str, str]
    sources: dict[str, str]
    closure_reasons: dict[str, str]
    resolution_categories: dict[str, str]
    transitions: dict[str, list[str]]


class TicketAssignee(BaseModel):
    id: UUID
    name: str
    role_name: Optional[str] = None


class TicketCategoryRouteRead(BaseModel):
    category: str
    category_label: str
    assignee_user_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    backup_user_id: Optional[UUID] = None
    backup_name: Optional[str] = None
    escalation_user_id: Optional[UUID] = None
    escalation_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    is_active: bool = True
    effective_from: Optional[date] = None
    fallback_roles: list[str] = Field(default_factory=list)


class TicketCategoryRouteUpdate(BaseModel):
    assignee_user_id: Optional[UUID] = None
    backup_user_id: Optional[UUID] = None
    escalation_user_id: Optional[UUID] = None
    org_department_id: Optional[UUID] = None
    is_active: bool = True
    effective_from: Optional[date] = None


class TicketRoutingRuleWrite(BaseModel):
    category: TicketCategory
    subcategory: Optional[str] = Field(default=None, max_length=60)
    source_module: Optional[str] = Field(default=None, max_length=40)
    primary_user_id: Optional[UUID] = None
    backup_user_id: Optional[UUID] = None
    escalation_user_id: Optional[UUID] = None
    default_priority: Optional[TicketPriority] = None
    is_active: bool = True
    effective_from: Optional[date] = None
    notes: Optional[str] = None


class TicketRoutingRuleRead(TicketRoutingRuleWrite):
    id: UUID
    primary_name: Optional[str] = None
    backup_name: Optional[str] = None
    escalation_name: Optional[str] = None


class TicketSlaPolicyWrite(BaseModel):
    category: str = "*"
    priority: Literal["low", "normal", "high", "urgent"]
    response_hours: Optional[int] = Field(default=None, ge=0)
    resolution_hours: Optional[int] = Field(default=None, ge=0)
    due_soon_hours: int = Field(default=24, ge=0)
    escalate_after_hours: Optional[int] = Field(default=None, ge=0)
    is_active: bool = True


class TicketSlaPolicyRead(TicketSlaPolicyWrite):
    id: UUID


class TicketStats(BaseModel):
    total: int = 0
    new: int = 0
    open: int = 0
    in_progress: int = 0
    pending: int = 0
    on_hold: int = 0
    resolved: int = 0
    closed: int = 0
    cancelled: int = 0
    active: int = 0
    assigned_to_me: int = 0
    raised_by_me: int = 0


class TicketReport(BaseModel):
    filters: dict[str, Any]
    totals: dict[str, Any]
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_family: dict[str, int]
    by_subcategory: dict[str, int]
    by_source: dict[str, int]
    by_assignee: list[dict[str, Any]]


class TicketReconciliation(BaseModel):
    counts: dict[str, int]
    rows: list[dict[str, Any]]


class EmployeeTicketRow(BaseModel):
    id: UUID
    ticket_number: str
    title: str
    category_label: str
    status: str
    status_label: str
    priority_label: str
    assignee_name: Optional[str] = None
    due_date: Optional[date] = None
    is_overdue: bool = False
    updated_at: Optional[datetime] = None
    relation: str
    can_open: bool = False
