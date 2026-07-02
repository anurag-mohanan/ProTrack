from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    DueDateCalculationMode,
    EmploymentType,
    ProjectPriority,
    ProjectStage,
    SkillLevel,
    UserAvailabilityStatus,
)
from app.schemas.common import TimestampSchema


class CompanySettingsRead(BaseModel):
    id: UUID
    company_name: str
    company_short_name: str | None = None
    logo_url: str | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    gst_number: str | None = None
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    financial_year_start_month: int = 4
    default_working_hours_per_day: Decimal = Decimal("8")
    default_working_days: str = "Mon,Tue,Wed,Thu,Fri"


class CompanySettingsUpdate(BaseModel):
    company_name: str | None = Field(default=None, max_length=200)
    company_short_name: str | None = Field(default=None, max_length=80)
    logo_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    gst_number: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=64)
    financial_year_start_month: int | None = Field(default=None, ge=1, le=12)
    default_working_hours_per_day: Decimal | None = Field(default=None, gt=0, le=24)
    default_working_days: str | None = Field(default=None, max_length=50)


class PublicCompanySettingsRead(BaseModel):
    company_name: str
    company_short_name: str | None = None
    logo_url: str | None = None
    website: str | None = None


class BrandingSettingsRead(BaseModel):
    id: UUID
    theme_preset: str = "prosohm_professional"
    primary_color: str = "#0066B3"
    secondary_color: str = "#1E293B"
    accent_color: str = "#0EA5E9"
    success_color: str = "#16A34A"
    warning_color: str = "#D97706"
    danger_color: str = "#DC2626"
    sidebar_color: str = "#0F172A"
    header_color: str = "#FFFFFF"
    button_style: str = "rounded"
    border_radius: int = 12
    card_style: str = "elevated"
    density: str = "default"


class BrandingSettingsUpdate(BaseModel):
    theme_preset: str | None = Field(default=None, max_length=64)
    primary_color: str | None = Field(default=None, max_length=20)
    secondary_color: str | None = Field(default=None, max_length=20)
    accent_color: str | None = Field(default=None, max_length=20)
    success_color: str | None = Field(default=None, max_length=20)
    warning_color: str | None = Field(default=None, max_length=20)
    danger_color: str | None = Field(default=None, max_length=20)
    sidebar_color: str | None = Field(default=None, max_length=20)
    header_color: str | None = Field(default=None, max_length=20)
    button_style: str | None = Field(default=None, max_length=20)
    border_radius: int | None = Field(default=None, ge=0, le=32)
    card_style: str | None = Field(default=None, max_length=20)
    density: str | None = Field(default=None, max_length=20)


class PublicBrandingRead(BaseModel):
    theme_preset: str
    primary_color: str
    secondary_color: str
    accent_color: str
    success_color: str
    warning_color: str
    danger_color: str
    sidebar_color: str
    header_color: str
    button_style: str
    border_radius: int
    card_style: str
    density: str


class PublicSettingsRead(BaseModel):
    company: PublicCompanySettingsRead
    branding: PublicBrandingRead


class HolidayBase(BaseModel):
    name: str = Field(max_length=200)
    holiday_date: date
    region: str | None = Field(default=None, max_length=100)
    is_working_day: bool = False
    is_recurring: bool = False


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    holiday_date: date | None = None
    region: str | None = Field(default=None, max_length=100)
    is_working_day: bool | None = None
    is_recurring: bool | None = None


class HolidayRead(HolidayBase, TimestampSchema):
    pass


class DepartmentBase(BaseModel):
    name: str = Field(max_length=100)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = None
    is_active: bool | None = None


class DepartmentRead(DepartmentBase, TimestampSchema):
    pass


class ContactTypeRead(TimestampSchema):
    id: UUID
    name: str
    description: str | None = None
    is_active: bool = True


class SkillRead(TimestampSchema):
    id: UUID
    name: str
    category: str | None = None
    is_active: bool = True


class EngineeringDisciplineRead(TimestampSchema):
    id: UUID
    name: str
    description: str | None = None
    is_active: bool = True


class UserSkillRead(TimestampSchema):
    id: UUID
    user_id: UUID
    skill_id: UUID
    skill_name: str | None = None
    proficiency: SkillLevel


class UserSkillCreate(BaseModel):
    skill_id: UUID
    proficiency: SkillLevel = SkillLevel.intermediate


class FilePathSettingsRead(BaseModel):
    id: UUID
    project_root_folder: str | None = None
    customer_folder_template: str | None = None
    drawing_folder_template: str | None = None
    design_folder_template: str | None = None
    backup_folder: str | None = None


class FilePathSettingsUpdate(BaseModel):
    project_root_folder: str | None = Field(default=None, max_length=500)
    customer_folder_template: str | None = Field(default=None, max_length=500)
    drawing_folder_template: str | None = Field(default=None, max_length=500)
    design_folder_template: str | None = Field(default=None, max_length=500)
    backup_folder: str | None = Field(default=None, max_length=500)


class NotificationSettingsRead(BaseModel):
    id: UUID
    projects_due_enabled: bool = True
    overdue_enabled: bool = True
    pending_approvals_enabled: bool = True
    new_assignments_enabled: bool = True
    imports_completed_enabled: bool = True


class NotificationSettingsUpdate(BaseModel):
    projects_due_enabled: bool | None = None
    overdue_enabled: bool | None = None
    pending_approvals_enabled: bool | None = None
    new_assignments_enabled: bool | None = None
    imports_completed_enabled: bool | None = None


class UserCapacityUpdate(BaseModel):
    working_hours_per_day: Decimal | None = Field(default=None, gt=0, le=24)
    working_days: str | None = Field(default=None, max_length=50)
    employment_type: EmploymentType | None = None
    department_id: UUID | None = None
    skill_level: SkillLevel | None = None
    joining_date: date | None = None
    leaving_date: date | None = None
    availability_status: UserAvailabilityStatus | None = None
    max_allocation_percent: int | None = Field(default=None, ge=0, le=100)


class CustomerSettingsUpdate(BaseModel):
    default_project_template_id: UUID | None = None
    default_team_id: UUID | None = None
    default_project_type_id: UUID | None = None
    default_folder_structure: str | None = Field(default=None, max_length=500)
    due_date_calculation: DueDateCalculationMode | None = None
    project_number_format: str | None = Field(default=None, max_length=100)
    project_number_prefix: str | None = Field(default=None, max_length=50)


class ProjectTemplateMilestoneExtended(BaseModel):
    project_stage: ProjectStage | None = None
    estimated_hours: Decimal | None = None


class ProjectPriorityRead(BaseModel):
    value: ProjectPriority
    label: str
