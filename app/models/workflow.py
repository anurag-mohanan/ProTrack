"""Template reconciliation history and workflow automation (phase 110).

Additive tables only. Reconciliation rows are the decision record of a template
change; automation rows are rule configuration and an append-only execution log.
Neither table owns business data: milestones, notifications and findings stay in
their existing tables and are only referenced here.
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
    UniqueConstraint,
    Uuid,
    mapped_column,
)
from app.models.mixins import TenantMixin, TimestampMixin

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_MERGED = "merged"
LIFECYCLE_SUPERSEDED = "superseded"
LIFECYCLE_ARCHIVED = "archived"
LIFECYCLE_STATES = (LIFECYCLE_ACTIVE, LIFECYCLE_MERGED, LIFECYCLE_SUPERSEDED, LIFECYCLE_ARCHIVED)

RECON_APPLIED = "applied"
RECON_FAILED = "failed"

EXEC_SUCCEEDED = "succeeded"
EXEC_FAILED = "failed"
EXEC_SKIPPED = "skipped"
EXEC_PENDING_REVIEW = "pending_review"
EXEC_DISMISSED = "dismissed"
EXEC_STATUSES = (EXEC_SUCCEEDED, EXEC_FAILED, EXEC_SKIPPED, EXEC_PENDING_REVIEW, EXEC_DISMISSED)


class ProjectTemplateReconciliation(Base, TimestampMixin, TenantMixin):
    """One confirmed (or failed) template change on a project."""

    __tablename__ = "project_template_reconciliations"
    __table_args__ = (
        UniqueConstraint("project_id", "request_key", name="uq_project_template_reconciliation_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Client-supplied idempotency key: a repeated submit returns the first result.
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    previous_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_templates.id"), nullable=True
    )
    previous_template_name: Mapped[Optional[str]] = mapped_column(String(200))
    previous_template_version: Mapped[Optional[int]] = mapped_column(Integer)
    new_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_templates.id"), nullable=False
    )
    new_template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    new_template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retained_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    superseded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Full decision record: milestone ids per action, merge pairs, dependency changes,
    # warnings and the confirmation text. JSON.
    decisions_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    confirmed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AutomationRule(Base, TimestampMixin, TenantMixin):
    """Persisted switch and run state for a rule defined in code (app.services.automation)."""

    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_status: Mapped[Optional[str]] = mapped_column(String(20))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class AutomationExecution(Base, TimestampMixin, TenantMixin):
    """One rule evaluation for one target. ``dedupe_key`` makes repeats and retries idempotent."""

    __tablename__ = "automation_executions"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_automation_executions_dedupe_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(80), nullable=False)
    # system | user
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False, default="system")
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    # JSON: what was done (notification ids, recipients, linked finding, recommendation).
    result_json: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
