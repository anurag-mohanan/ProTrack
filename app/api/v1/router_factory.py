# pyright: reportInvalidTypeForm=false, reportArgumentType=false

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.crud.base import CRUDBase
from app.models.enums import ExecutionStatus, ProjectLifecycleFilter, ProjectStage, TimesheetStatus
from app.models.models import User
from app.schemas.common import BaseModel
from app.schemas.delete_check import DeleteCheckResponse
from app.services.master_data_delete_service import ensure_can_delete, log_record_deleted, run_delete_check


class EmptyFilters(BaseModel):
    pass


class ContactFilters(BaseModel):
    customer_id: UUID | None = None


class TaskTypeFilters(BaseModel):
    stream_id: UUID | None = None


class ProjectFilters(BaseModel):
    customer_id: UUID | None = None
    customer_ids: list[UUID] | None = None
    customer_contact_id: UUID | None = None
    design_leader_id: UUID | None = None
    designer_id: UUID | None = None
    surfacer_id: UUID | None = None
    stream_id: UUID | None = None
    team_id: UUID | None = None
    team_ids: list[UUID] | None = None
    project_type_id: UUID | None = None
    execution_status: ExecutionStatus | None = None
    project_stage: ProjectStage | None = None
    lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all


class MilestoneFilters(BaseModel):
    project_id: UUID | None = None


class TimesheetFilters(BaseModel):
    user_id: UUID | None = None
    status: TimesheetStatus | None = None


class TimesheetEntryFilters(BaseModel):
    timesheet_id: UUID | None = None
    project_id: UUID | None = None


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


def _record_display_name(db_obj: object) -> str:
    for attr in ("name", "code", "email"):
        value = getattr(db_obj, attr, None)
        if value:
            return str(value)
    first_name = getattr(db_obj, "first_name", None)
    last_name = getattr(db_obj, "last_name", None)
    if first_name or last_name:
        return f"{first_name or ''} {last_name or ''}".strip()
    return str(getattr(db_obj, "id", "record"))


def build_crud_router(
    *,
    prefix: str,
    tags: list[str],
    crud: CRUDBase[Any, Any, Any],
    schema_read: type[BaseModel],
    schema_create: type[BaseModel],
    schema_update: type[BaseModel],
    filters_model: type[BaseModel] = EmptyFilters,
    write_roles: tuple[str, ...] = ("Admin", "Engineering Manager"),
    router_dependencies: Sequence[Any] | None = None,
    delete_entity: str | None = None,
) -> APIRouter:
    dependencies = list(router_dependencies or [Depends(get_current_user)])
    write_dependency = Depends(require_roles(*write_roles))
    admin_delete_dependency = Depends(require_roles("Admin"))

    router = APIRouter(prefix=prefix, tags=tags, dependencies=dependencies)  # type: ignore[arg-type]

    @router.get("", response_model=list[schema_read])
    def list_records(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        filters: filters_model = Depends(),  # type: ignore[valid-type]
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

    if delete_entity is not None:

        @router.get(
            "/{record_id}/delete-check",
            response_model=DeleteCheckResponse,
            dependencies=[admin_delete_dependency],
        )
        def delete_check(record_id: UUID, db: Session = Depends(get_db)):
            try:
                return run_delete_check(db, delete_entity, record_id)
            except ProTrackValidationError as exc:
                raise _handle_validation(exc) from exc

    @router.post(
        "",
        response_model=schema_read,
        status_code=status.HTTP_201_CREATED,
        dependencies=[write_dependency],
    )
    def create_record(obj_in: schema_create, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        return crud.create(db, obj_in=obj_in)

    @router.patch(
        "/{record_id}",
        response_model=schema_read,
        dependencies=[write_dependency],
    )
    def update_record(
        record_id: UUID,
        obj_in: schema_update,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
    ):
        db_obj = get_object_or_404(crud, db, record_id)
        return crud.update(db, db_obj=db_obj, obj_in=obj_in)

    @router.delete(
        "/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[admin_delete_dependency],
    )
    def delete_record(
        record_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        db_obj = get_object_or_404(crud, db, record_id)
        record_name = _record_display_name(db_obj)
        if delete_entity is not None:
            try:
                ensure_can_delete(db, delete_entity, record_id)
            except ProTrackValidationError as exc:
                raise _handle_validation(exc) from exc
        deleted = crud.delete(db, record_id=record_id)
        if deleted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
            )
        if delete_entity is not None:
            log_record_deleted(
                db,
                user=current_user,
                entity_key=delete_entity,
                record_id=record_id,
                record_name=record_name,
            )

    return router
