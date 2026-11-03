"""Strategic management (phase 113): objectives, measurements, initiatives, reviews, actions, events.

Additive tables only. None of them owns business data: actual figures are read from the Finance,
delivery, timesheet, capacity and skills services and are never written here except as dated
snapshots (automatic measurements, review snapshots). Manual measurements are appended, never
edited, and only for objectives measured manually. Every change to a target, baseline, status or
decision is appended to ``management_events`` with the person who made or approved it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Index

from app.db.base import (
    Base,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    Uuid,
    mapped_column,
)
from app.models.mixins import TenantMixin, TimestampMixin

OBJECTIVE_STATUSES = ("not_started", "on_track", "at_risk", "delayed", "completed", "cancelled")
OBJECTIVE_PERIODS = ("annual", "quarterly", "monthly")
OBJECTIVE_CATEGORIES = ("financial", "delivery", "efficiency", "customer", "workforce", "quality", "growth", "other")
MEASURE_AUTOMATIC = "automatic"
MEASURE_MANUAL = "manual"
DIRECTION_INCREASE = "increase"
DIRECTION_DECREASE = "decrease"

INITIATIVE_STATUSES = ("planned", "in_progress", "on_hold", "at_risk", "completed", "cancelled")
PRIORITIES = ("low", "medium", "high", "critical")

REVIEW_TYPES = ("monthly", "quarterly", "annual")
REVIEW_DRAFT = "draft"
REVIEW_FINAL = "final"

ACTION_STATUSES = ("open", "in_progress", "blocked", "completed", "cancelled")
ACTION_CLOSED = ("completed", "cancelled")

EVENT_ENTITY_TYPES = ("objective", "initiative", "review", "action")


class StrategicObjective(Base, TimestampMixin, TenantMixin):
    __tablename__ = "strategic_objectives"
    __table_args__ = (Index("ix_strategic_objectives_fy", "fy_start_year", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    fy_start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")
    # Quarter (1-4) or month (1-12) of the financial year; empty for annual objectives.
    period_index: Mapped[Optional[int]] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default=DIRECTION_INCREASE)
    measurement: Mapped[str] = mapped_column(String(20), nullable=False, default=MEASURE_MANUAL)
    # Automatic objectives: key in the management KPI registry and its JSON parameters.
    metric_key: Mapped[Optional[str]] = mapped_column(String(60))
    metric_params_json: Mapped[Optional[str]] = mapped_column(Text)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    baseline_note: Mapped[Optional[str]] = mapped_column(String(500))
    # Targets set by someone without approval rights stay proposed until approved.
    target_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    target_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    supporting_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("teams.id"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    related_kpis_json: Mapped[Optional[str]] = mapped_column(Text)
    related_project_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class ObjectiveMeasurement(Base, TenantMixin):
    """A dated value for an objective. Rows are appended; corrections add a new row."""

    __tablename__ = "objective_measurements"
    __table_args__ = (Index("ix_objective_measurements_objective", "objective_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    objective_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("strategic_objectives.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    # automatic (snapshot of the calculated actual) | manual (entered with evidence)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_detail: Mapped[Optional[str]] = mapped_column(String(300))
    note: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("objective_measurements.id"))
    recorded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class StrategicInitiative(Base, TimestampMixin, TenantMixin):
    __tablename__ = "strategic_initiatives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("strategic_objectives.id", ondelete="SET NULL"), index=True
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # Reported by the owner; not derived from any project figure.
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # JSON list of {"title", "due_date", "done"}.
    milestones_json: Mapped[Optional[str]] = mapped_column(Text)
    dependencies: Mapped[Optional[str]] = mapped_column(Text)
    risks: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Existing projects delivering the initiative (references only; projects are not duplicated).
    related_project_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class ManagementReview(Base, TimestampMixin, TenantMixin):
    """A management review: generated figures (snapshot) plus human summary, decisions and actions."""

    __tablename__ = "management_reviews"
    __table_args__ = (Index("ix_management_reviews_period", "review_type", "period_start"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    fy_start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_index: Mapped[Optional[int]] = mapped_column(Integer)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=REVIEW_DRAFT)
    filters_json: Mapped[Optional[str]] = mapped_column(Text)
    # Generated sections as calculated at generated_at; replaced only while the review is a draft.
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    generated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    # Written or confirmed by a person; required before the review is finalised.
    executive_summary: Mapped[Optional[str]] = mapped_column(Text)
    # AI draft kept separately and labelled; never official on its own.
    ai_summary_draft: Mapped[Optional[str]] = mapped_column(Text)
    finalised_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finalised_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    previous_review_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("management_reviews.id"))
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class ManagementAction(Base, TimestampMixin, TenantMixin):
    __tablename__ = "management_actions"
    __table_args__ = (Index("ix_management_actions_status", "status", "due_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("management_reviews.id", ondelete="SET NULL"), index=True
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("strategic_objectives.id", ondelete="SET NULL"), index=True
    )
    initiative_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("strategic_initiatives.id", ondelete="SET NULL")
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    # The review decision this action implements, when it came from one.
    decision_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("management_events.id"))
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    completion_evidence: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class ManagementEvent(Base, TenantMixin):
    """Append-only history: comments, decisions, status/target/baseline changes and approvals."""

    __tablename__ = "management_events"
    __table_args__ = (Index("ix_management_events_entity", "entity_type", "entity_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # created | updated | status_changed | target_changed | baseline_changed | target_approved |
    # measurement_recorded | comment | decision | generated | finalised | completed
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    old_value_json: Mapped[Optional[str]] = mapped_column(Text)
    new_value_json: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    # Person with approval rights who authorised a target or baseline change.
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
