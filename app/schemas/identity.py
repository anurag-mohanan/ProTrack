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


class RoleCreate(BlankOptionalFieldsMixin, RoleBase):
    pass


class RoleUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=50)
    description: str | None = None


class RoleRead(RoleBase, TimestampSchema):
    pass


class UserTeamAssignmentBase(BaseModel):
    team_id: UUID
    relationship_type: TeamRelationshipType = TeamRelationshipType.member
    is_primary: bool = False


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
    leaving_date: date | None = None
    availability_status: UserAvailabilityStatus = UserAvailabilityStatus.available
    max_allocation_percent: int = 100
    operational_role_type_id: UUID | None = None
    kpi_engineering_productivity: bool = True
    kpi_capacity_planning: bool = True
    kpi_utilization: bool = True
    kpi_workload_planning: bool = True
    kpi_dashboard_productivity: bool = True


class UserCreate(BlankOptionalFieldsMixin, UserBase):
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
    team_assignments: list[UserTeamAssignmentWrite] | None = None


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
    leaving_date: date | None = None
    availability_status: UserAvailabilityStatus | None = None
    max_allocation_percent: int | None = Field(default=None, ge=0, le=100)
    operational_role_type_id: UUID | None = None
    kpi_engineering_productivity: bool | None = None
    kpi_capacity_planning: bool | None = None
    kpi_utilization: bool | None = None
    kpi_workload_planning: bool | None = None
    kpi_dashboard_productivity: bool | None = None
    reset_kpi_defaults: bool = False
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
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
    team_name: str | None = None
    team_assignments: list[UserTeamAssignmentRead] = Field(default_factory=list)
    team_names: list[str] = Field(default_factory=list)
    department_name: str | None = None
    manager_name: str | None = None
    active_projects_count: int = 0
    last_login: datetime | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_id: UUID | None = None
    is_locked: bool = False
    failed_login_count: int = 0
    module_access: list[str] | None = None
    special_permissions: list[str] | None = None
    resolved_modules: list[str] = Field(default_factory=list)
    resolved_special_permissions: list[str] = Field(default_factory=list)
    kpi_configuration: UserKpiConfiguration | None = None

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
