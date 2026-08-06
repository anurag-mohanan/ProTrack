"""Simplified designer-by-team timesheet reports (W/M/Q/Y)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TeamBillingMode, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import User, WorkingModel
from app.schemas.reporting import DesignerTeamTimesheetPayload
from app.services.finance.commercial_fee_rules import uses_flat_customer_fee
from app.services.reporting.cross_team_hours import build_cross_team_hours
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


def _active_team_commercial_terms(
    db: Session, team_id: UUID, *, as_of: date | None = None
) -> TeamCommercialTerms | None:
    today = as_of or date.today()
    rows = db.scalars(
        select(TeamCommercialTerms)
        .where(
            TeamCommercialTerms.team_id == team_id,
            TeamCommercialTerms.is_active.is_(True),
        )
        .order_by(TeamCommercialTerms.effective_from.desc())
    ).all()
    for row in rows:
        if row.effective_from and row.effective_from > today:
            continue
        if row.effective_to and row.effective_to < today:
            continue
        return row
    return None


def _team_is_retainer_or_subscription(db: Session, team_id: UUID, *, as_of: date | None = None) -> bool:
    """Retainer working model / subscription billing — customer column is not useful."""
    terms = _active_team_commercial_terms(db, team_id, as_of=as_of)
    if terms is None:
        return False
    if terms.billing_mode == TeamBillingMode.subscription:
        return True
    model = db.get(WorkingModel, terms.working_model_id)
    if model is None:
        return False
    strategy = model.strategy_key
    return uses_flat_customer_fee(strategy) or strategy == WorkingModelCode.retainer


def include_customer_columns_for_scope(
    db: Session,
    *,
    customer_id: UUID | None,
    team_id: UUID | None,
    as_of: date | None = None,
) -> bool:
    """Omit Customer columns for single-customer or retainer/subscription team reports."""
    if customer_id is not None:
        return False
    if team_id is not None and _team_is_retainer_or_subscription(db, team_id, as_of=as_of):
        return False
    return True


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

    scoped_team_id = team_id
    if (
        scoped_team_id is None
        and report_scope.team_ids is not None
        and len(report_scope.team_ids) == 1
    ):
        scoped_team_id = next(iter(report_scope.team_ids))

    cross_rows, outbound_hours, inbound_hours = build_cross_team_hours(
        db,
        start_date=full.period.start_date,
        end_date=full.period.end_date,
        team_id=scoped_team_id,
        customer_id=report_scope.customer_id or customer_id,
        user_ids=set(report_scope.user_ids) if report_scope.user_ids is not None else None,
    )

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
        include_customer_columns=include_customer_columns_for_scope(
            db,
            customer_id=report_scope.customer_id or customer_id,
            team_id=team_id,
            as_of=full.period.end_date if full.period else None,
        ),
        cross_team_hours=cross_rows,
        cross_team_hours_outbound=outbound_hours,
        cross_team_hours_inbound=inbound_hours,
    )
