"""Central forecast catalogue, method versions, periods and metadata."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

from app.schemas.forecasting import (
    ForecastDefinition,
    ForecastMetadata,
    ForecastPeriod,
    ForecastStatus,
)

EFFORT_METHOD_VERSION = "effort-1"
CAPACITY_METHOD_VERSION = "capacity-1"
FINANCE_METHOD_VERSION = "finance-1"

NO_CONFIDENCE_NOTE = (
    "No confidence interval or probability is given: there is no calibrated model behind these "
    "values. Read the status, the backtest and the limitations instead."
)

COMPLETION_DEFERRED_REASON = (
    "Not forecast: a completion date needs phased demand, allocations and planned leave, none of "
    "which are recorded, and the only scheduler converts hours to days at a fixed rate."
)
STAGE_DEFERRED_REASON = (
    "Not forecast: stage actuals are incomplete because the weekly timesheet grid and imports do "
    "not link hours to milestones."
)
SCENARIO_DEFERRED_REASON = (
    "Deferred until completion and phased-demand forecasts exist; a scenario would otherwise show "
    "impacts that cannot be calculated."
)

DEFINITIONS: tuple[ForecastDefinition, ...] = (
    ForecastDefinition(
        key="remaining_effort",
        label="Remaining effort",
        value_kind="forecast",
        method_version=EFFORT_METHOD_VERSION,
        description=(
            "Estimate at completion = original approved estimate × median(actual ÷ original approved "
            "estimate) of completed projects finished on or before the as-of date; remaining = "
            "estimate at completion − actual to date. Only projects with an approved estimate "
            "(stage estimates or milestone planned hours) are forecast."
        ),
    ),
    ForecastDefinition(
        key="approved_remaining",
        label="Approved remaining hours",
        value_kind="approved_plan",
        method_version=EFFORT_METHOD_VERSION,
        description=(
            "Current approved estimate − actual to date, from the shared engineering metrics. "
            "A plan value, not a forecast: it does not assume the plan is sufficient."
        ),
    ),
    ForecastDefinition(
        key="completion_date",
        label="Completion date",
        value_kind="forecast",
        method_version=EFFORT_METHOD_VERSION,
        description="Forecast project completion date.",
        deferred=True,
        deferred_reason=COMPLETION_DEFERRED_REASON,
    ),
    ForecastDefinition(
        key="stage_forecast",
        label="Stage forecast",
        value_kind="forecast",
        method_version=EFFORT_METHOD_VERSION,
        description="Remaining effort and dates per engineering stage.",
        deferred=True,
        deferred_reason=STAGE_DEFERRED_REASON,
    ),
    ForecastDefinition(
        key="capacity_supply",
        label="Capacity supply",
        value_kind="forecast",
        method_version=CAPACITY_METHOD_VERSION,
        description=(
            "Per person and day: scheduled hours (shift hours, else working hours per day, on the "
            "person's working days) minus holidays, days outside the employment window and an "
            "unavailable status; allocatable = available × max allocation %."
        ),
    ),
    ForecastDefinition(
        key="capacity_gap",
        label="Capacity gap",
        value_kind="forecast",
        method_version=CAPACITY_METHOD_VERSION,
        description="Demand vs capacity by period, team and skill.",
        deferred=True,
        deferred_reason=(
            "Demand cannot be phased into periods: there is no allocation model, and skills are "
            "not verified for any user."
        ),
    ),
    ForecastDefinition(
        key="collections",
        label="Collections",
        value_kind="forecast",
        method_version=FINANCE_METHOD_VERSION,
        description=(
            "Outstanding balance of each issued invoice line (FIFO allocation of quote payments) "
            "placed in the period of its contractual due date. Overdue and undated balances are "
            "shown separately with no expected date."
        ),
    ),
    ForecastDefinition(
        key="billing",
        label="Billing",
        value_kind="forecast",
        method_version=FINANCE_METHOD_VERSION,
        description=(
            "Remaining to invoice (awarded value − invoiced − closed balance) for quotes linked to "
            "a live project, split into billing milestones. A milestone is dated only when it is "
            "triggered on project completion and the project has a current target date."
        ),
    ),
    ForecastDefinition(
        key="scenarios",
        label="Scenarios",
        value_kind="scenario",
        method_version="-",
        description="Non-destructive what-if analysis.",
        deferred=True,
        deferred_reason=SCENARIO_DEFERRED_REASON,
    ),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def metadata(
    *,
    forecast_type: str,
    method_version: str,
    as_of: date,
    status: ForecastStatus,
    status_reason: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    sources: list[str],
    assumptions: list[str],
    limitations: list[str],
) -> ForecastMetadata:
    return ForecastMetadata(
        forecast_type=forecast_type,
        method_version=method_version,
        generated_at=utc_now(),
        as_of=as_of,
        period_start=period_start,
        period_end=period_end,
        status=status,
        status_reason=status_reason,
        confidence_note=NO_CONFIDENCE_NOTE,
        sources=sources,
        assumptions=assumptions,
        limitations=limitations,
    )


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def build_periods(start: date, granularity: str, count: int) -> list[ForecastPeriod]:
    """Calendar weeks (Monday start) or calendar months beginning at the period containing ``start``."""
    periods: list[ForecastPeriod] = []
    if granularity == "week":
        cursor = start - timedelta(days=start.weekday())
        for _ in range(count):
            end = cursor + timedelta(days=6)
            iso = cursor.isocalendar()
            periods.append(
                ForecastPeriod(
                    key=f"{iso.year}-W{iso.week:02d}",
                    label=f"W{iso.week} · {cursor.strftime('%d %b')}",
                    start_date=cursor,
                    end_date=end,
                )
            )
            cursor = end + timedelta(days=1)
        return periods
    cursor = _month_start(start)
    for _ in range(count):
        end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        periods.append(
            ForecastPeriod(
                key=f"{cursor.year}-{cursor.month:02d}",
                label=cursor.strftime("%b %Y"),
                start_date=cursor,
                end_date=end,
            )
        )
        cursor = _next_month(cursor)
    return periods


def period_key_for(day: date, periods: list[ForecastPeriod]) -> str | None:
    for period in periods:
        if period.start_date <= day <= period.end_date:
            return period.key
    return None
