from collections.abc import Callable
from uuid import UUID

from app.api.deps import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Session,
    get_db,
    get_object_or_404,
    status,
)
from app.api.auth_deps import get_current_user, require_roles
from app.crud.base import CRUDBase
from app.models.enums import ProjectStatus, TimesheetStatus
from app.models.models import User
from app.schemas.common import BaseModel


class EmptyFilters(BaseModel):
    pass


class ContactFilters(BaseModel):
    customer_id: UUID | None = None


class TaskTypeFilters(BaseModel):
    stream_id: UUID | None = None


class ProjectFilters(BaseModel):
    customer_id: UUID | None = None
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    status: ProjectStatus | None = None


class MilestoneFilters(BaseModel):
    project_id: UUID | None = None


class TimesheetFilters(BaseModel):
    user_id: UUID | None = None
    status: TimesheetStatus | None = None


class TimesheetEntryFilters(BaseModel):
    timesheet_id: UUID | None = None
    project_id: UUID | None = None


def build_crud_router(
    *,
    prefix: str,
    tags: list[str],
    crud: CRUDBase,
    schema_read: type[BaseModel],
    schema_create: type[BaseModel],
    schema_update: type[BaseModel],
    filters_model: type[BaseModel] = EmptyFilters,
    write_roles: tuple[str, ...] = ("Admin", "Project Manager"),
    router_dependencies: list[Callable] | None = None,
) -> APIRouter:
    dependencies = router_dependencies or [Depends(get_current_user)]
    write_dependency = Depends(require_roles(*write_roles))

    router = APIRouter(prefix=prefix, tags=tags, dependencies=dependencies)

    @router.get("", response_model=list[schema_read])
    def list_records(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        filters: filters_model = Depends(),
        db: Session = Depends(get_db),
    ):
        active_filters = {
            key: value
            for key, value in filters.model_dump().items()
            if value is not None
        }
        return crud.get_multi(db, skip=skip, limit=limit, filters=active_filters)

    @router.get("/{record_id}", response_model=schema_read)
    def get_record(record_id: UUID, db: Session = Depends(get_db)):
        return get_object_or_404(crud, db, record_id)

    @router.post(
        "",
        response_model=schema_read,
        status_code=status.HTTP_201_CREATED,
        dependencies=[write_dependency],
    )
    def create_record(obj_in: schema_create, db: Session = Depends(get_db)):
        return crud.create(db, obj_in=obj_in)

    @router.patch(
        "/{record_id}",
        response_model=schema_read,
        dependencies=[write_dependency],
    )
    def update_record(
        record_id: UUID,
        obj_in: schema_update,
        db: Session = Depends(get_db),
    ):
        db_obj = get_object_or_404(crud, db, record_id)
        return crud.update(db, db_obj=db_obj, obj_in=obj_in)

    @router.delete(
        "/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[write_dependency],
    )
    def delete_record(record_id: UUID, db: Session = Depends(get_db)):
        deleted = crud.delete(db, record_id=record_id)
        if deleted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
            )

    return router
