from app.crud.base import CRUDBase
from app.crud.milestone import milestone
from app.crud.project import project
from app.crud.timesheet import timesheet
from app.crud.timesheet_entry import timesheet_entry
from app.crud.user import user
from app.models.models import Contact, Customer, Role, Stream, TaskType
from app.schemas.identity import RoleCreate, RoleUpdate
from app.schemas.organization import (
    ContactCreate,
    ContactUpdate,
    CustomerCreate,
    CustomerUpdate,
    StreamCreate,
    StreamUpdate,
    TaskTypeCreate,
    TaskTypeUpdate,
)

role = CRUDBase[Role, RoleCreate, RoleUpdate](Role)
stream = CRUDBase[Stream, StreamCreate, StreamUpdate](Stream)
customer = CRUDBase[Customer, CustomerCreate, CustomerUpdate](Customer)
contact = CRUDBase[Contact, ContactCreate, ContactUpdate](Contact)
task_type = CRUDBase[TaskType, TaskTypeCreate, TaskTypeUpdate](TaskType)

__all__ = [
    "contact",
    "customer",
    "milestone",
    "project",
    "role",
    "stream",
    "task_type",
    "timesheet",
    "timesheet_entry",
    "user",
]
