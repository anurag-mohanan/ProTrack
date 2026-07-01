from uuid import UUID

from datetime import date

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import APIRouter, Depends, HTTPException, Session, get_db, get_object_or_404, status
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import can_update_project
from app.crud import project as project_crud
from app.crud.dashboard import (
    get_dashboard_overview,
    get_dashboard_summary,
    get_designer_workload,
    get_project_dashboard,
    get_workflow_dashboard,
)
from app.models.enums import ProjectStage
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
    ResourcePlanningAssignRequest,
    ResourcePlanningGranularity,
    ResourcePlanningGrid,
)
from app.crud.team_reports import get_team_resource_planning
from app.services.resource_planning_service import get_resource_planning_grid
from app.services.dashboard_service import (
    get_attention_projects,
    get_dashboard_kpis,
    get_dashboard_my_tasks,
    get_dashboard_recent_activity,
    safe_dashboard_call,
)

_planning_access = Depends(
    require_roles(
        "Admin",
        "Engineering Manager",
        "Design Leader",
        "Read Only",
        "Project Manager",
    )
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    project_stage: ProjectStage | None = None,
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_summary(
        db, current_user, project_stage=project_stage, team_id=team_id
    )


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
    dependencies=[_planning_access],
)
def dashboard_workload(db: Session = Depends(get_db)):
    return get_designer_workload(db)


@router.get(
    "/resource-planning",
    response_model=list[TeamResourcePlanningRow],
    dependencies=[_planning_access],
)
def dashboard_resource_planning(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    return get_team_resource_planning(db, team_id=team_id)


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
):
    return get_resource_planning_grid(
        db,
        start=start,
        granularity=granularity,
        team_id=team_id,
    )


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
