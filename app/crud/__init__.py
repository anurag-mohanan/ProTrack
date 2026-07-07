from app.crud.base import CRUDBase
from app.crud.milestone import milestone
from app.crud.project import project
from app.crud.timesheet import timesheet
from app.crud.timesheet_entry import timesheet_entry
from app.crud.user import user
from app.crud.project_template import project_template
from app.crud.task_type import task_type
from app.models.models import Contact, Customer, ProjectType, Role, Stream, TaskType
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
from app.schemas.templates import ProjectTypeCreate, ProjectTypeUpdate

role = CRUDBase[Role, RoleCreate, RoleUpdate](Role)
project_type = CRUDBase[ProjectType, ProjectTypeCreate, ProjectTypeUpdate](ProjectType)
stream = CRUDBase[Stream, StreamCreate, StreamUpdate](Stream)
customer = CRUDBase[Customer, CustomerCreate, CustomerUpdate](Customer)
contact = CRUDBase[Contact, ContactCreate, ContactUpdate](Contact)

__all__ = [
    "contact",
    "customer",
    "milestone",
    "project",
    "project_template",
    "project_type",
    "role",
    "stream",
    "task_type",
    "timesheet",
    "timesheet_entry",
    "user",
]
