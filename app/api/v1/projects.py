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
from app.api.v1.router_factory import ProjectFilters
from app.crud import project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: ProjectFilters = Depends(),
    db: Session = Depends(get_db),
):
    active_filters = {
        key: value
        for key, value in filters.model_dump().items()
        if value is not None
    }
    return project.get_multi_read(
        db, skip=skip, limit=limit, filters=active_filters
    )


@router.get("/{record_id}", response_model=ProjectRead)
def get_project(record_id: UUID, db: Session = Depends(get_db)):
    db_obj = project.get_read(db, record_id)
    if db_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return db_obj


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(obj_in: ProjectCreate, db: Session = Depends(get_db)):
    db_obj = project.create(db, obj_in=obj_in)
    return project.get_read(db, db_obj.id)


@router.patch("/{record_id}", response_model=ProjectRead)
def update_project(
    record_id: UUID,
    obj_in: ProjectUpdate,
    db: Session = Depends(get_db),
):
    db_project = get_object_or_404(project, db, record_id)
    project.update(db, db_obj=db_project, obj_in=obj_in)
    return project.get_read(db, record_id)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(record_id: UUID, db: Session = Depends(get_db)):
    deleted = project.delete(db, record_id=record_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
