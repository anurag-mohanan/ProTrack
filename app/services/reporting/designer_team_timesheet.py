"""Simplified designer-by-team timesheet reports (W/M/Q/Y)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import User
from app.schemas.reporting import DesignerTeamTimesheetPayload
from app.services.reporting.data_service import build_engineering_report
from app.services.reporting.report_scope import ReportScope, resolve_report_scope

TIMESHEET_REPORT_PERIODS: dict[str, str] = {
    "weekly-timesheet": "weekly",
    "monthly-timesheet": "monthly",
    "quarterly-timesheet": "quarterly",
    "yearly-timesheet": "yearly",
}

_PERIOD_TITLES = {
    "weekly": "Weekly Timesheet Report",
    "monthly": "Monthly Timesheet Report",
    "quarterly": "Quarterly Timesheet Report",
    "yearly": "Yearly Timesheet Report",
}


def is_designer_team_timesheet_report(report_id: str) -> bool:
    return report_id in TIMESHEET_REPORT_PERIODS


def period_for_timesheet_report(report_id: str, period_type: str | None = None) -> str:
    if report_id in TIMESHEET_REPORT_PERIODS:
        return TIMESHEET_REPORT_PERIODS[report_id]
    if period_type in ("weekly", "monthly", "quarterly", "yearly"):
        return period_type
    return "monthly"


def build_designer_team_timesheet(
    db: Session,
    *,
    current_user: User,
    report_id: str = "monthly-timesheet",
    period_type: str | None = None,
    anchor: date | None = None,
    customer_id: UUID | None = None,
    team_id: UUID | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
    scope: ReportScope | None = None,
) -> DesignerTeamTimesheetPayload:
    resolved_period = period_for_timesheet_report(report_id, period_type)
    report_scope = scope or resolve_report_scope(
        db,
        current_user,
        customer_id=customer_id,
        team_id=team_id,
    )

    # Reuse engine aggregations so Customer/Team scope stays consistent.
    full = build_engineering_report(
        db,
        period_type=resolved_period,
        anchor=anchor,
        include_archived=include_archived,
        include_deleted=include_deleted,
        report_id=report_id if is_designer_team_timesheet_report(report_id) else f"{resolved_period}-timesheet",
        scope=report_scope,
    )

    designers = sorted(
        full.designer_productivity,
        key=lambda row: ((row.team_name or "—").lower(), row.designer_name.lower()),
    )
    projects = sorted(full.tool_hours, key=lambda row: row.tool_number)
    teams = {row.team_name or "—" for row in designers}

    total_designer = sum((row.total_hours for row in designers), Decimal("0"))
    total_project = sum((row.actual_hours for row in projects), Decimal("0"))

    return DesignerTeamTimesheetPayload(
        report_id=full.report_id,
        title=_PERIOD_TITLES.get(resolved_period, "Timesheet Report"),
        company_name=full.company_name,
        period=full.period,
        generated_at=datetime.now(timezone.utc),
        designers=designers,
        projects=projects,
        total_designer_hours=total_designer,
        total_project_actual_hours=total_project,
        team_count=len(teams),
        designer_count=len(designers),
        project_count=len(projects),
    )
