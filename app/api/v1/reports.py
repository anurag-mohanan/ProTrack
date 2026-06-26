from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Session, get_db
from app.crud.reports import (
    get_customer_summary_report,
    get_designer_productivity_report,
    get_milestone_completion_report,
    get_project_delay_report,
    get_project_hours_report,
    get_reports_bundle,
    get_timesheet_approval_report,
)
from app.crud.dashboard import get_designer_workload
from app.schemas.dashboard import DesignerWorkload
from app.schemas.reports import (
    CustomerSummaryReportRow,
    DesignerProductivityReportRow,
    MilestoneCompletionReportRow,
    ProjectDelayReportRow,
    ProjectHoursReportRow,
    ReportsBundle,
    TimesheetApprovalReportRow,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ReportsBundle)
def list_reports(db: Session = Depends(get_db)):
    return get_reports_bundle(db)


@router.get("/project-hours", response_model=list[ProjectHoursReportRow])
def project_hours_report(db: Session = Depends(get_db)):
    return get_project_hours_report(db)


@router.get("/designer-utilization", response_model=list[DesignerWorkload])
def designer_utilization_report(db: Session = Depends(get_db)):
    return get_designer_workload(db)


@router.get("/customer-summary", response_model=list[CustomerSummaryReportRow])
def customer_summary_report(db: Session = Depends(get_db)):
    return get_customer_summary_report(db)


@router.get("/timesheet-approval", response_model=list[TimesheetApprovalReportRow])
def timesheet_approval_report(db: Session = Depends(get_db)):
    return get_timesheet_approval_report(db)


@router.get("/project-delay", response_model=list[ProjectDelayReportRow])
def project_delay_report(db: Session = Depends(get_db)):
    return get_project_delay_report(db)


@router.get("/milestone-completion", response_model=list[MilestoneCompletionReportRow])
def milestone_completion_report(db: Session = Depends(get_db)):
    return get_milestone_completion_report(db)


@router.get("/designer-productivity", response_model=list[DesignerProductivityReportRow])
def designer_productivity_report(db: Session = Depends(get_db)):
    return get_designer_productivity_report(db)
