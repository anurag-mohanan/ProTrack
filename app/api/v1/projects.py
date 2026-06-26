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
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    READ_ALL_PROJECT_ROLES,
    can_archive_project,
    can_create_project,
    can_read_project,
    can_soft_delete_project,
    can_update_project,
    can_view_deleted_projects,
    get_role_name,
    project_assignment_filter,
)
from app.crud import project
from app.crud.dashboard import get_project_dashboard
from app.models.enums import ActivityAction, EntityType, ProjectLifecycleFilter
from app.models.models import User
from app.schemas.dashboard import ProjectDashboard
from app.schemas.project import (
    ArchivedProjectListItem,
    ProjectCreate,
    ProjectDeleteCheck,
    ProjectRead,
    ProjectUpdate,
)
from app.services.activity_service import log_activity
from app.services.project_lifecycle_service import (
    archive_project,
    get_project_delete_dependencies,
    permanent_delete_project,
    restore_project_from_archive,
    restore_project_from_deleted,
    soft_delete_project,
)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


def _list_projects(
    db: Session,
    current_user: User,
    *,
    skip: int,
    limit: int,
    filters: ProjectFilters,
) -> list[ProjectRead]:
    if filters.lifecycle == ProjectLifecycleFilter.deleted:
        if not can_view_deleted_projects(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    active_filters = {
        key: value
        for key, value in filters.model_dump().items()
        if value is not None
    }
    lifecycle = filters.lifecycle
    role_name = get_role_name(db, current_user)
    assignment_clause = None
    if role_name not in READ_ALL_PROJECT_ROLES:
        assignment_clause = project_assignment_filter(current_user, role_name)
        if assignment_clause is None:
            return []

    rows = project.query_projects(
        db,
        lifecycle=lifecycle,
        skip=skip,
        limit=limit,
        filters=active_filters,
        assignment_clause=assignment_clause,
    )
    if role_name not in READ_ALL_PROJECT_ROLES:
        rows = [row for row in rows if can_read_project(db, current_user, row)]
    from app.crud.project_metrics import build_project_reads

    return build_project_reads(db, rows)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filters: ProjectFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list_projects(db, current_user, skip=skip, limit=limit, filters=filters)


@router.get("/archived", response_model=list[ArchivedProjectListItem])
def list_archived_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_name = get_role_name(db, current_user)
    assignment_clause = None
    if role_name not in READ_ALL_PROJECT_ROLES:
        assignment_clause = project_assignment_filter(current_user, role_name)
        if assignment_clause is None:
            return []
    items = project.get_archived_list(
        db, skip=skip, limit=limit, assignment_clause=assignment_clause
    )
    if role_name not in READ_ALL_PROJECT_ROLES:
        return [
            item
            for item in items
            if can_read_project(db, current_user, project.get(db, item.id))
        ]
    return items


@router.get("/deleted", response_model=list[ProjectRead])
def list_deleted_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_view_deleted_projects(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    filters = ProjectFilters(lifecycle=ProjectLifecycleFilter.deleted)
    return _list_projects(db, current_user, skip=skip, limit=limit, filters=filters)


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


@router.get("/{record_id}/detail", response_model=ProjectDashboard)
def get_project_detail(
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
    result = get_project_dashboard(db, record_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return result


@router.get("/{record_id}/delete-check", response_model=ProjectDeleteCheck)
def check_project_delete(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_view_deleted_projects(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_project = project.get(db, record_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    deps = get_project_delete_dependencies(db, record_id)
    blockers = deps.blocker_messages()
    return ProjectDeleteCheck(
        can_permanently_delete=not deps.has_blockers,
        blockers=blockers,
    )


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
    try:
        db_obj = project.create(db, obj_in=obj_in)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=db_obj.id,
            action=ActivityAction.project_created,
            new_value=db_obj.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
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
    try:
        project.update(db, db_obj=db_project, obj_in=obj_in)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=db_project.id,
            action=ActivityAction.project_updated,
            new_value=db_project.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, record_id)


@router.post("/{record_id}/archive", response_model=ProjectRead)
def archive_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_archive_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        archived = archive_project(db, record_id, current_user)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=archived.id,
            action=ActivityAction.project_archived,
            new_value=archived.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, record_id)


@router.post("/{record_id}/restore", response_model=ProjectRead)
def restore_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        restored = restore_project_from_archive(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=restored.id,
            action=ActivityAction.project_restored,
            new_value=restored.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, record_id)


@router.post("/{record_id}/soft-delete", response_model=ProjectRead)
def soft_delete_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_soft_delete_project(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_project = get_object_or_404(project, db, record_id)
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        deleted = soft_delete_project(db, record_id, current_user)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=deleted.id,
            action=ActivityAction.project_deleted,
            new_value=deleted.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, record_id)


@router.post("/{record_id}/restore-deleted", response_model=ProjectRead)
def restore_deleted_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_view_deleted_projects(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        restored = restore_project_from_deleted(db, record_id)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=restored.id,
            action=ActivityAction.project_restored_from_deleted,
            new_value=restored.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, record_id)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_project_legacy(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a project (legacy route; prefer POST /soft-delete)."""
    if not can_soft_delete_project(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    db_project = get_object_or_404(project, db, record_id)
    try:
        deleted = soft_delete_project(db, record_id, current_user)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=deleted.id,
            action=ActivityAction.project_deleted,
            new_value=deleted.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.delete("/{record_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_view_deleted_projects(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        permanent_delete_project(db, record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
