"""Engineering management assistant (phase 111): conversations, recommendations, audit.

Additive tables only. None of them owns business data: figures shown in a message are
a snapshot of what the tools returned at the time and are never read back as facts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Mapped,
    String,
    Text,
    Uuid,
    mapped_column,
)
from app.models.mixins import TenantMixin, TimestampMixin

MESSAGE_ROLES = ("user", "assistant")
# ok = answered by the provider; data = suggested question answered directly from a tool
# (no provider); offline = provider not configured; error = provider or tool failure.
MESSAGE_STATUSES = ("ok", "data", "offline", "error")

REC_NEW = "new"
REC_ACCEPTED = "accepted"
REC_REJECTED = "rejected"
REC_DEFERRED = "deferred"
REC_COMPLETED = "completed"
REC_STATUSES = (REC_NEW, REC_ACCEPTED, REC_REJECTED, REC_DEFERRED, REC_COMPLETED)
REC_PRIORITIES = ("low", "medium", "high")

TOOL_OK = "ok"
TOOL_DENIED = "denied"
TOOL_INVALID = "invalid"
TOOL_ERROR = "error"


class AIConversation(Base, TimestampMixin, TenantMixin):
    """A conversation is private to its owner. Deleting hides it; rows are kept for audit."""

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[Optional[str]] = mapped_column(String(40))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AIMessage(Base, TimestampMixin, TenantMixin):
    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    error_code: Mapped[Optional[str]] = mapped_column(String(40))
    # JSON lists shown with the answer: source references, tables, limitations, follow-ups.
    sources_json: Mapped[Optional[str]] = mapped_column(Text)
    tables_json: Mapped[Optional[str]] = mapped_column(Text)
    limitations_json: Mapped[Optional[str]] = mapped_column(Text)
    follow_ups_json: Mapped[Optional[str]] = mapped_column(Text)
    # JSON: tool name, status and record count per call (no data payloads).
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text)
    provider: Mapped[Optional[str]] = mapped_column(String(40))
    model: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # up | down
    feedback: Mapped[Optional[str]] = mapped_column(String(10))
    feedback_comment: Mapped[Optional[str]] = mapped_column(Text)
    feedback_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AIRecommendation(Base, TimestampMixin, TenantMixin):
    """A suggestion recorded from a conversation. Never executed automatically."""

    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    module: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON list of source references the recommendation rests on.
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=REC_NEW, index=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AIToolExecution(Base, TimestampMixin, TenantMixin):
    """Data-access audit: one row per tool call, allowed or not. Stores no record contents."""

    __tablename__ = "ai_tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # Validated arguments only (filters such as a project number or date range).
    arguments_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_count: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    detail: Mapped[Optional[str]] = mapped_column(Text)
