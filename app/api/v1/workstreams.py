"""Workstream master-data API (admin write; authenticated read)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse, pagination_query, PaginationParams
from app.crud.workstream import workstream
from app.models.models import User
from app.schemas.workstream import WorkstreamCreate, WorkstreamRead, WorkstreamUpdate

router = APIRouter(
    prefix="/workstreams",
    tags=["workstreams"],
    dependencies=[Depends(get_current_user)],
)

admin_write = Depends(require_roles("Admin"))


@router.get("", response_model=PaginatedResponse[WorkstreamRead])
def list_workstreams(
    pagination: PaginationParams = Depends(pagination_query),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user  # authenticated via dependency
    filters: dict = {}
    if is_active is not None:
        filters["is_active"] = is_active
    return workstream.get_multi_paginated(
        db,
        page=pagination.page,
        page_size=pagination.page_size,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=filters,
        sort=pagination.sort or "display_order",
    )


@router.get("/{record_id}", response_model=WorkstreamRead)
def get_workstream(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(workstream, db, record_id)


@router.post(
    "",
    response_model=WorkstreamRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[admin_write],
)
def create_workstream(obj_in: WorkstreamCreate, db: Session = Depends(get_db)):
    return workstream.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=WorkstreamRead,
    dependencies=[admin_write],
)
def update_workstream(
    record_id: UUID, obj_in: WorkstreamUpdate, db: Session = Depends(get_db)
):
    db_obj = get_object_or_404(workstream, db, record_id)
    return workstream.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete(
    "/{record_id}",
    response_model=WorkstreamRead,
    dependencies=[admin_write],
)
def delete_workstream(record_id: UUID, db: Session = Depends(get_db)):
    try:
        deleted = workstream.delete(db, record_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.detail
        ) from exc
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return deleted
