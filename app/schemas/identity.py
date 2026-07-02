from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    EmploymentType,
    SkillLevel,
    UserAvailabilityStatus,
)
from app.schemas.common import TimestampSchema


class RoleBase(BaseModel):
    name: str = Field(max_length=50)
    description: str | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    description: str | None = None


class RoleRead(RoleBase, TimestampSchema):
    pass


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


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True


class UserUpdate(BaseModel):
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


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)
    generate_temporary: bool = False


class ResetPasswordResponse(BaseModel):
    temporary_password: str | None = None
    message: str


class UserRead(UserBase, TimestampSchema):
    model_config = ConfigDict(from_attributes=True)
    team_name: str | None = None
    department_name: str | None = None
    manager_name: str | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_id: UUID | None = None


class UserDeleteCheck(BaseModel):
    can_permanently_delete: bool
    blockers: list[str] = Field(default_factory=list)
