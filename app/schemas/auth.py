from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.password_policy import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: UUID
    email: EmailStr
    name: str | None = None
    role: str | None = None
    permissions: list[str] = Field(default_factory=list)
    team_id: UUID | None = None
    team_name: str | None = None
    team_ids: list[UUID] = Field(default_factory=list)
    team_names: list[str] = Field(default_factory=list)
    impersonator_id: UUID | None = None
    token_version: int = 0
    issued_at: datetime | None = None


class CurrentUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    role_id: UUID
    role_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    team_ids: list[UUID] = Field(default_factory=list)
    team_names: list[str] = Field(default_factory=list)
    stream_id: UUID | None = None
    stream_name: str | None = None
    relevant_stream_ids: list[UUID] = Field(default_factory=list)
    can_view_all_streams: bool = False
    is_active: bool
    must_change_password: bool
    last_login: datetime | None = None
    impersonator_id: UUID | None = None
    impersonator_name: str | None = None
    module_access: list[str] = Field(default_factory=list)
    special_permissions: list[str] = Field(default_factory=list)
    module_actions: dict[str, list[str]] = Field(default_factory=dict)
    requires_timesheet: bool = False
    can_enter_own_timesheet: bool = False
    can_view_organization_chart: bool = False
    data_scope: dict | None = None

    @property
    def password_changed(self) -> bool:
        return not self.must_change_password


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class ChangePasswordResponse(BaseModel):
    message: str
    must_change_password: bool = False


class UserProfileSkill(BaseModel):
    skill_id: UUID
    skill_name: str | None = None
    proficiency: str


class UserProfileSummary(BaseModel):
    active_projects: int = 0
    quoted_hours_assigned: Decimal = Decimal("0")
    actual_hours_logged: Decimal = Decimal("0")
    utilization_percent: Decimal = Decimal("0")
    timesheet_count: int = 0


class UserProfileRead(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str | None = None
    role_id: UUID
    role_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    department_id: UUID | None = None
    department_name: str | None = None
    manager_id: UUID | None = None
    manager_name: str | None = None
    is_active: bool
    employment_type: str | None = None
    working_hours_per_day: Decimal
    working_days: str
    availability_status: str
    skills: list[UserProfileSkill] = Field(default_factory=list)
    summary: UserProfileSummary
    preferences: "UserPreferencesSnapshot"


class UserPreferencesSnapshot(BaseModel):
    theme_mode: str = "company_default"
    sidebar_expanded: bool = True
    sidebar_auto_collapse: bool = False
    dashboard_layout: str = "default"
    table_density: str = "comfortable"
    font_size: str = "medium"
    animations_enabled: bool = True
    reduced_motion: bool = False
    default_landing_page: str = "dashboard"


UserProfileRead.model_rebuild()
