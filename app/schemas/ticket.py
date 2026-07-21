"""Help-desk / ticketing API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema

TicketCategory = Literal["it", "facility", "admin", "hr", "other"]
TicketPriority = Literal["low", "medium", "high", "urgent"]
TicketStatus = Literal[
    "open", "in_progress", "on_hold", "resolved", "closed", "cancelled"
]


class TicketCreate(BlankOptionalFieldsMixin, BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    category: TicketCategory
    priority: TicketPriority = "medium"
    location: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date] = None
    org_department_id: Optional[UUID] = None


class TicketUpdate(BlankOptionalFieldsMixin, BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    category: Optional[TicketCategory] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assignee_id: Optional[UUID] = None
    location: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date] = None
    resolution: Optional[str] = None
    org_department_id: Optional[UUID] = None


class TicketAssignRequest(BaseModel):
    assignee_id: Optional[UUID] = None


class TicketStatusRequest(BaseModel):
    status: TicketStatus
    resolution: Optional[str] = None


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
    priority: str
    status: str
    status_label: str
    requester_id: UUID
    requester_name: Optional[str] = None
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    org_department_id: Optional[UUID] = None
    location: Optional[str] = None
    due_date: Optional[date] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    comment_count: int = 0
    can_manage: bool = False


class TicketDetailRead(TicketRead):
    comments: list[TicketCommentRead] = Field(default_factory=list)


class TicketStats(BaseModel):
    total: int = 0
    open: int = 0
    in_progress: int = 0
    on_hold: int = 0
    resolved: int = 0
    closed: int = 0
    cancelled: int = 0
    assigned_to_me: int = 0
    raised_by_me: int = 0
