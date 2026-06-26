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
from app.api.v1.router_factory import MilestoneFilters
from app.core.permissions import can_write_milestones
from app.crud.milestone import milestone
from app.models.models import Project, User
from app.schemas.project import MilestoneCreate, MilestoneRead, MilestoneUpdate

router = APIRouter(
    prefix="/milestones",
    tags=["milestones"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[MilestoneRead])
def list_milestones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: MilestoneFilters = Depends(),
    db: Session = Depends(get_db),
):
    active_filters = {
        key: value
        for key, value in filters.model_dump().items()
        if value is not None
    }
    return milestone.get_multi(db, skip=skip, limit=limit, filters=active_filters)


@router.get("/{record_id}", response_model=MilestoneRead)
def get_milestone(record_id: UUID, db: Session = Depends(get_db)):
    return get_object_or_404(milestone, db, record_id)


@router.post("", response_model=MilestoneRead, status_code=status.HTTP_201_CREATED)
def create_milestone(
    obj_in: MilestoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = db.get(Project, obj_in.project_id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not can_write_milestones(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return milestone.create(db, obj_in=obj_in)


@router.patch("/{record_id}", response_model=MilestoneRead)
def update_milestone(
    record_id: UUID,
    obj_in: MilestoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(milestone, db, record_id)
    if not can_write_milestones(db, current_user, db_obj.project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return milestone.update(db, db_obj=db_obj, obj_in=obj_in, actor=current_user)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = milestone.get(db, record_id)
    if db_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    if not can_write_milestones(db, current_user, db_obj.project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    milestone.delete(db, record_id=record_id)
