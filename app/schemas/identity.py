from datetime import date, datetime
import json
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from app.core.password_policy import validate_password_strength

from app.models.enums import (
    EmploymentType,
    SkillLevel,
    TaskTypeFunctionCategory,
    TeamRelationshipType,
    UserAvailabilityStatus,
)
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class RoleBase(BaseModel):
    name: str = Field(max_length=50)
    description: str | None = None
    org_department_id: UUID | None = None
    rank: int = 100
    parent_role_id: UUID | None = None


class RoleCreate(BlankOptionalFieldsMixin, RoleBase):
    pass


class RoleUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=50)
    description: str | None = None
    org_department_id: UUID | None = None
    rank: int | None = None
    parent_role_id: UUID | None = None
    is_active: bool | None = None


class RoleRead(RoleBase, TimestampSchema):
    is_active: bool = True


class RoleHierarchyNode(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    rank: int = 100
    parent_role_id: UUID | None = None
    parent_role_name: str | None = None
    is_active: bool = True
    is_system: bool = False
    user_count: int = 0


class RoleHierarchyDepartment(BaseModel):
    department_id: UUID | None = None
    department_code: str | None = None
    department_name: str
    colour: str | None = None
    sort_order: int = 100
    roles: list[RoleHierarchyNode] = Field(default_factory=list)


class RoleHierarchyRead(BaseModel):
    departments: list[RoleHierarchyDepartment] = Field(default_factory=list)


class OrgDepartmentBase(BaseModel):
    code: str = Field(max_length=40)
    name: str = Field(max_length=120)
    description: str | None = None
    colour: str = Field(default="#1976d2", max_length=20)
    sort_order: int = 100
    head_user_id: UUID | None = None
    is_active: bool = True


class OrgDepartmentCreate(BlankOptionalFieldsMixin, OrgDepartmentBase):
    pass


class OrgDepartmentUpdate(BlankOptionalFieldsMixin, BaseModel):
    code: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    colour: str | None = Field(default=None, max_length=20)
    sort_order: int | None = None
    head_user_id: UUID | None = None
    is_active: bool | None = None


class OrgDepartmentRead(OrgDepartmentBase, TimestampSchema):
    head_name: str | None = None
    member_count: int = 0


class AssignDepartmentRequest(BaseModel):
    user_id: UUID


class UserTeamAssignmentBase(BaseModel):
    team_id: UUID
    relationship_type: TeamRelationshipType = TeamRelationshipType.member
    is_primary: bool = False
    include_in_timesheet_reports: bool = True


class UserTeamAssignmentWrite(BlankOptionalFieldsMixin, UserTeamAssignmentBase):
    pass


class UserTeamAssignmentRead(UserTeamAssignmentBase):
    id: UUID
    team_name: str
    created_at: datetime | None = None


class OperationalRoleTypeRead(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None = None
    dashboard_profile: str
    default_kpi_engineering_productivity: bool = True
    default_kpi_capacity_planning: bool = True
    default_kpi_utilization: bool = True
    default_kpi_workload_planning: bool = True
    default_kpi_dashboard_productivity: bool = True


class UserKpiConfiguration(BaseModel):
    operational_role_type_id: UUID | None = None
    operational_role_name: str | None = None
    dashboard_profile: str = "engineering"
    kpi_engineering_productivity: bool = True
    kpi_capacity_planning: bool = True
    kpi_utilization: bool = True
    kpi_workload_planning: bool = True
    kpi_dashboard_productivity: bool = True


class UserBase(BaseModel):
    role_id: UUID
    email: EmailStr
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=100)
    manager_id: UUID | None = None
    is_active: bool = True
    must_change_password: bool = False
    team_id: UUID | None = None
    department_id: UUID | None = None
    working_hours_per_day: Decimal = Decimal("8")
    working_days: str = "Mon,Tue,Wed,Thu,Fri"
    employment_type: EmploymentType | None = None
    skill_level: SkillLevel | None = None
    joining_date: date | None = None
    first_job_date: date | None = None
    leaving_date: date | None = None
    stream_id: UUID | None = None
    primary_tool: str | None = Field(default=None, max_length=80)
    work_function: str | None = Field(default=None, max_length=120)
    availability_status: UserAvailabilityStatus = UserAvailabilityStatus.available
    max_allocation_percent: int = 100
    operational_role_type_id: UUID | None = None
    kpi_engineering_productivity: bool = True
    kpi_capacity_planning: bool = True
    kpi_utilization: bool = True
    kpi_workload_planning: bool = True
    kpi_dashboard_productivity: bool = True
    default_working_model_id: UUID | None = None


class UserCreate(BlankOptionalFieldsMixin, UserBase):
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True
    requires_timesheet: bool | None = None
    requires_salary: bool | None = None
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
    module_actions: dict[str, list[str]] | None = None
    team_assignments: list[UserTeamAssignmentWrite] | None = None
    confirm_left_organisation: bool = False


class UserUpdate(BlankOptionalFieldsMixin, BaseModel):
    role_id: UUID | None = None
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=100)
    manager_id: UUID | None = None
    is_active: bool | None = None
    team_id: UUID | None = None
    department_id: UUID | None = None
    working_hours_per_day: Decimal | None = Field(default=None, gt=0, le=24)
    working_days: str | None = Field(default=None, max_length=50)
    employment_type: EmploymentType | None = None
    skill_level: SkillLevel | None = None
    joining_date: date | None = None
    first_job_date: date | None = None
    leaving_date: date | None = None
    confirm_left_organisation: bool = False
    stream_id: UUID | None = None
    primary_tool: str | None = Field(default=None, max_length=80)
    work_function: str | None = Field(default=None, max_length=120)
    availability_status: UserAvailabilityStatus | None = None
    max_allocation_percent: int | None = Field(default=None, ge=0, le=100)
    operational_role_type_id: UUID | None = None
    kpi_engineering_productivity: bool | None = None
    kpi_capacity_planning: bool | None = None
    kpi_utilization: bool | None = None
    kpi_workload_planning: bool | None = None
    kpi_dashboard_productivity: bool | None = None
    default_working_model_id: UUID | None = None
    requires_timesheet: bool | None = None
    requires_salary: bool | None = None
    reset_kpi_defaults: bool = False
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
    module_actions: dict[str, list[str]] | None = None
    team_assignments: list[UserTeamAssignmentWrite] | None = None


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)
    generate_temporary: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value is not None:
            validate_password_strength(value)
        return value


class ResetPasswordResponse(BaseModel):
    temporary_password: str | None = None
    message: str


class MustChangePasswordRequest(BaseModel):
    required: bool


class UserRead(UserBase, TimestampSchema):
    model_config = ConfigDict(from_attributes=True)
    requires_timesheet: bool = False
    requires_salary: bool = True
    team_name: str | None = None
    stream_name: str | None = None
    team_assignments: list[UserTeamAssignmentRead] = Field(default_factory=list)
    team_names: list[str] = Field(default_factory=list)
    department_name: str | None = None
    manager_name: str | None = None
    active_projects_count: int = 0
    last_login: datetime | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    offboard_applied_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_id: UUID | None = None
    is_locked: bool = False
    failed_login_count: int = 0
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
    module_actions: dict[str, list[str]] | None = None
    resolved_modules: list[str] = Field(default_factory=list)
    resolved_special_permissions: list[str] = Field(default_factory=list)
    resolved_module_actions: dict[str, list[str]] = Field(default_factory=dict)
    kpi_configuration: UserKpiConfiguration | None = None

    @field_validator("module_actions", mode="before")
    @classmethod
    def parse_module_actions_json(cls, value: object) -> dict[str, list[str]] | None:
        if value is None or isinstance(value, dict):
            return value  # type: ignore[return-value]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, dict):
                return {
                    str(k): [str(a) for a in v if isinstance(a, str)]
                    for k, v in parsed.items()
                    if isinstance(v, list)
                }
        return None

    @field_validator("module_access", "special_permissions", mode="before")
    @classmethod
    def parse_access_json(cls, value: object) -> list[str] | None:
        if value is None or isinstance(value, list):
            return value  # type: ignore[return-value]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        return None

    @computed_field
    @property
    def password_changed(self) -> bool:
        return not self.must_change_password


class UserDeleteCheck(BaseModel):
    can_permanently_delete: bool
    blockers: list[str] = Field(default_factory=list)
