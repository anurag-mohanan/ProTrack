from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.permissions import can_view_deleted_projects
from app.crud.reports import (
    get_billable_utilization_report,
    get_billable_vs_non_billable_report,
    get_customer_summary_report,
    get_designer_productivity_report,
    get_execution_status_summary_report,
    get_milestone_completion_report,
    get_monthly_np_trends_report,
    get_non_productive_hours_report,
    get_np_hours_by_designer_report,
    get_productive_hours_report,
    get_project_delay_report,
    get_project_hours_report,
    get_project_portfolio_report,
    get_project_stage_summary_report,
    get_reports_bundle,
    get_timesheet_approval_report,
    get_top_np_activities_report,
)
from app.models.enums import ProjectStage
from app.crud.dashboard import get_designer_workload
from app.models.models import User
from app.schemas.dashboard import DesignerWorkload
from app.schemas.reports import (
    BillableUtilizationReportRow,
    BillableVsNonBillableReportRow,
    CustomerSummaryReportRow,
    DesignerProductivityReportRow,
    ExecutionStatusSummaryRow,
    MilestoneCompletionReportRow,
    MonthlyNpTrendReportRow,
    NonProductiveHoursReportRow,
    NpHoursByDesignerReportRow,
    ProductiveHoursReportRow,
    ProjectDelayReportRow,
    ProjectHoursReportRow,
    ProjectPortfolioReportRow,
    ProjectStageSummaryRow,
    ReportsBundle,
    TimesheetApprovalReportRow,
    TopNpActivityReportRow,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)


def _report_options(
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    return {
        "include_archived": include_archived,
        "include_deleted": include_deleted,
    }


@router.get("", response_model=ReportsBundle)
def list_reports(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_reports_bundle(db, **options)


@router.get("/project-hours", response_model=list[ProjectHoursReportRow])
def project_hours_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_hours_report(db, **options)


@router.get("/designer-utilization", response_model=list[DesignerWorkload])
def designer_utilization_report(db: Session = Depends(get_db)):
    return get_designer_workload(db)


@router.get("/customer-summary", response_model=list[CustomerSummaryReportRow])
def customer_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_customer_summary_report(db, **options)


@router.get("/timesheet-approval", response_model=list[TimesheetApprovalReportRow])
def timesheet_approval_report(db: Session = Depends(get_db)):
    return get_timesheet_approval_report(db)


@router.get("/project-delay", response_model=list[ProjectDelayReportRow])
def project_delay_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_delay_report(db, **options)


@router.get("/milestone-completion", response_model=list[MilestoneCompletionReportRow])
def milestone_completion_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_milestone_completion_report(db, **options)


@router.get("/designer-productivity", response_model=list[DesignerProductivityReportRow])
def designer_productivity_report(db: Session = Depends(get_db)):
    return get_designer_productivity_report(db)


@router.get("/productive-hours", response_model=list[ProductiveHoursReportRow])
def productive_hours_report(db: Session = Depends(get_db)):
    return get_productive_hours_report(db)


@router.get("/non-productive-hours", response_model=list[NonProductiveHoursReportRow])
def non_productive_hours_report(db: Session = Depends(get_db)):
    return get_non_productive_hours_report(db)


@router.get("/billable-utilization", response_model=list[BillableUtilizationReportRow])
def billable_utilization_report(db: Session = Depends(get_db)):
    return get_billable_utilization_report(db)


@router.get("/monthly-np-trends", response_model=list[MonthlyNpTrendReportRow])
def monthly_np_trends_report(db: Session = Depends(get_db)):
    return get_monthly_np_trends_report(db)


@router.get("/np-hours-by-designer", response_model=list[NpHoursByDesignerReportRow])
def np_hours_by_designer_report(db: Session = Depends(get_db)):
    return get_np_hours_by_designer_report(db)


@router.get("/billable-vs-non-billable", response_model=BillableVsNonBillableReportRow)
def billable_vs_non_billable_report(db: Session = Depends(get_db)):
    return get_billable_vs_non_billable_report(db)


@router.get("/top-np-activities", response_model=list[TopNpActivityReportRow])
def top_np_activities_report(db: Session = Depends(get_db)):
    return get_top_np_activities_report(db)


@router.get("/project-portfolio", response_model=list[ProjectPortfolioReportRow])
def project_portfolio_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_portfolio_report(db, **options)


@router.get("/project-stage-summary", response_model=list[ProjectStageSummaryRow])
def project_stage_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_stage_summary_report(db, **options)


@router.get("/execution-status-summary", response_model=list[ExecutionStatusSummaryRow])
def execution_status_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_execution_status_summary_report(db, **options)
