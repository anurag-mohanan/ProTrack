from uuid import UUID
from datetime import date

from fastapi import Query

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import APIRouter, Depends, HTTPException, Session, get_db, get_object_or_404, status
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import can_update_project, FULL_ACCESS_ROLES, DESIGN_LEADER, get_role_name, normalize_role_name
from app.core.team_access import resolve_team_scope
from app.crud import project as project_crud
from app.crud.dashboard import (
    get_dashboard_overview,
    get_dashboard_summary,
    get_designer_workload,
    get_project_dashboard,
    get_workflow_dashboard,
)
from app.models.enums import NotificationType, ProjectStage
from app.models.models import User
from app.schemas.dashboard import (
    DashboardKpis,
    DashboardMyTasks,
    DashboardOverview,
    DashboardSummary,
    DesignerWorkload,
    ProjectAttentionRow,
    ProjectDashboard,
    WorkflowDashboard,
)
from app.schemas.timesheet import ActivityRead
from app.schemas.reports import TeamResourcePlanningRow
from app.schemas.resource_planning import (
    ResourceITGaps,
    ResourceITMatrix,
    ResourcePlanningAssignRequest,
    ResourcePlanningGranularity,
    ResourcePlanningGrid,
)
from app.schemas.it_operations import (
    ResourcePackageAssignRequest,
    ResourcePackagePreviewRequest,
    ResourcePackageRead,
)
from app.core.access_control import (
    MODULE_IT_OPERATIONS,
    MODULE_RESOURCE_PLANNING,
    SPECIAL_ALLOCATE_IT_IPS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_ASSIGN_RESOURCE_SHIFTS,
    SPECIAL_MANAGE_IT_SOFTWARE,
    SPECIAL_VIEW_IT_OPERATIONS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
    user_has_module,
    user_has_special,
)
from app.services import resource_it_gap_service
from app.services import resource_package_service
from app.services.resource_shift_service import ShiftConflictError, ShiftValidationError
from app.crud.team_reports import get_team_resource_planning
from app.services.notification_service import create_notification
from app.services.resource_planning_service import get_resource_planning_grid
from app.schemas.kpi import RoleKpiSnapshot
from app.services.kpi_engine import get_administration_kpis, get_leadership_scope, get_management_kpis
from app.services.kpi_participation import (
    capacity_planning_users,
    engineering_productivity_users,
    get_user_dashboard_profile,
    is_administration_user,
    is_management_user,
)
from app.services.dashboard_service import (
    get_attention_projects,
    get_dashboard_kpis,
    get_dashboard_my_tasks,
    get_dashboard_recent_activity,
    safe_dashboard_call,
)

_workload_access = Depends(
    require_roles(
        "Admin",
        "Engineering Manager",
        "Design Leader",
        "Project Manager",
        "Planning Board",
    )
)

_planning_access = Depends(
    require_roles(
        "Admin",
        "Engineering Manager",
        "Project Manager",
        "Planning Board",
    )
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


def _require_it_readiness_access(db: Session, user: User) -> None:
    """IT readiness is shared surface: planners see it, so does IT Operations."""
    role = normalize_role_name(get_role_name(db, user))
    if (
        user_has_special(user, role, SPECIAL_VIEW_RESOURCE_PLANNING)
        or user_has_module(user, role, MODULE_RESOURCE_PLANNING)
        or user_has_special(user, role, SPECIAL_VIEW_IT_OPERATIONS)
        or user_has_module(user, role, MODULE_IT_OPERATIONS)
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires view_resource_planning or IT Operations view access.",
    )


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    project_stage: ProjectStage | None = None,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_team_ids = resolve_team_scope(
        db,
        current_user,
        team_id=team_id,
        team_ids=team_ids,
    )
    return get_dashboard_summary(
        db,
        current_user,
        project_stage=project_stage,
        team_ids=list(scoped_team_ids) if scoped_team_ids is not None else None,
    )


@router.get("/role-kpis", response_model=RoleKpiSnapshot)
def dashboard_role_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_user_dashboard_profile(current_user)
    snapshot = RoleKpiSnapshot(
        dashboard_profile=profile,
        engineering_productivity_user_count=len(engineering_productivity_users(db)),
        capacity_planning_user_count=len(capacity_planning_users(db)),
        leadership=get_leadership_scope(db, current_user),
    )
    if is_management_user(current_user) or profile == "management":
        snapshot.management = get_management_kpis(db, current_user)
    if is_administration_user(current_user) or profile == "administration":
        snapshot.administration = get_administration_kpis(db)
    return snapshot


@router.get("/kpis", response_model=DashboardKpis)
def dashboard_kpis(db: Session = Depends(get_db)):
    return safe_dashboard_call(
        "kpis",
        lambda: get_dashboard_kpis(db),
        DashboardKpis(),
    )


@router.get("/attention-projects", response_model=list[ProjectAttentionRow])
def dashboard_attention_projects(db: Session = Depends(get_db)):
    return safe_dashboard_call(
        "attention_projects",
        lambda: get_attention_projects(db, limit=25),
        [],
    )


@router.get("/recent-activity", response_model=list[ActivityRead])
def dashboard_recent_activity(db: Session = Depends(get_db)):
    return safe_dashboard_call(
        "recent_activity",
        lambda: get_dashboard_recent_activity(db, limit=20),
        [],
    )


@router.get("/my-tasks", response_model=DashboardMyTasks)
def dashboard_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return safe_dashboard_call(
        "my_tasks",
        lambda: get_dashboard_my_tasks(db, current_user),
        DashboardMyTasks(),
    )


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_overview(db, current_user)


@router.get(
    "/workload",
    response_model=list[DesignerWorkload],
    dependencies=[_workload_access],
)
def dashboard_workload(
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_team_ids = resolve_team_scope(
        db,
        current_user,
        team_id=team_id,
        team_ids=team_ids,
    )
    return get_designer_workload(
        db,
        team_ids=list(scoped_team_ids) if scoped_team_ids is not None else None,
    )


@router.get(
    "/resource-planning",
    response_model=list[TeamResourcePlanningRow],
    dependencies=[_planning_access],
)
def dashboard_resource_planning(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is None:
        return get_team_resource_planning(db, team_id=team_id)
    if team_id is not None and team_id not in scoped_team_ids:
        return []
    return get_team_resource_planning(
        db,
        team_id=team_id,
        team_ids=None if team_id is not None else list(scoped_team_ids),
    )


@router.get(
    "/resource-planning/grid",
    response_model=ResourcePlanningGrid,
    dependencies=[_planning_access],
)
def dashboard_resource_planning_grid(
    start: date | None = None,
    granularity: ResourcePlanningGranularity = ResourcePlanningGranularity.week,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is not None and team_id is not None and team_id not in scoped_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    return get_resource_planning_grid(
        db,
        start=start,
        granularity=granularity,
        team_id=team_id,
        team_ids=(
            None
            if scoped_team_ids is None or team_id is not None
            else list(scoped_team_ids)
        ),
    )


@router.get("/resource-planning/it-gaps", response_model=ResourceITGaps)
def dashboard_resource_planning_it_gaps(
    team_id: UUID | None = None,
    on_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """IT readiness gaps (computers, license compliance) for planned people."""
    _require_it_readiness_access(db, current_user)
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is not None and team_id is not None and team_id not in scoped_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    return resource_it_gap_service.get_resource_gaps(
        db,
        team_id=team_id,
        on_date=on_date,
    )


@router.get("/resource-planning/it-matrix", response_model=ResourceITMatrix)
def dashboard_resource_planning_it_matrix(
    from_date: date | None = None,
    to_date: date | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """People × computer / license readiness over a planning window."""
    _require_it_readiness_access(db, current_user)
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is not None and team_id is not None and team_id not in scoped_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    start = from_date or date.today()
    return resource_it_gap_service.get_resource_matrix(
        db,
        from_date=start,
        to_date=to_date or start,
        team_id=team_id,
    )


@router.get("/resource-planning/data-quality")
def dashboard_resource_planning_data_quality(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inventory integrity catalog for Resource Planning / IT (flags only)."""
    _require_it_readiness_access(db, current_user)
    from app.services import it_data_quality_service

    return it_data_quality_service.build_data_quality_report(db)


@router.get("/resource-planning/computers-by-shift")
def dashboard_resource_planning_computers_by_shift(
    on_date: date | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open and assigned computers bucketed by company shifts."""
    _require_it_readiness_access(db, current_user)
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is not None and team_id is not None and team_id not in scoped_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    from app.services import it_computer_shift_service

    return it_computer_shift_service.computers_by_shift(
        db, on_date=on_date, team_id=team_id
    )


@router.get("/resource-planning/workstation-capacity")
def dashboard_resource_planning_workstation_capacity(
    on_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shift-aware workstation package capacity for Resource Planning."""
    _require_it_readiness_access(db, current_user)
    from app.services import workstation_package_service as ws_packages

    return ws_packages.capacity_by_computer_type(db, on_date=on_date)


@router.get("/resource-planning/shift-hierarchy")
def dashboard_resource_planning_shift_hierarchy(
    on_date: date | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SHIFT → TEAM → EMPLOYEE → computer/IP/software/project (read-only)."""
    _require_it_readiness_access(db, current_user)
    scoped_team_ids = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped_team_ids is not None and team_id is not None and team_id not in scoped_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    from app.services.resource_shift_hierarchy_service import build_shift_hierarchy

    return build_shift_hierarchy(db, on_date=on_date, team_id=team_id)


def _require_special(db: Session, user: User, permission: str, detail: str) -> None:
    role = normalize_role_name(get_role_name(db, user))
    if not user_has_special(user, role, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@router.get("/resource-planning/packages", response_model=list[ResourcePackageRead])
def dashboard_resource_planning_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_readiness_access(db, current_user)
    from app.api.v1.it_operations import _package_read

    return [
        _package_read(row)
        for row in resource_package_service.list_packages(db, active_only=True)
    ]


@router.post("/resource-planning/packages/{package_id}/preview")
def dashboard_resource_planning_package_preview(
    package_id: UUID,
    payload: ResourcePackagePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_readiness_access(db, current_user)
    _require_special(
        db,
        current_user,
        SPECIAL_ASSIGN_IT_ASSETS,
        "Requires assign_it_assets.",
    )
    try:
        return resource_package_service.preview_package_assignment(
            db,
            user_id=payload.user_id,
            package_id=package_id,
            on_date=payload.on_date,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        ) from exc


@router.post("/resource-planning/packages/{package_id}/assign")
def dashboard_resource_planning_package_assign(
    package_id: UUID,
    payload: ResourcePackageAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_readiness_access(db, current_user)
    _require_special(
        db,
        current_user,
        SPECIAL_ASSIGN_IT_ASSETS,
        "Requires assign_it_assets.",
    )
    if payload.shift_id is not None:
        _require_special(
            db,
            current_user,
            SPECIAL_ASSIGN_RESOURCE_SHIFTS,
            "Requires assign_resource_shifts to set a shift.",
        )
    if payload.ip_address_id is not None or payload.network_id is not None:
        _require_special(
            db,
            current_user,
            SPECIAL_ALLOCATE_IT_IPS,
            "Requires allocate_it_ips to assign an IP.",
        )
    if payload.license_pool_ids:
        _require_special(
            db,
            current_user,
            SPECIAL_MANAGE_IT_SOFTWARE,
            "Requires manage_it_software to assign licenses.",
        )
    try:
        return resource_package_service.assign_package(
            db,
            actor=current_user,
            user_id=payload.user_id,
            package_id=package_id,
            asset_ids=payload.asset_ids,
            license_pool_ids=payload.license_pool_ids,
            shift_id=payload.shift_id,
            ip_address_id=payload.ip_address_id,
            network_id=payload.network_id,
            notes=payload.notes,
            assigned_date=payload.assigned_date,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        ) from exc
    except (ShiftValidationError, ShiftConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/resource-planning/assign", status_code=status.HTTP_204_NO_CONTENT)
def dashboard_resource_planning_assign(
    payload: ResourcePlanningAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_project = get_object_or_404(project_crud, db, payload.project_id)
    if not can_update_project(db, current_user, db_project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        project_crud.update(
            db,
            db_obj=db_project,
            obj_in={"designer_id": payload.designer_id},
        )
    except ProTrackValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        ) from exc


@router.get("/workflow", response_model=WorkflowDashboard)
def dashboard_workflow(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_workflow_dashboard(db, current_user)


@router.get("/project/{project_id}", response_model=ProjectDashboard)
def dashboard_project(project_id: UUID, db: Session = Depends(get_db)):
    result = get_project_dashboard(db, project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return result


@router.post("/timesheet-reminders/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def send_timesheet_reminder(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_name = normalize_role_name(get_role_name(db, current_user))
    if role_name not in FULL_ACCESS_ROLES | {DESIGN_LEADER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    create_notification(
        db,
        user_id=user_id,
        notification_type=NotificationType.pending_approval,
        title="Timesheet reminder",
        message="Please submit your missing timesheet entries for recent working days.",
    )
    return None
