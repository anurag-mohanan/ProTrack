from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Session, get_db
from app.crud.reports import (
    get_customer_summary_report,
    get_project_hours_report,
    get_reports_bundle,
)
from app.crud.dashboard import get_designer_workload
from app.schemas.dashboard import DesignerWorkload
from app.schemas.reports import (
    CustomerSummaryReportRow,
    ProjectHoursReportRow,
    ReportsBundle,
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
