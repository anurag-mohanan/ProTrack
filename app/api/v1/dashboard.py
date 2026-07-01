from uuid import UUID

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Session, get_db, status
from app.crud.dashboard import (
    get_dashboard_overview,
    get_dashboard_summary,
    get_designer_workload,
    get_project_dashboard,
    get_workflow_dashboard,
)
from app.models.models import User
from app.schemas.dashboard import (
    DashboardOverview,
    DashboardSummary,
    DesignerWorkload,
    ProjectDashboard,
    WorkflowDashboard,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    return get_dashboard_summary(db)


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_overview(db, current_user)


@router.get("/workload", response_model=list[DesignerWorkload])
def dashboard_workload(db: Session = Depends(get_db)):
    return get_designer_workload(db)


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
