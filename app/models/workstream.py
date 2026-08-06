"""Workstream layer for Projects Command Center (distinct from Stream business line)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Index

from app.db.base import (
    Base,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    mapped_column,
    relationship,
)
from app.models.enums import ExecutionStatus, ProjectHealth, ProjectPriority
from app.models.mixins import TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.models import Project, Team, User


class Workstream(Base, TimestampMixin, TenantMixin):
    """Configurable delivery workstream (portfolio taxonomy — not business-line Stream)."""

    __tablename__ = "workstreams"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_workstreams_tenant_name"),
        UniqueConstraint("tenant_id", "code", name="uq_workstreams_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project_links: Mapped[list["ProjectWorkstream"]] = relationship(
        back_populates="workstream", cascade="all, delete-orphan"
    )


class ProjectWorkstream(Base, TimestampMixin, TenantMixin):
    """Project ↔ Workstream assignment with optional ownership and hours."""

    __tablename__ = "project_workstreams"
    __table_args__ = (
        UniqueConstraint("project_id", "workstream_id", name="uq_project_workstream"),
        Index("ix_project_workstreams_tenant_workstream", "tenant_id", "workstream_id"),
        Index("ix_project_workstreams_project", "project_id"),
        Index("ix_project_workstreams_team", "team_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workstreams.id", ondelete="RESTRICT"),
        nullable=False,
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[Optional[ExecutionStatus]] = mapped_column(
        Enum(ExecutionStatus, name="project_workstream_status", native_enum=False),
        nullable=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    progress_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    health: Mapped[Optional[ProjectHealth]] = mapped_column(
        Enum(ProjectHealth, name="project_workstream_health", native_enum=False),
        nullable=True,
    )
    priority: Mapped[Optional[ProjectPriority]] = mapped_column(
        Enum(ProjectPriority, name="project_workstream_priority", native_enum=False),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="workstream_links")
    workstream: Mapped[Workstream] = relationship(back_populates="project_links")
    team: Mapped[Optional["Team"]] = relationship(foreign_keys=[team_id])
    lead: Mapped[Optional["User"]] = relationship(foreign_keys=[lead_id])


class ProjectSavedView(Base, TimestampMixin, TenantMixin):
    """Named filter/display snapshot for the Projects Command Center."""

    __tablename__ = "project_saved_views"
    __table_args__ = (
        Index("ix_project_saved_views_user", "user_id"),
        UniqueConstraint(
            "tenant_id", "user_id", "name", name="uq_project_saved_views_user_name"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    display_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
