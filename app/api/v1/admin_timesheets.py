"""Admin maintenance endpoints for the timesheet engine."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.schemas.timesheet import TimesheetRecalculationReport
from app.services.timesheet_reconciliation_service import recalculate_all_timesheets

router = APIRouter(prefix="/admin/timesheets", tags=["admin-timesheets"])


@router.post("/recalculate", response_model=TimesheetRecalculationReport)
def recalculate_timesheets(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("Admin")),
):
    """Rebuild all derived timesheet statistics and validate integrity.

    Recalculates project actual hours + health from entries, validates orphan
    entries and dangling references, and returns a detailed report. Safe to run
    after every historical import.
    """
    report = recalculate_all_timesheets(db)
    return TimesheetRecalculationReport(**report.as_dict())
