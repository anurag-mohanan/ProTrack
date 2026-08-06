# pyright: reportInvalidTypeForm=false, reportArgumentType=false

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_module_action, require_roles
from app.core.module_actions import MODULE_ACTION_VIEW
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse, pagination_query, PaginationParams
from app.crud.base import CRUDBase
from app.models.enums import (
    ExecutionStatus,
    ProjectHealth,
    ProjectLifecycleFilter,
    ProjectPriority,
    ProjectStage,
    TimesheetStatus,
)
from app.models.models import User
from app.schemas.common import BaseModel
from app.schemas.delete_check import DeleteCheckResponse
from app.services.master_data_delete_service import ensure_can_delete, log_record_deleted, run_delete_check


class EmptyFilters(BaseModel):
    pass


class CustomerFilters(BaseModel):
    search: str | None = None
    is_active: bool | None = None


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
    stream_ids: list[UUID] | None = None
    workstream_ids: list[UUID] | None = None
    team_id: UUID | None = None
    team_ids: list[UUID] | None = None
    project_type_id: UUID | None = None
    execution_status: ExecutionStatus | None = None
    project_stage: ProjectStage | None = None
    health: ProjectHealth | None = None
    priority: ProjectPriority | None = None
    q: str | None = None
    due: str | None = None  # week | overdue | 7days
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
        status_code=exc.status_code,
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
    read_module: str | None = None,
) -> APIRouter:
    dependencies = list(router_dependencies or [Depends(get_current_user)])
    write_dependency = Depends(require_roles(*write_roles))
    admin_delete_dependency = Depends(require_roles("Admin"))
    # Optional module-view gate for read routes (enterprise action-based RBAC).
    # When unset, reads remain authenticated-only (prior behaviour) so shared
    # lookup data used across pages is not accidentally locked out.
    read_dependencies = (
        [Depends(require_module_action(read_module, MODULE_ACTION_VIEW))]
        if read_module
        else []
    )

    router = APIRouter(prefix=prefix, tags=tags, dependencies=dependencies)  # type: ignore[arg-type]

    @router.get(
        "",
        response_model=PaginatedResponse[schema_read],
        dependencies=read_dependencies,
    )
    def list_records(
        pagination: PaginationParams = Depends(pagination_query),
        filters: filters_model = Depends(),  # type: ignore[valid-type]
        db: Session = Depends(get_db),
    ):
        active_filters = {
            key: value
            for key, value in filters.model_dump().items()
            if value is not None
        }
        return crud.get_multi_paginated(
            db,
            page=pagination.page,
            page_size=pagination.page_size,
            skip=pagination.skip,
            limit=pagination.limit,
            filters=active_filters,
            sort=pagination.sort,
        )

    @router.get(
        "/{record_id}",
        response_model=schema_read,
        dependencies=read_dependencies,
    )
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
        try:
            return crud.create(db, obj_in=obj_in)
        except ProTrackValidationError as exc:
            raise _handle_validation(exc) from exc

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
        try:
            return crud.update(db, db_obj=db_obj, obj_in=obj_in)
        except ProTrackValidationError as exc:
            raise _handle_validation(exc) from exc

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
