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
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    can_edit_milestone,
    can_read_project,
    can_update_milestone_progress,
    can_write_milestones,
)
from app.crud.milestone import milestone
from app.models.models import Milestone, Project, User
from app.schemas.project import (
    MilestoneCreate,
    MilestoneRead,
    MilestoneReorderRequest,
    MilestoneUpdate,
    ProjectMilestoneSummary,
)
from app.services.milestone_workspace_service import (
    enrich_milestone_read,
    get_project_milestone_summary,
    reorder_milestones,
)

router = APIRouter(
    prefix="/milestones",
    tags=["milestones"],
    dependencies=[Depends(get_current_user)],
)

_PROGRESS_ONLY_FIELDS = frozenset(
    {"progress_percent", "status", "due_date", "qa_acknowledged"}
)


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _milestone_to_read(db: Session, row: Milestone) -> MilestoneRead:
    return enrich_milestone_read(db, row)


@router.get("", response_model=list[MilestoneRead])
def list_milestones(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: MilestoneFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_filters = {
        key: value
        for key, value in filters.model_dump().items()
        if value is not None
    }
    if filters.project_id is not None:
        db_project = db.get(Project, filters.project_id)
        if db_project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_read_project(db, current_user, db_project):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    rows = milestone.get_multi(db, skip=skip, limit=limit, filters=active_filters)
    return [_milestone_to_read(db, row) for row in rows]


@router.get("/summary/{project_id}", response_model=ProjectMilestoneSummary)
def get_milestone_summary(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = db.get(Project, project_id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return get_project_milestone_summary(db, project_id)


@router.get("/{record_id}", response_model=MilestoneRead)
def get_milestone(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(milestone, db, record_id)
    if not can_read_project(db, current_user, db_obj.project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return _milestone_to_read(db, db_obj)


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
    created = milestone.create(db, obj_in=obj_in, actor=current_user)
    return _milestone_to_read(db, created)


@router.post("/reorder", response_model=list[MilestoneRead])
def reorder_project_milestones(
    payload: MilestoneReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = db.get(Project, payload.project_id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not can_write_milestones(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    rows = reorder_milestones(
        db,
        project_id=payload.project_id,
        items=[(item.id, item.sort_order) for item in payload.items],
        actor=current_user,
    )
    return [_milestone_to_read(db, row) for row in rows]


@router.patch("/{record_id}", response_model=MilestoneRead)
def update_milestone(
    record_id: UUID,
    obj_in: MilestoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_obj = get_object_or_404(milestone, db, record_id)
    update_fields = set(obj_in.model_dump(exclude_unset=True).keys())
    if can_edit_milestone(db, current_user, db_obj.project, db_obj):
        allowed = True
    elif can_update_milestone_progress(db, current_user, db_obj.project, db_obj):
        allowed = update_fields.issubset(_PROGRESS_ONLY_FIELDS)
    else:
        allowed = False
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        updated = milestone.update(db, db_obj=db_obj, obj_in=obj_in, actor=current_user)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return _milestone_to_read(db, updated)


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
    milestone.delete(db, record_id=record_id, actor=current_user)
