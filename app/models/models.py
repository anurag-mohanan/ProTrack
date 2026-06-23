from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    CheckConstraint,
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
from app.models.enums import MilestoneStatus, ProjectStatus, TimesheetStatus
from app.models.mixins import TimestampMixin


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    role: Mapped[Role] = relationship(back_populates="users")
    timesheets: Mapped[list[Timesheet]] = relationship(
        back_populates="user", foreign_keys="Timesheet.user_id"
    )
    timesheets_approved: Mapped[list[Timesheet]] = relationship(
        back_populates="approver", foreign_keys="Timesheet.approved_by"
    )
    design_leader_projects: Mapped[list[Project]] = relationship(
        back_populates="design_leader",
        foreign_keys="Project.design_leader_id",
    )
    designed_projects: Mapped[list[Project]] = relationship(
        back_populates="designer",
        foreign_keys="Project.designer_id",
    )
    surfaced_projects: Mapped[list[Project]] = relationship(
        back_populates="surfacer",
        foreign_keys="Project.surfacer_id",
    )


class Stream(Base, TimestampMixin):
    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    task_types: Mapped[list[TaskType]] = relationship(back_populates="stream")
    projects: Mapped[list[Project]] = relationship(back_populates="stream")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="customer")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customer: Mapped[Customer] = relationship(back_populates="contacts")
    projects: Mapped[list[Project]] = relationship(back_populates="customer_contact")


class TaskType(Base, TimestampMixin):
    __tablename__ = "task_types"
    __table_args__ = (UniqueConstraint("stream_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("streams.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    stream: Mapped[Stream] = relationship(back_populates="task_types")
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="task_type"
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tool_number: Mapped[str] = mapped_column(String(50), nullable=False)
    part_description: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    customer_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    design_leader_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    designer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    surfacer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("streams.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    quoted_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=True),
        nullable=False,
        default=ProjectStatus.not_started,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="projects")
    customer_contact: Mapped[Contact] = relationship(back_populates="projects")
    design_leader: Mapped[User] = relationship(
        back_populates="design_leader_projects", foreign_keys=[design_leader_id]
    )
    designer: Mapped[Optional[User]] = relationship(
        back_populates="designed_projects", foreign_keys=[designer_id]
    )
    surfacer: Mapped[Optional[User]] = relationship(
        back_populates="surfaced_projects", foreign_keys=[surfacer_id]
    )
    stream: Mapped[Stream] = relationship(back_populates="projects")
    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="project"
    )


class Milestone(Base, TimestampMixin):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[MilestoneStatus] = mapped_column(
        Enum(MilestoneStatus, name="milestone_status", native_enum=True),
        nullable=False,
        default=MilestoneStatus.not_started,
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped[Project] = relationship(back_populates="milestones")
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="milestone"
    )


class Timesheet(Base, TimestampMixin):
    __tablename__ = "timesheets"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TimesheetStatus] = mapped_column(
        Enum(TimesheetStatus, name="timesheet_status", native_enum=True),
        nullable=False,
        default=TimesheetStatus.draft,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(
        back_populates="timesheets", foreign_keys=[user_id]
    )
    approver: Mapped[Optional[User]] = relationship(
        back_populates="timesheets_approved", foreign_keys=[approved_by]
    )
    entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="timesheet", cascade="all, delete-orphan"
    )


class TimesheetEntry(Base, TimestampMixin):
    __tablename__ = "timesheet_entries"
    __table_args__ = (
        CheckConstraint("hours > 0 AND hours <= 24", name="ck_timesheet_entry_hours"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timesheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("timesheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    task_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_types.id")
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id")
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    timesheet: Mapped[Timesheet] = relationship(back_populates="entries")
    project: Mapped[Project] = relationship(back_populates="timesheet_entries")
    task_type: Mapped[Optional[TaskType]] = relationship(
        back_populates="timesheet_entries"
    )
    milestone: Mapped[Optional[Milestone]] = relationship(
        back_populates="timesheet_entries"
    )
