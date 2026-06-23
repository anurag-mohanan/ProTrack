from uuid import UUID

from app.api.auth_deps import get_current_user
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
from app.core.permissions import (
    READ_ALL_PROJECT_ROLES,
    can_create_project,
    can_delete_project,
    can_read_project,
    can_update_project,
    get_role_name,
    project_assignment_filter,
)
from app.crud import project
from app.crud.project_metrics import build_project_read
from app.models.models import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: ProjectFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_filters = {
        key: value
        for key, value in filters.model_dump().items()
        if value is not None
    }
    role_name = get_role_name(db, current_user)
    if role_name not in READ_ALL_PROJECT_ROLES:
        assignment = project_assignment_filter(current_user, role_name)
        if assignment is None:
            return []
        rows = project.get_multi(db, skip=skip, limit=limit, filters=active_filters)
        rows = [row for row in rows if can_read_project(db, current_user, row)]
        return [build_project_read(db, row) for row in rows]

    return project.get_multi_read(
        db, skip=skip, limit=limit, filters=active_filters
    )


@router.get("/{record_id}", response_model=ProjectRead)
def get_project(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = project.get(db, record_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return project.get_read(db, record_id)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    obj_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_create_project(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_obj = project.create(db, obj_in=obj_in)
    return project.get_read(db, db_obj.id)


@router.patch("/{record_id}", response_model=ProjectRead)
def update_project(
    record_id: UUID,
    obj_in: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    project.update(db, db_obj=db_project, obj_in=obj_in)
    return project.get_read(db, record_id)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = project.get(db, record_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    if not can_delete_project(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    project.delete(db, record_id=record_id)
