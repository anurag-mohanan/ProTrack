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
from app.crud.command_center import (
    clone_project,
    engineering_change,
    project_decision,
    update_project_folders,
)
from app.crud import project
from app.crud.dashboard import get_project_dashboard
from app.models.enums import ActivityAction, EntityType, ExecutionStatus, ProjectLifecycleFilter, ProjectStage
from app.models.models import User
from app.schemas.command_center import (
    EngineeringChangeCreate,
    EngineeringChangeRead,
    EngineeringChangeUpdate,
    ProjectCommandCenter,
    ProjectDecisionCreate,
    ProjectDecisionRead,
    ProjectDecisionUpdate,
    ProjectFolderPaths,
    ProjectFolderPathsUpdate,
)
from app.schemas.dashboard import ProjectDashboard
from app.schemas.project import (
    ArchivedProjectListItem,
    ProjectCreate,
    ProjectDeleteCheck,
    ProjectRead,
    ProjectUpdate,
)
from app.services.activity_service import log_activity
from app.services.command_center_service import get_project_command_center
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


def _normalize_project_filters(filters: ProjectFilters) -> tuple[ProjectLifecycleFilter, dict[str, object]]:
    data = filters.model_dump()
    lifecycle = data.pop("lifecycle", ProjectLifecycleFilter.all)

    customer_ids = list(data.pop("customer_ids") or [])
    if data.get("customer_id"):
        cid = data.pop("customer_id")
        if cid not in customer_ids:
            customer_ids.append(cid)
    else:
        data.pop("customer_id", None)
    if customer_ids:
        data["customer_ids"] = customer_ids

    team_ids = list(data.pop("team_ids") or [])
    if data.get("team_id"):
        tid = data.pop("team_id")
        if tid not in team_ids:
            team_ids.append(tid)
    else:
        data.pop("team_id", None)
    if team_ids:
        data["team_ids"] = team_ids

    active_filters = {key: value for key, value in data.items() if value is not None}
    return lifecycle, active_filters


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

    lifecycle, active_filters = _normalize_project_filters(filters)
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
    customer_id: UUID | None = None,
    customer_ids: list[UUID] | None = Query(None),
    customer_contact_id: UUID | None = None,
    design_leader_id: UUID | None = None,
    designer_id: UUID | None = None,
    surfacer_id: UUID | None = None,
    stream_id: UUID | None = None,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = Query(None),
    project_type_id: UUID | None = None,
    execution_status: ExecutionStatus | None = None,
    project_stage: ProjectStage | None = None,
    lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = ProjectFilters(
        customer_id=customer_id,
        customer_ids=customer_ids,
        customer_contact_id=customer_contact_id,
        design_leader_id=design_leader_id,
        designer_id=designer_id,
        surfacer_id=surfacer_id,
        stream_id=stream_id,
        team_id=team_id,
        team_ids=team_ids,
        project_type_id=project_type_id,
        execution_status=execution_status,
        project_stage=project_stage,
        lifecycle=lifecycle,
    )
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


@router.get("/{record_id}/command-center", response_model=ProjectCommandCenter)
def get_project_command_center_endpoint(
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
    result = get_project_command_center(db, record_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return result


@router.post("/{record_id}/clone", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def clone_project_endpoint(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_create_project(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        cloned = clone_project(db, db_project)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=cloned.id,
            action=ActivityAction.project_created,
            new_value=cloned.code,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return project.get_read(db, cloned.id)


@router.patch("/{record_id}/folders", response_model=ProjectFolderPaths)
def update_project_folders_endpoint(
    record_id: UUID,
    payload: ProjectFolderPathsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    updated = update_project_folders(db, db_project, payload)
    from app.services.command_center_service import _resolve_folders

    return _resolve_folders(db, updated)


@router.get("/{record_id}/decisions", response_model=list[ProjectDecisionRead])
def list_project_decisions(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return project_decision.list_for_project(db, record_id)


@router.post(
    "/{record_id}/decisions",
    response_model=ProjectDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_decision(
    record_id: UUID,
    payload: ProjectDecisionCreate,
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
        return project_decision.create(
            db, project_id=record_id, user_id=current_user.id, obj_in=payload
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch("/{record_id}/decisions/{decision_id}", response_model=ProjectDecisionRead)
def update_project_decision(
    record_id: UUID,
    decision_id: UUID,
    payload: ProjectDecisionUpdate,
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
        row = project_decision.update(
            db, decision_id=decision_id, project_id=record_id, obj_in=payload
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return row


@router.delete("/{record_id}/decisions/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_decision(
    record_id: UUID,
    decision_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    if not project_decision.delete(db, decision_id=decision_id, project_id=record_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")


@router.post(
    "/{record_id}/engineering-changes",
    response_model=EngineeringChangeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_engineering_change(
    record_id: UUID,
    payload: EngineeringChangeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    row = engineering_change.create(db, project_id=record_id, obj_in=payload)
    return EngineeringChangeRead.model_validate(row, from_attributes=True)


@router.patch(
    "/{record_id}/engineering-changes/{ec_id}",
    response_model=EngineeringChangeRead,
)
def update_engineering_change(
    record_id: UUID,
    ec_id: UUID,
    payload: EngineeringChangeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    row = engineering_change.update(
        db, ec_id=ec_id, project_id=record_id, obj_in=payload
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Engineering change not found"
        )
    return EngineeringChangeRead.model_validate(row, from_attributes=True)


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
