from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import DueDateCalculationMode, NonProductiveCodeCategory, TaskTypeFunctionCategory
from app.schemas.common import BlankOptionalFieldsMixin, TimestampSchema


class StreamBase(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    is_active: bool = True


class StreamCreate(BlankOptionalFieldsMixin, StreamBase):
    pass


class StreamUpdate(BlankOptionalFieldsMixin, BaseModel):
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
    default_project_template_id: UUID | None = None
    default_team_id: UUID | None = None
    default_project_type_id: UUID | None = None
    default_folder_structure: str | None = Field(default=None, max_length=500)
    due_date_calculation: DueDateCalculationMode = DueDateCalculationMode.from_start
    project_number_format: str | None = Field(default=None, max_length=100)
    project_number_prefix: str | None = Field(default=None, max_length=50)


class CustomerCreate(BlankOptionalFieldsMixin, CustomerBase):
    pass


class CustomerUpdate(BlankOptionalFieldsMixin, BaseModel):
    name: str | None = Field(default=None, max_length=200)
    code: str | None = Field(default=None, max_length=20)
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    default_project_template_id: UUID | None = None
    default_team_id: UUID | None = None
    default_project_type_id: UUID | None = None
    default_folder_structure: str | None = Field(default=None, max_length=500)
    due_date_calculation: DueDateCalculationMode | None = None
    project_number_format: str | None = Field(default=None, max_length=100)
    project_number_prefix: str | None = Field(default=None, max_length=50)


class CustomerRead(CustomerBase, TimestampSchema):
    pass


class ContactBase(BaseModel):
    customer_id: UUID
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    contact_type_id: UUID | None = None
    is_primary: bool = False
    is_active: bool = True


class ContactCreate(BlankOptionalFieldsMixin, ContactBase):
    pass


class ContactUpdate(BlankOptionalFieldsMixin, BaseModel):
    customer_id: UUID | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    job_title: str | None = Field(default=None, max_length=100)
    contact_type_id: UUID | None = None
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
    function_category: TaskTypeFunctionCategory = TaskTypeFunctionCategory.engineering


class TaskTypeCreate(BlankOptionalFieldsMixin, TaskTypeBase):
    pass


class TaskTypeUpdate(BlankOptionalFieldsMixin, BaseModel):
    stream_id: UUID | None = None
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_billable: bool | None = None
    is_active: bool | None = None
    function_category: TaskTypeFunctionCategory | None = None


class TaskTypeRead(TaskTypeBase, TimestampSchema):
    pass


class NonProductiveCodeBase(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=255)
    category: NonProductiveCodeCategory = NonProductiveCodeCategory.non_productive
    is_active: bool = True
    is_archived: bool = False
    sort_order: int = 0


class NonProductiveCodeCreate(BlankOptionalFieldsMixin, NonProductiveCodeBase):
    pass


class NonProductiveCodeUpdate(BlankOptionalFieldsMixin, BaseModel):
    code: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=255)
    category: NonProductiveCodeCategory | None = None
    is_active: bool | None = None
    is_archived: bool | None = None
    sort_order: int | None = None


class NonProductiveCodeRead(NonProductiveCodeBase, TimestampSchema):
    pass
