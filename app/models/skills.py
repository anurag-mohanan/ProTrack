"""Engineering skills graph — relationship, history and planning tables (phase 109).

Additive tables only. The skill master is ``skills`` and the employee-skill
record is ``user_skills`` (``app.models.foundation``); these tables hang off
them. Nothing here is derived automatically from projects or timesheets.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Mapped,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    mapped_column,
    relationship,
)
from app.models.mixins import TenantMixin, TimestampMixin

STATUS_SELF_DECLARED = "self_declared"
STATUS_PENDING = "pending_verification"
STATUS_VERIFIED = "verified"
STATUS_REJECTED = "rejected"
STATUS_NEEDS_REASSESSMENT = "needs_reassessment"
STATUS_ARCHIVED = "archived"
SKILL_STATUSES = (
    STATUS_SELF_DECLARED,
    STATUS_PENDING,
    STATUS_VERIFIED,
    STATUS_REJECTED,
    STATUS_NEEDS_REASSESSMENT,
    STATUS_ARCHIVED,
)

ORIGIN_SELF = "self"
ORIGIN_MANAGER = "manager"
ORIGIN_LEGACY = "legacy"

PLAN_PLANNED = "planned"
PLAN_IN_PROGRESS = "in_progress"
PLAN_COMPLETED = "completed"
PLAN_CANCELLED = "cancelled"
PLAN_STATUSES = (PLAN_PLANNED, PLAN_IN_PROGRESS, PLAN_COMPLETED, PLAN_CANCELLED)
OPEN_PLAN_STATUSES = (PLAN_PLANNED, PLAN_IN_PROGRESS)


class SkillProficiencyLevel(Base, TimestampMixin, TenantMixin):
    """Configurable labels and descriptions for proficiency levels 1–5."""

    __tablename__ = "skill_proficiency_levels"
    __table_args__ = (UniqueConstraint("tenant_id", "level", name="uq_skill_proficiency_levels_tenant_level"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class SkillRelationship(Base, TimestampMixin, TenantMixin):
    __tablename__ = "skill_relationships"
    __table_args__ = (
        UniqueConstraint("from_skill_id", "to_skill_id", "relation_type", name="uq_skill_relationship"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class UserSkillEvent(Base, TenantMixin):
    """Append-only history of an employee-skill record."""

    __tablename__ = "user_skill_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[Optional[str]] = mapped_column(String(30))
    from_declared_level: Mapped[Optional[int]] = mapped_column(Integer)
    to_declared_level: Mapped[Optional[int]] = mapped_column(Integer)
    from_verified_level: Mapped[Optional[int]] = mapped_column(Integer)
    to_verified_level: Mapped[Optional[int]] = mapped_column(Integer)
    verification_method: Mapped[Optional[str]] = mapped_column(String(30))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    confidential_note: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserSkillEvidence(Base, TimestampMixin, TenantMixin):
    """A project cited as supporting evidence for an employee-skill record."""

    __tablename__ = "user_skill_evidence"
    __table_args__ = (UniqueConstraint("user_skill_id", "project_id", name="uq_user_skill_evidence_project"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text)
    added_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class ProjectSkillRequirement(Base, TimestampMixin, TenantMixin):
    __tablename__ = "project_skill_requirements"
    __table_args__ = (UniqueConstraint("project_id", "skill_id", name="uq_project_skill_requirement"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id"), nullable=False, index=True
    )
    min_level: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    skill = relationship("Skill")


class SkillDevelopmentPlan(Base, TimestampMixin, TenantMixin):
    """Development objective for one employee and skill. Completing a plan never changes proficiency."""

    __tablename__ = "skill_development_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id"), nullable=False, index=True
    )
    baseline_verified_level: Mapped[Optional[int]] = mapped_column(Integer)
    target_level: Mapped[int] = mapped_column(Integer, nullable=False)
    objective: Mapped[Optional[str]] = mapped_column(Text)
    training_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    training_requirement: Mapped[Optional[str]] = mapped_column(Text)
    is_knowledge_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mentor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    target_review_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PLAN_PLANNED)
    progress_note: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
