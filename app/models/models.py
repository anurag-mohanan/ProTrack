from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

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
from app.models.enums import (
    ActivityAction,
    DashboardProfile,
    DueDateCalculationMode,
    EmploymentType,
    EntityType,
    ExecutionStatus,
    MilestoneStatus,
    NonProductiveCodeCategory,
    NotificationType,
    ProjectHealth,
    ProjectComplexity,
    ProjectPriority,
    ProjectStage,
    SkillLevel,
    TaskTypeFunctionCategory,
    TeamRelationshipType,
    TimesheetStatus,
    UserAvailabilityStatus,
    WorkCategory,
    ContributionReason,
    WorkingModelCode,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.foundation import Department, UserPreferences


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    users: Mapped[list[User]] = relationship(back_populates="role")


class OperationalRoleType(Base, TimestampMixin):
    """Configurable operational role classification for KPI participation."""

    __tablename__ = "operational_role_types"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dashboard_profile: Mapped[DashboardProfile] = mapped_column(
        Enum(DashboardProfile, name="dashboard_profile", native_enum=False),
        nullable=False,
        default=DashboardProfile.engineering,
    )
    default_kpi_engineering_productivity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    default_kpi_capacity_planning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    default_kpi_utilization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    default_kpi_workload_planning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    default_kpi_dashboard_productivity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    users: Mapped[list["User"]] = relationship(back_populates="operational_role_type")


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
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    designation: Mapped[Optional[str]] = mapped_column(String(100))
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    working_hours_per_day: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("8")
    )
    working_days: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Mon,Tue,Wed,Thu,Fri"
    )
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        Enum(EmploymentType, name="employment_type", native_enum=False),
        nullable=True,
    )
    skill_level: Mapped[Optional[SkillLevel]] = mapped_column(
        Enum(SkillLevel, name="user_skill_level", native_enum=False),
        nullable=True,
    )
    joining_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    leaving_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    availability_status: Mapped[UserAvailabilityStatus] = mapped_column(
        Enum(UserAvailabilityStatus, name="user_availability_status", native_enum=False),
        nullable=False,
        default=UserAvailabilityStatus.available,
    )
    max_allocation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    operational_role_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("operational_role_types.id"), nullable=True
    )
    kpi_engineering_productivity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    kpi_capacity_planning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    kpi_utilization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    kpi_workload_planning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    kpi_dashboard_productivity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    requires_timesheet: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    requires_salary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    default_working_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=True
    )
    module_access: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    special_permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role: Mapped[Role] = relationship(back_populates="users")
    operational_role_type: Mapped[Optional[OperationalRoleType]] = relationship(
        back_populates="users"
    )
    default_working_model: Mapped[Optional["WorkingModel"]] = relationship(
        foreign_keys=[default_working_model_id]
    )
    manager: Mapped[Optional["User"]] = relationship(
        remote_side="User.id",
        foreign_keys=[manager_id],
    )
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    department: Mapped[Optional["Department"]] = relationship(
        back_populates="users", foreign_keys=[department_id]
    )
    team: Mapped[Optional["Team"]] = relationship(
        foreign_keys=[team_id],
        back_populates="assigned_users",
    )
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
    activities: Mapped[list[Activity]] = relationship(back_populates="user")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")
    team_memberships: Mapped[list[TeamMember]] = relationship(
        back_populates="user", foreign_keys="TeamMember.user_id"
    )
    performance_reviews: Mapped[list["PerformanceReviewSheet"]] = relationship(
        back_populates="employee",
        foreign_keys="PerformanceReviewSheet.employee_id",
    )
    performance_reviews_authored: Mapped[list["PerformanceReviewSheet"]] = relationship(
        back_populates="reviewer",
        foreign_keys="PerformanceReviewSheet.reviewer_id",
    )
    performance_review_cycles_created: Mapped[list["PerformanceReviewCycle"]] = relationship(
        back_populates="created_by",
        foreign_keys="PerformanceReviewCycle.created_by_id",
    )
    user_skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WorkingModel(Base, TimestampMixin):
    __tablename__ = "working_models"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    strategy_key: Mapped[WorkingModelCode] = mapped_column(
        Enum(WorkingModelCode, name="working_model_code", native_enum=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customers: Mapped[list["Customer"]] = relationship(
        back_populates="default_working_model",
        foreign_keys="Customer.default_working_model_id",
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="default_working_model",
        foreign_keys="User.default_working_model_id",
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="working_model")


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


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    team_lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    colour: Mapped[str] = mapped_column(String(20), nullable=False, default="#1976d2")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Future: offices, business units, companies (Part 12)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    team_lead: Mapped[Optional[User]] = relationship(
        foreign_keys=[team_lead_id]
    )
    assigned_users: Mapped[list[User]] = relationship(
        back_populates="team",
        foreign_keys="User.team_id",
    )
    members: Mapped[list[TeamMember]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="team")


class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_within_team: Mapped[Optional[str]] = mapped_column(String(100))
    relationship_type: Mapped[TeamRelationshipType] = mapped_column(
        Enum(TeamRelationshipType, name="team_relationship_type", native_enum=False),
        nullable=False,
        default=TeamRelationshipType.member,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_billable_headcount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_in_timesheet_reports: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class TeamMembershipPeriod(Base, TimestampMixin):
    """Primary-home history for finance — day-prorated salary by team."""

    __tablename__ = "team_membership_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_billable_headcount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    role_within_team: Mapped[Optional[str]] = mapped_column(String(100))
    relationship_type: Mapped[TeamRelationshipType] = mapped_column(
        Enum(TeamRelationshipType, name="team_relationship_type", native_enum=False),
        nullable=False,
        default=TeamRelationshipType.member,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(255))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    team: Mapped[Team] = relationship(foreign_keys=[team_id])


class PerformanceReviewCycle(Base, TimestampMixin):
    __tablename__ = "performance_review_cycles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    review_year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[Optional[User]] = relationship(
        back_populates="performance_review_cycles_created",
        foreign_keys=[created_by_id],
    )
    sheets: Mapped[list["PerformanceReviewSheet"]] = relationship(
        back_populates="cycle", cascade="all, delete-orphan"
    )


class PerformanceReviewSheet(Base, TimestampMixin):
    __tablename__ = "performance_review_sheets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cycle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("performance_review_cycles.id"), nullable=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True
    )
    period_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    overall_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    employee_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strengths_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    career_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_experience: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    review_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    cycle: Mapped[Optional[PerformanceReviewCycle]] = relationship(back_populates="sheets")
    employee: Mapped[User] = relationship(
        back_populates="performance_reviews",
        foreign_keys=[employee_id],
    )
    reviewer: Mapped[User] = relationship(
        back_populates="performance_reviews_authored",
        foreign_keys=[reviewer_id],
    )
    team: Mapped[Optional[Team]] = relationship(foreign_keys=[team_id])
    sections: Mapped[list["PerformanceReviewSection"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )
    projects: Mapped[list["PerformanceReviewProject"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )


class PerformanceReviewProject(Base, TimestampMixin):
    __tablename__ = "performance_review_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("performance_review_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )
    tool_number: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    part_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    assignment_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    hours_logged: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    execution_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    project_stage: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contribution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    achievement_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_auto_imported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sheet: Mapped[PerformanceReviewSheet] = relationship(back_populates="projects")
    project: Mapped[Optional["Project"]] = relationship(foreign_keys=[project_id])


class PerformanceReviewSection(Base, TimestampMixin):
    __tablename__ = "performance_review_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("performance_review_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sheet: Mapped[PerformanceReviewSheet] = relationship(back_populates="sections")
    items: Mapped[list["PerformanceReviewItem"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class PerformanceReviewItem(Base, TimestampMixin):
    __tablename__ = "performance_review_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("performance_review_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    employee_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    section: Mapped[PerformanceReviewSection] = relationship(back_populates="items")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_project_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_templates.id"), nullable=True
    )
    default_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    default_project_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_types.id"), nullable=True
    )
    default_working_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=True
    )
    default_folder_structure: Mapped[Optional[str]] = mapped_column(String(500))
    due_date_calculation: Mapped[DueDateCalculationMode] = mapped_column(
        Enum(DueDateCalculationMode, name="due_date_calculation", native_enum=False),
        nullable=False,
        default=DueDateCalculationMode.from_start,
    )
    project_number_format: Mapped[Optional[str]] = mapped_column(String(100))
    project_number_prefix: Mapped[Optional[str]] = mapped_column(String(50))
    next_project_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    default_currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="customer")
    project_templates: Mapped[list[ProjectTemplate]] = relationship(
        back_populates="customer",
        foreign_keys="ProjectTemplate.customer_id",
    )
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="customer"
    )
    default_working_model: Mapped[Optional[WorkingModel]] = relationship(
        back_populates="customers",
        foreign_keys=[default_working_model_id],
    )


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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contact_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contact_types.id"), nullable=True
    )

    customer: Mapped[Customer] = relationship(back_populates="contacts")
    contact_type: Mapped[Optional["ContactType"]] = relationship(
        back_populates="contacts"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="customer_contact")


class ProjectType(Base, TimestampMixin):
    __tablename__ = "project_types"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    templates: Mapped[list[ProjectTemplate]] = relationship(
        back_populates="project_type"
    )
    projects: Mapped[list[Project]] = relationship(back_populates="project_type")


class ProjectTemplate(Base, TimestampMixin):
    __tablename__ = "project_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    project_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_types.id"), nullable=False
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    default_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project_type: Mapped[ProjectType] = relationship(back_populates="templates")
    customer: Mapped[Optional[Customer]] = relationship(
        back_populates="project_templates",
        foreign_keys=[customer_id],
    )
    default_team: Mapped[Optional[Team]] = relationship(
        foreign_keys=[default_team_id]
    )
    milestones: Mapped[list[ProjectTemplateMilestone]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ProjectTemplateMilestone.sort_order",
    )
    projects: Mapped[list[Project]] = relationship(back_populates="project_template")


class ProjectTemplateMilestone(Base, TimestampMixin):
    __tablename__ = "project_template_milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    milestone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_due_offset_days: Mapped[Optional[int]] = mapped_column(Integer)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    project_stage: Mapped[Optional[ProjectStage]] = mapped_column(
        Enum(ProjectStage, name="template_milestone_stage", native_enum=False),
        nullable=True,
    )
    estimated_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    assigned_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_assigned_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    template: Mapped[ProjectTemplate] = relationship(back_populates="milestones")
    default_assigned_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[default_assigned_user_id]
    )


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
    function_category: Mapped[TaskTypeFunctionCategory] = mapped_column(
        Enum(TaskTypeFunctionCategory, name="task_type_function_category", native_enum=False),
        nullable=False,
        default=TaskTypeFunctionCategory.engineering,
    )

    stream: Mapped[Stream] = relationship(back_populates="task_types")
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="task_type"
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tool_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    part_description: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    customer_contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    design_leader_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    designer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    surfacer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    stream_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("streams.id"), nullable=True
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    project_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_types.id"), nullable=True
    )
    project_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_templates.id"), nullable=True
    )
    working_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=True
    )
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    quoted_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    current_planned_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    actual_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        "status",
        Enum(ExecutionStatus, name="project_status", native_enum=False),
        nullable=False,
        default=ExecutionStatus.planning,
    )
    project_stage: Mapped[ProjectStage] = mapped_column(
        Enum(ProjectStage, name="project_stage", native_enum=False),
        nullable=False,
        default=ProjectStage.preliminary,
    )
    health: Mapped[ProjectHealth] = mapped_column(
        Enum(ProjectHealth, name="project_health", native_enum=True),
        nullable=False,
        default=ProjectHealth.green,
    )
    priority: Mapped[ProjectPriority] = mapped_column(
        Enum(ProjectPriority, name="project_priority", native_enum=False),
        nullable=False,
        default=ProjectPriority.medium,
    )
    complexity: Mapped[ProjectComplexity] = mapped_column(
        Enum(ProjectComplexity, name="project_complexity", native_enum=False),
        nullable=False,
        default=ProjectComplexity.medium,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    work_order_number: Mapped[Optional[str]] = mapped_column(String(100))
    press_tonnage: Mapped[Optional[str]] = mapped_column(String(50))
    plastic_material: Mapped[Optional[str]] = mapped_column(String(150))
    cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tool_type: Mapped[Optional[str]] = mapped_column(String(100))
    customer_specs: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    project_folder_path: Mapped[Optional[str]] = mapped_column(String(500))
    cad_folder_path: Mapped[Optional[str]] = mapped_column(String(500))
    released_folder_path: Mapped[Optional[str]] = mapped_column(String(500))

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
    team: Mapped[Optional[Team]] = relationship(back_populates="projects")
    project_type: Mapped[Optional[ProjectType]] = relationship(
        back_populates="projects"
    )
    project_template: Mapped[Optional[ProjectTemplate]] = relationship(
        back_populates="projects"
    )
    working_model: Mapped[Optional[WorkingModel]] = relationship(back_populates="projects")
    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="project"
    )
    decisions: Mapped[list["ProjectDecision"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    engineering_changes: Mapped[list["EngineeringChange"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
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
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    planned_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0")
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assignment_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped[Project] = relationship(back_populates="milestones")
    assigned_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[assigned_user_id]
    )
    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="milestone"
    )


class NonProductiveCode(Base, TimestampMixin):
    __tablename__ = "non_productive_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[NonProductiveCodeCategory] = mapped_column(
        Enum(
            NonProductiveCodeCategory,
            name="non_productive_code_category",
            native_enum=False,
        ),
        nullable=False,
        default=NonProductiveCodeCategory.non_productive,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    timesheet_entries: Mapped[list[TimesheetEntry]] = relationship(
        back_populates="non_productive_code"
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
    approval_comments: Mapped[Optional[str]] = mapped_column(Text)

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
        CheckConstraint("hours >= 0 AND hours <= 24", name="ck_timesheet_entry_hours"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timesheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("timesheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    task_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_types.id")
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id")
    )
    non_productive_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("non_productive_codes.id")
    )
    work_category: Mapped[WorkCategory] = mapped_column(
        Enum(WorkCategory, name="work_category", native_enum=True),
        nullable=False,
        default=WorkCategory.productive,
    )
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    leave_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    contribution_reason: Mapped[Optional[ContributionReason]] = mapped_column(
        Enum(ContributionReason, name="contribution_reason", native_enum=False),
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    delete_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    timesheet: Mapped[Timesheet] = relationship(back_populates="entries")
    project: Mapped[Optional[Project]] = relationship(back_populates="timesheet_entries")
    customer: Mapped[Optional[Customer]] = relationship(back_populates="timesheet_entries")
    task_type: Mapped[Optional[TaskType]] = relationship(
        back_populates="timesheet_entries"
    )
    milestone: Mapped[Optional[Milestone]] = relationship(
        back_populates="timesheet_entries"
    )
    non_productive_code: Mapped[Optional[NonProductiveCode]] = relationship(
        back_populates="timesheet_entries"
    )


class TimesheetEntryDeletionLog(Base, TimestampMixin):
    __tablename__ = "timesheet_entry_deletion_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    designer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    designer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    tool_number: Mapped[Optional[str]] = mapped_column(String(100))
    task_name: Mapped[Optional[str]] = mapped_column(String(120))
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    deleted_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False, default="User Deleted")
    restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    restored_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class TimesheetImportHistory(Base, TimestampMixin):
    __tablename__ = "timesheet_import_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    designer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    designer_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    week_start: Mapped[Optional[date]] = mapped_column(Date)
    date_range_label: Mapped[Optional[str]] = mapped_column(String(80))
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    upload_id: Mapped[Optional[str]] = mapped_column(String(64))
    log_json: Mapped[Optional[str]] = mapped_column(Text)

    imported_by: Mapped[User] = relationship(foreign_keys=[imported_by_id])
    designer_user: Mapped[Optional[User]] = relationship(foreign_keys=[designer_user_id])


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type", native_enum=True),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[ActivityAction] = mapped_column(
        Enum(ActivityAction, name="activity_action", native_enum=True),
        nullable=False,
    )
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[Optional[User]] = relationship(back_populates="activities")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[EntityType]] = mapped_column(
        Enum(EntityType, name="notification_entity_type", native_enum=True),
        nullable=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="notifications")


# Phase 7 foundation models (registers tables with metadata)
from app.models.foundation import (  # noqa: E402, F401
    CompanySettings,
    ContactType,
    Department,
    EngineeringDiscipline,
    FilePathSettings,
    Holiday,
    EmailSettings,
    EmailTemplate,
    EmailMessage,
    NotificationSettings,
    Skill,
    UserPreferences,
    UserSkill,
)
from app.models.intelligence import (  # noqa: E402, F401
    EngineeringChange,
    LessonLearned,
    ProjectDecision,
    ProjectKnowledgeRecord,
)
