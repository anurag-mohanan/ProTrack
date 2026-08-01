"""Employee training courses and assignments (onboarding + ad-hoc)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, UniqueConstraint
from app.models.mixins import TenantMixin, TimestampMixin


class TrainingCourse(Base, TimestampMixin, TenantMixin):
    __tablename__ = "training_courses"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_training_courses_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_department: Mapped[Optional[str]] = mapped_column(String(80))
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    external_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_required_for_onboarding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    assignments: Mapped[list["TrainingAssignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class TrainingAssignment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "training_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("training_courses.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    assigned_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    onboarding_checklist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("onboarding_checklists.id"), nullable=True
    )

    course: Mapped[TrainingCourse] = relationship(back_populates="assignments")
