from fastapi import Depends

from app.api.auth_deps import require_roles
from app.api.v1 import (
    activities,
    auth,
    dashboard,
    imports,
    timesheet_imports,
    lookups,
    milestones,
    non_productive_codes,
    notifications,
    preferences,
    project_templates,
    project_types,
    projects,
    reports,
    roles,
    settings,
    timesheet_entries,
    timesheets,
    teams,
    users,
)
from app.api.v1.router_factory import (
    APIRouter,
    ContactFilters,
    TaskTypeFilters,
    build_crud_router,
)
from app.crud import (
    contact,
    customer,
    stream,
    task_type,
)
from app.schemas.organization import (
    ContactCreate,
    ContactRead,
    ContactUpdate,
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    StreamCreate,
    StreamRead,
    StreamUpdate,
    TaskTypeCreate,
    TaskTypeRead,
    TaskTypeUpdate,
)
from app.schemas.project import MilestoneCreate, MilestoneRead, MilestoneUpdate

api_router = APIRouter()

api_router.include_router(auth.router)

admin_access = [Depends(require_roles("Admin", "Engineering Manager"))]
master_data_write = ("Admin", "Engineering Manager")
delivery_write = ("Admin", "Engineering Manager", "Design Leader")

api_router.include_router(lookups.router)
api_router.include_router(roles.router)
api_router.include_router(users.router)
api_router.include_router(teams.router)
api_router.include_router(
    build_crud_router(
        prefix="/streams",
        tags=["streams"],
        crud=stream,
        schema_read=StreamRead,
        schema_create=StreamCreate,
        schema_update=StreamUpdate,
        router_dependencies=admin_access,
        write_roles=master_data_write,
        delete_entity="stream",
    )
)
api_router.include_router(
    build_crud_router(
        prefix="/customers",
        tags=["customers"],
        crud=customer,
        schema_read=CustomerRead,
        schema_create=CustomerCreate,
        schema_update=CustomerUpdate,
        router_dependencies=admin_access,
        write_roles=master_data_write,
        delete_entity="customer",
    )
)
api_router.include_router(
    build_crud_router(
        prefix="/contacts",
        tags=["contacts"],
        crud=contact,
        schema_read=ContactRead,
        schema_create=ContactCreate,
        schema_update=ContactUpdate,
        filters_model=ContactFilters,
        router_dependencies=admin_access,
        write_roles=master_data_write,
        delete_entity="contact",
    )
)
api_router.include_router(
    build_crud_router(
        prefix="/task-types",
        tags=["task-types"],
        crud=task_type,
        schema_read=TaskTypeRead,
        schema_create=TaskTypeCreate,
        schema_update=TaskTypeUpdate,
        filters_model=TaskTypeFilters,
        router_dependencies=admin_access,
        write_roles=master_data_write,
        delete_entity="task_type",
    )
)
api_router.include_router(project_types.router)
api_router.include_router(project_templates.router)
api_router.include_router(projects.router)
api_router.include_router(milestones.router)
api_router.include_router(timesheets.router)
api_router.include_router(timesheet_entries.router)
api_router.include_router(non_productive_codes.router)
api_router.include_router(settings.router)
api_router.include_router(preferences.router)
api_router.include_router(notifications.router)
api_router.include_router(activities.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(imports.router)
api_router.include_router(timesheet_imports.router)
