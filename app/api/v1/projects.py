import json
import logging
from fastapi import File, UploadFile
from pydantic import BaseModel
from uuid import UUID

from app.services.project_template_service import (
    apply_template_to_project,
    resolve_template,
)

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
from app.core.pagination import PaginatedResponse, pagination_query, PaginationParams
from app.api.v1.router_factory import ProjectFilters
from app.core.exceptions import ProTrackValidationError
from app.core.uploads import enforce_upload_size
from app.core.permissions import (
    can_archive_project,
    can_create_project,
    can_read_project,
    can_soft_delete_project,
    can_update_project,
    can_view_deleted_projects,
)
from app.crud.command_center import (
    clone_project,
    engineering_change,
    project_decision,
    update_project_folders,
)
from app.crud import project
from app.crud.dashboard import get_project_dashboard
from app.models.enums import (
    ActivityAction,
    EntityType,
    ExecutionStatus,
    ProjectHealth,
    ProjectLifecycleFilter,
    ProjectPriority,
    ProjectStage,
)
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
    WorkorderPdfExtractResult,
)
from app.schemas.workstream import (
    ProjectPortfolioSummary,
    ProjectSavedViewCreate,
    ProjectSavedViewRead,
    ProjectSavedViewUpdate,
    ProjectWorkstreamRead,
    ProjectWorkstreamsReplace,
)
from app.schemas.communication import EmailMessageRead
from app.services.email.engine import list_email_messages
from app.services.command_center_service import get_project_command_center
from app.services.activity_service import log_activity
from app.services.workorder_pdf_extract import extract_workorder_fields_from_file
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

logger = logging.getLogger(__name__)


class ApplyProjectTemplateRequest(BaseModel):
    project_template_id: UUID | None = None
    # Quote/shell projects may have no type yet; allow setting it when applying.
    project_type_id: UUID | None = None


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    logger.info("Project validation error: %s", exc.detail)
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

    stream_ids = list(data.pop("stream_ids") or [])
    if data.get("stream_id"):
        sid = data.pop("stream_id")
        if sid not in stream_ids:
            stream_ids.append(sid)
    else:
        data.pop("stream_id", None)
    if stream_ids:
        data["stream_ids"] = stream_ids

    workstream_ids = list(data.pop("workstream_ids") or [])
    if workstream_ids:
        data["workstream_ids"] = workstream_ids

    active_filters = {key: value for key, value in data.items() if value is not None}
    return lifecycle, active_filters


def _list_projects(
    db: Session,
    current_user: User,
    *,
    pagination: PaginationParams,
    filters: ProjectFilters,
) -> PaginatedResponse[ProjectRead]:
    if filters.lifecycle == ProjectLifecycleFilter.deleted:
        if not can_view_deleted_projects(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    lifecycle, active_filters = _normalize_project_filters(filters)
    from app.core.team_access import project_visibility_clause

    visibility_clause = project_visibility_clause(db, current_user)

    total = project.count_projects(
        db,
        lifecycle=lifecycle,
        filters=active_filters,
        assignment_clause=visibility_clause,
    )
    rows = project.query_projects(
        db,
        lifecycle=lifecycle,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=active_filters,
        assignment_clause=visibility_clause,
    )
    rows = [row for row in rows if can_read_project(db, current_user, row)]
    from app.crud.project_metrics import build_project_reads

    items = build_project_reads(db, rows)
    return PaginatedResponse.build(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("", response_model=PaginatedResponse[ProjectRead])
def list_projects(
    pagination: PaginationParams = Depends(pagination_query),
    customer_id: UUID | None = None,
    customer_ids: list[UUID] | None = Query(None),
    customer_contact_id: UUID | None = None,
    design_leader_id: UUID | None = None,
    designer_id: UUID | None = None,
    surfacer_id: UUID | None = None,
    stream_id: UUID | None = None,
    stream_ids: list[UUID] | None = Query(None),
    workstream_ids: list[UUID] | None = Query(None),
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = Query(None),
    project_type_id: UUID | None = None,
    execution_status: ExecutionStatus | None = None,
    project_stage: ProjectStage | None = None,
    health: ProjectHealth | None = None,
    priority: ProjectPriority | None = None,
    q: str | None = None,
    due: str | None = None,
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
        stream_ids=stream_ids,
        workstream_ids=workstream_ids,
        team_id=team_id,
        team_ids=team_ids,
        project_type_id=project_type_id,
        execution_status=execution_status,
        project_stage=project_stage,
        health=health,
        priority=priority,
        q=q,
        due=due,
        lifecycle=lifecycle,
    )
    return _list_projects(db, current_user, pagination=pagination, filters=filters)


@router.get("/archived", response_model=PaginatedResponse[ArchivedProjectListItem])
def list_archived_projects(
    pagination: PaginationParams = Depends(pagination_query),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.team_access import project_visibility_clause

    visibility_clause = project_visibility_clause(db, current_user)
    total = project.count_projects(
        db,
        lifecycle=ProjectLifecycleFilter.archived,
        assignment_clause=visibility_clause,
    )
    items = project.get_archived_list(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        assignment_clause=visibility_clause,
    )
    items = [
        item
        for item in items
        if can_read_project(db, current_user, project.get(db, item.id))
    ]
    return PaginatedResponse.build(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/deleted", response_model=PaginatedResponse[ProjectRead])
def list_deleted_projects(
    pagination: PaginationParams = Depends(pagination_query),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = ProjectFilters(lifecycle=ProjectLifecycleFilter.deleted)
    return _list_projects(db, current_user, pagination=pagination, filters=filters)


@router.get("/summary", response_model=ProjectPortfolioSummary)
def projects_summary(
    customer_id: UUID | None = None,
    customer_ids: list[UUID] | None = Query(None),
    stream_id: UUID | None = None,
    stream_ids: list[UUID] | None = Query(None),
    workstream_ids: list[UUID] | None = Query(None),
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = Query(None),
    project_type_id: UUID | None = None,
    execution_status: ExecutionStatus | None = None,
    project_stage: ProjectStage | None = None,
    health: ProjectHealth | None = None,
    priority: ProjectPriority | None = None,
    q: str | None = None,
    due: str | None = None,
    lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.active,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.core.team_access import project_visibility_clause
    from app.models.workstream import ProjectWorkstream

    filters = ProjectFilters(
        customer_id=customer_id,
        customer_ids=customer_ids,
        stream_id=stream_id,
        stream_ids=stream_ids,
        workstream_ids=workstream_ids,
        team_id=team_id,
        team_ids=team_ids,
        project_type_id=project_type_id,
        execution_status=execution_status,
        project_stage=project_stage,
        health=health,
        priority=priority,
        q=q,
        due=due,
        lifecycle=lifecycle,
    )
    lifecycle_f, active_filters = _normalize_project_filters(filters)
    visibility_clause = project_visibility_clause(db, current_user)
    rows = project.query_projects(
        db,
        lifecycle=lifecycle_f,
        skip=0,
        limit=5000,
        filters=active_filters,
        assignment_clause=visibility_clause,
    )
    rows = [row for row in rows if can_read_project(db, current_user, row)]
    today = date.today()
    week_end = today + timedelta(days=7)
    active_count = 0
    due_week = 0
    overdue = 0
    at_risk = 0
    for row in rows:
        if row.execution_status not in (ExecutionStatus.completed, ExecutionStatus.cancelled):
            active_count += 1
            if row.due_date and today <= row.due_date <= week_end:
                due_week += 1
            if row.due_date and row.due_date < today:
                overdue += 1
            if row.health == ProjectHealth.red:
                at_risk += 1
    project_ids = [row.id for row in rows]
    estimated = Decimal("0")
    actual = Decimal("0")
    if project_ids:
        from sqlalchemy import func, select

        est = db.scalar(
            select(func.coalesce(func.sum(ProjectWorkstream.estimated_hours), 0)).where(
                ProjectWorkstream.project_id.in_(project_ids)
            )
        )
        act = db.scalar(
            select(func.coalesce(func.sum(ProjectWorkstream.actual_hours), 0)).where(
                ProjectWorkstream.project_id.in_(project_ids)
            )
        )
        estimated = Decimal(str(est or 0))
        actual = Decimal(str(act or 0))
        if estimated == 0:
            estimated = sum((row.current_planned_hours or Decimal("0")) for row in rows)
            actual = sum((row.actual_hours or Decimal("0")) for row in rows)
    return ProjectPortfolioSummary(
        active_count=active_count,
        due_week_count=due_week,
        overdue_count=overdue,
        at_risk_count=at_risk,
        estimated_hours=estimated,
        actual_hours=actual,
        remaining_hours=estimated - actual,
    )


@router.get("/views", response_model=list[ProjectSavedViewRead])
def list_project_views(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import list_saved_views

    return list_saved_views(db, current_user)


@router.post(
    "/views",
    response_model=ProjectSavedViewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_view(
    payload: ProjectSavedViewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import create_saved_view

    try:
        return create_saved_view(db, current_user, payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch("/views/{view_id}", response_model=ProjectSavedViewRead)
def update_project_view(
    view_id: UUID,
    payload: ProjectSavedViewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import update_saved_view

    try:
        return update_saved_view(db, current_user, view_id, payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import delete_saved_view

    try:
        delete_saved_view(db, current_user, view_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


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


@router.get("/{record_id}/workstreams", response_model=list[ProjectWorkstreamRead])
def get_project_workstreams(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import list_project_workstreams

    db_project = project.get(db, record_id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return list_project_workstreams(db, record_id)


@router.put("/{record_id}/workstreams", response_model=list[ProjectWorkstreamRead])
def put_project_workstreams(
    record_id: UUID,
    payload: ProjectWorkstreamsReplace,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.workstream import replace_project_workstreams

    db_project = project.get(db, record_id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        return replace_project_workstreams(db, db_project, payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


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


@router.post(
    "/{record_id}/workorder-pdf/extract",
    response_model=WorkorderPdfExtractResult,
)
async def extract_workorder_pdf(
    record_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse a customer workorder PDF or Excel into suggested Overview fields (does not save).

    Work order number is optional. Part description is the priority field.
    """
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )
    suffix = file.filename.lower().rsplit(".", 1)[-1]
    if suffix not in {"pdf", "xlsx", "xlsm"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and Excel (.xlsx/.xlsm) workorder files are supported.",
        )
    content = await file.read()
    enforce_upload_size(content)
    try:
        extracted = extract_workorder_fields_from_file(content, filename=file.filename)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return WorkorderPdfExtractResult(
        part_description=extracted.part_description,
        work_order_number=extracted.work_order_number,
        press_tonnage=extracted.press_tonnage,
        plastic_material=extracted.plastic_material,
        cavity_count=extracted.cavity_count,
        tool_type=extracted.tool_type,
        customer_specs=extracted.customer_specs,
        warnings=extracted.warnings,
        source_chars=extracted.source_chars,
    )


@router.post("/{record_id}/apply-template", response_model=ProjectRead)
def apply_project_template_endpoint(
    record_id: UUID,
    payload: ApplyProjectTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    if db_project.project_type_id is None:
        if payload.project_type_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project type is required before applying a template",
            )
        db_project.project_type_id = payload.project_type_id
        db.add(db_project)
        db.flush()
    try:
        template = resolve_template(
            db,
            project_type_id=db_project.project_type_id,
            customer_id=db_project.customer_id,
            template_id=payload.project_template_id or db_project.project_template_id,
        )
        apply_template_to_project(db, project=db_project, template=template)
        db.commit()
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.project,
            entity_id=db_project.id,
            action=ActivityAction.project_updated,
            new_value=f"Applied template: {template.name}",
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


@router.get("/{record_id}/communications", response_model=list[EmailMessageRead])
def get_project_communications(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str | None = None,
):
    db_project = get_object_or_404(project, db, record_id)
    if not can_read_project(db, current_user, db_project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    messages = list_email_messages(db, project_id=record_id, search=search)
    return [
        EmailMessageRead(
            id=message.id,
            project_id=message.project_id,
            sent_by_user_id=message.sent_by_user_id,
            template_slug=message.template_slug,
            to_addresses=json.loads(message.to_addresses or "[]"),
            subject=message.subject,
            body_html=message.body_html,
            body_text=message.body_text,
            status=message.status,
            retry_count=message.retry_count,
            max_retries=message.max_retries,
            last_error=message.last_error,
            smtp_response=message.smtp_response,
            attachments=json.loads(message.attachment_metadata or "[]"),
            recipients_display=message.recipients_display,
            timeline_label=message.timeline_label,
            sent_at=message.sent_at,
            delivered_at=message.delivered_at,
            created_at=message.created_at,
        )
        for message in messages
    ]


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
