"""Phase 7 foundation models — company settings, org structure, skills."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    Date,
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
from app.models.enums import DueDateCalculationMode, SkillLevel
from app.models.mixins import TimestampMixin


class CompanySettings(Base, TimestampMixin):
    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Prosohm")
    company_short_name: Mapped[Optional[str]] = mapped_column(String(80))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    gst_number: Mapped[Optional[str]] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    financial_year_start_month: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    default_working_hours_per_day: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("8")
    )
    default_working_days: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Mon,Tue,Wed,Thu,Fri"
    )


class BrandingSettings(Base, TimestampMixin):
    __tablename__ = "branding_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    theme_preset: Mapped[str] = mapped_column(
        String(64), nullable=False, default="prosohm_professional"
    )
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#0066B3")
    secondary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1E293B")
    accent_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#0EA5E9")
    success_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#16A34A")
    warning_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#D97706")
    danger_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#DC2626")
    sidebar_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#0F172A")
    header_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#FFFFFF")
    button_style: Mapped[str] = mapped_column(String(20), nullable=False, default="rounded")
    border_radius: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    card_style: Mapped[str] = mapped_column(String(20), nullable=False, default="elevated")
    density: Mapped[str] = mapped_column(String(20), nullable=False, default="default")


class UserPreferences(Base, TimestampMixin):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    theme_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="company_default"
    )
    sidebar_expanded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sidebar_auto_collapse: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dashboard_layout: Mapped[str] = mapped_column(String(20), nullable=False, default="default")
    table_density: Mapped[str] = mapped_column(String(20), nullable=False, default="comfortable")
    font_size: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    animations_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_landing_page: Mapped[str] = mapped_column(
        String(32), nullable=False, default="dashboard"
    )

    user: Mapped["User"] = relationship(back_populates="preferences")


class Holiday(Base, TimestampMixin):
    __tablename__ = "holidays"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(100))
    is_working_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list["User"]] = relationship(back_populates="department")


class ContactType(Base, TimestampMixin):
    __tablename__ = "contact_types"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="contact_type")


class EngineeringDiscipline(Base, TimestampMixin):
    __tablename__ = "engineering_disciplines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user_skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )


class UserSkill(Base, TimestampMixin):
    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    proficiency: Mapped[SkillLevel] = mapped_column(
        Enum(SkillLevel, name="skill_level", native_enum=False),
        nullable=False,
        default=SkillLevel.intermediate,
    )

    user: Mapped["User"] = relationship(back_populates="user_skills")
    skill: Mapped[Skill] = relationship(back_populates="user_skills")


class FilePathSettings(Base, TimestampMixin):
    __tablename__ = "file_path_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_root_folder: Mapped[Optional[str]] = mapped_column(String(500))
    customer_folder_template: Mapped[Optional[str]] = mapped_column(String(500))
    drawing_folder_template: Mapped[Optional[str]] = mapped_column(String(500))
    design_folder_template: Mapped[Optional[str]] = mapped_column(String(500))
    backup_folder: Mapped[Optional[str]] = mapped_column(String(500))


class NotificationSettings(Base, TimestampMixin):
    __tablename__ = "notification_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    projects_due_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overdue_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pending_approvals_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    new_assignments_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imports_completed_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
