"""Phase 8 intelligence models — decisions, engineering changes."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.db.base import (
    Base,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    Uuid,
    mapped_column,
    relationship,
)
from app.models.enums import DecisionCategory, EngineeringChangeStatus
from app.models.mixins import TenantMixin, TimestampMixin


class ProjectDecision(Base, TimestampMixin, TenantMixin):
    __tablename__ = "project_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    category: Mapped[DecisionCategory] = mapped_column(
        Enum(DecisionCategory, name="decision_category", native_enum=False),
        nullable=False,
        default=DecisionCategory.general,
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped["Project"] = relationship(back_populates="decisions")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    milestone: Mapped[Optional["Milestone"]] = relationship(foreign_keys=[milestone_id])


class EngineeringChange(Base, TimestampMixin, TenantMixin):
    __tablename__ = "engineering_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    ec_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[EngineeringChangeStatus] = mapped_column(
        Enum(EngineeringChangeStatus, name="engineering_change_status", native_enum=False),
        nullable=False,
        default=EngineeringChangeStatus.open,
    )
    hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="engineering_changes")


class LessonLearned(Base, TimestampMixin, TenantMixin):
    __tablename__ = "lessons_learned"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    what_went_well: Mapped[Optional[str]] = mapped_column(Text)
    problems_encountered: Mapped[Optional[str]] = mapped_column(Text)
    recommendations: Mapped[Optional[str]] = mapped_column(Text)
    hours_observations: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped["Project"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])


class ProjectKnowledgeRecord(Base, TimestampMixin, TenantMixin):
    """Searchable knowledge index for completed projects."""

    __tablename__ = "project_knowledge_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tool_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    project_type_name: Mapped[Optional[str]] = mapped_column(String(255))
    designer_name: Mapped[Optional[str]] = mapped_column(String(255))
    surfacer_name: Mapped[Optional[str]] = mapped_column(String(255))
    quoted_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    actual_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    milestone_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engineering_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mechanism: Mapped[Optional[str]] = mapped_column(String(255))
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()
