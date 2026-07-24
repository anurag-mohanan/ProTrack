"""R4 enterprise models — legal entities, document metadata, learning plans."""

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
    Uuid,
    mapped_column,
    relationship,
)
from app.models.mixins import TimestampMixin


class LegalEntity(Base, TimestampMixin):
    """Single-tenant legal entity prep (R4). Not multi-book / multi-tenant."""

    __tablename__ = "legal_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DocumentAsset(Base, TimestampMixin):
    """DMS metadata registry (R4). Storage backend local by default; S3-ready keys."""

    __tablename__ = "document_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128))
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)


class LearningPlan(Base, TimestampMixin):
    """Personal development plan seeded from skill gaps (R4)."""

    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    items: Mapped[list["LearningPlanItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="LearningPlanItem.sort_order",
    )


class LearningPlanItem(Base, TimestampMixin):
    __tablename__ = "learning_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("learning_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stream_skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stream_skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_proficiency: Mapped[Optional[str]] = mapped_column(String(32))
    target_proficiency: Mapped[str] = mapped_column(String(32), nullable=False, default="proficient")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan: Mapped[LearningPlan] = relationship(back_populates="items")
