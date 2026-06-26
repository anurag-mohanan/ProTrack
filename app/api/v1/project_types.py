from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db, get_object_or_404
from app.crud import project_type as project_type_crud
from app.schemas.templates import (
    ProjectTypeCreate,
    ProjectTypeRead,
    ProjectTypeUpdate,
)

router = APIRouter(
    prefix="/project-types",
    tags=["project-types"],
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)


@router.get("", response_model=list[ProjectTypeRead])
def list_project_types(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return project_type_crud.get_multi(db, skip=skip, limit=limit)


@router.get("/{record_id}", response_model=ProjectTypeRead)
def get_project_type(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(project_type_crud, db, record_id)


@router.post(
    "",
    response_model=ProjectTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)
def create_project_type(obj_in: ProjectTypeCreate, db: Session = Depends(get_db)):
    return project_type_crud.create(db, obj_in=obj_in)


@router.patch(
    "/{record_id}",
    response_model=ProjectTypeRead,
    dependencies=[Depends(require_roles("Admin", "Engineering Manager"))],
)
def update_project_type(
    record_id: UUID,
    obj_in: ProjectTypeUpdate,
    db: Session = Depends(get_db),
):
    db_obj = get_object_or_404(project_type_crud, db, record_id)
    return project_type_crud.update(db, db_obj=db_obj, obj_in=obj_in)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_type(record_id: UUID, db: Session = Depends(get_db)):
    db_obj = get_object_or_404(project_type_crud, db, record_id)
    deleted = project_type_crud.delete(db, record_id=db_obj.id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
