"""Engineering Control Tower — persisted risk and data-quality findings.

Additive tables only. A finding row is one *episode* of a condition (the same
pattern as ``StockAlert``): it stays open (``active`` or ``not_assessable``)
while the condition holds, is updated in place by each evaluation, and is
closed (``resolved``) when the condition clears. A later recurrence opens a new
row. ``finding_key`` identifies the condition across episodes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Index, text

from app.db.base import (
    Base,
    Date,
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

FINDING_ACTIVE = "active"
FINDING_NOT_ASSESSABLE = "not_assessable"
FINDING_RESOLVED = "resolved"
OPEN_FINDING_STATUSES = (FINDING_ACTIVE, FINDING_NOT_ASSESSABLE)

RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"


class ProjectRiskEvaluationRun(Base, TimestampMixin, TenantMixin):
    """One Control Tower evaluation pass over all open projects."""

    __tablename__ = "project_risk_evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # running | succeeded | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RUN_RUNNING, index=True)
    # manual | job
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    triggered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    evaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    projects_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_opened: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_resolved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_open: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)


class ProjectRiskFinding(Base, TimestampMixin, TenantMixin):
    """One episode of a rule condition on a project (optionally a milestone)."""

    __tablename__ = "project_risk_findings"
    __table_args__ = (
        # At most one open episode per condition; resolved episodes are history.
        Index(
            "uq_project_risk_findings_open_key",
            "tenant_id",
            "finding_key",
            unique=True,
            sqlite_where=text("status != 'resolved'"),
            postgresql_where=text("status != 'resolved'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # schedule | effort | delivery | data_quality
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # critical | high | medium | info
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # active | not_assessable | resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FINDING_ACTIVE, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON object of raw metric values used by the rule.
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # JSON list of {"label", "value"} evidence lines, display-ready.
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    not_assessable_reason: Mapped[Optional[str]] = mapped_column(Text)
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # milestone_assignee | design_leader
    owner_basis: Mapped[Optional[str]] = mapped_column(String(30))
    first_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_note: Mapped[Optional[str]] = mapped_column(String(300))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledgement_note: Mapped[Optional[str]] = mapped_column(String(500))
    previous_episode_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_risk_findings.id", ondelete="SET NULL"), nullable=True
    )
    detected_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_risk_evaluation_runs.id", ondelete="SET NULL")
    )
    last_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_risk_evaluation_runs.id", ondelete="SET NULL")
    )


class ProjectRiskFindingEvent(Base, TimestampMixin, TenantMixin):
    """Audit history of a finding: opened, changed, resolved, acknowledged."""

    __tablename__ = "project_risk_finding_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_risk_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # opened | reopened | severity_changed | not_assessable | reassessed | resolved | acknowledged
    event: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_risk_evaluation_runs.id", ondelete="SET NULL")
    )
    detail: Mapped[Optional[str]] = mapped_column(Text)
