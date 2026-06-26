from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema


class StreamBase(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    is_active: bool = True


class StreamCreate(StreamBase):
    pass


class StreamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class StreamRead(StreamBase, TimestampSchema):
    pass


class CustomerBase(BaseModel):
    name: str = Field(max_length=200)
    code: str | None = Field(default=None, max_length=20)
    address: str | None = None
    notes: str | None = None
    is_active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    code: str | None = Field(default=None, max_length=20)
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerRead(CustomerBase, TimestampSchema):
    pass


class ContactBase(BaseModel):
    customer_id: UUID
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    is_primary: bool = False
    is_active: bool = True


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    customer_id: UUID | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    is_primary: bool | None = None
    is_active: bool | None = None


class ContactRead(ContactBase, TimestampSchema):
    pass


class TaskTypeBase(BaseModel):
    stream_id: UUID
    name: str = Field(max_length=100)
    description: str | None = None
    is_billable: bool = True
    is_active: bool = True


class TaskTypeCreate(TaskTypeBase):
    pass


class TaskTypeUpdate(BaseModel):
    stream_id: UUID | None = None
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_billable: bool | None = None
    is_active: bool | None = None


class TaskTypeRead(TaskTypeBase, TimestampSchema):
    pass
