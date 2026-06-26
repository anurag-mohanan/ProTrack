from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    is_active: bool = True
    must_change_password: bool = False


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True


class UserUpdate(BaseModel):
    role_id: UUID | None = None
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)
    generate_temporary: bool = False


class ResetPasswordResponse(BaseModel):
    temporary_password: str | None = None
    message: str


class UserRead(UserBase, TimestampSchema):
    model_config = ConfigDict(from_attributes=True)
    is_archived: bool = False
    archived_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by_id: UUID | None = None


class UserDeleteCheck(BaseModel):
    can_permanently_delete: bool
    blockers: list[str] = Field(default_factory=list)
