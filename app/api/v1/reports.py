from uuid import UUID

from app.api.auth_deps import get_current_user, require_roles
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
from app.crud.team_reports import (
    get_customer_by_team_report,
    get_designer_by_team_report,
    get_hours_by_team_report,
    get_monthly_team_summary_report,
    get_projects_by_team_report,
    get_quoted_vs_actual_by_team_report,
    get_team_profitability_report,
    get_team_utilization_report,
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
    ProjectsByTeamReportRow,
    HoursByTeamReportRow,
    QuotedVsActualByTeamReportRow,
    TeamUtilizationReportRow,
    CustomerByTeamReportRow,
    DesignerByTeamReportRow,
    TeamProfitabilityReportRow,
    MonthlyTeamSummaryRow,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[
        Depends(get_current_user),
        Depends(
            require_roles(
                "Admin",
                "Engineering Manager",
                "Design Leader",
                "Read Only",
                "Project Manager",
            )
        ),
    ],
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


def _team_report_options(
    team_id: UUID | None = None,
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    return {
        "team_id": team_id,
        "include_archived": include_archived,
        "include_deleted": include_deleted,
    }


@router.get("/projects-by-team", response_model=list[ProjectsByTeamReportRow])
def projects_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return get_projects_by_team_report(db, **options)


@router.get("/hours-by-team", response_model=list[HoursByTeamReportRow])
def hours_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return get_hours_by_team_report(db, **options)


@router.get("/quoted-vs-actual-by-team", response_model=list[QuotedVsActualByTeamReportRow])
def quoted_vs_actual_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return get_quoted_vs_actual_by_team_report(db, **options)


@router.get("/team-utilization", response_model=list[TeamUtilizationReportRow])
def team_utilization_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
):
    return get_team_utilization_report(db, team_id=team_id)


@router.get("/customer-by-team", response_model=list[CustomerByTeamReportRow])
def customer_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return get_customer_by_team_report(db, **options)


@router.get("/designer-by-team", response_model=list[DesignerByTeamReportRow])
def designer_by_team_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
):
    return get_designer_by_team_report(db, team_id=team_id)


@router.get("/team-profitability", response_model=list[TeamProfitabilityReportRow])
def team_profitability_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return get_team_profitability_report(db, **options)


@router.get("/monthly-team-summary", response_model=list[MonthlyTeamSummaryRow])
def monthly_team_summary_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
):
    return get_monthly_team_summary_report(db, team_id=team_id)
