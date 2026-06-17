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


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    role_id: UUID | None = None
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class UserRead(UserBase, TimestampSchema):
    model_config = ConfigDict(from_attributes=True)
