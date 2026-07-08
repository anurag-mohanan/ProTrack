"""Report period helpers."""

from __future__ import annotations

from datetime import date, timedelta

from app.schemas.reporting import ReportPeriod

PERIOD_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "yearly": "Yearly",
}


def period_bounds(
    period_type: str,
    *,
    anchor: date | None = None,
) -> tuple[date, date]:
    today = anchor or date.today()
    if period_type == "daily":
        return today, today
    if period_type == "weekly":
        week_start = today - timedelta(days=today.weekday())
        return week_start, week_start + timedelta(days=6)
    if period_type == "monthly":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start, end
    if period_type == "quarterly":
        quarter = (today.month - 1) // 3
        start_month = quarter * 3 + 1
        start = date(today.year, start_month, 1)
        end_month = start_month + 2
        if end_month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, end_month + 1, 1) - timedelta(days=1)
        return start, end
    if period_type == "yearly":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    raise ValueError(f"Unsupported period type: {period_type}")


def count_working_days(start: date, end: date, holidays: set[date]) -> int:
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


def build_report_period(
    period_type: str,
    *,
    anchor: date | None = None,
    holidays: set[date] | None = None,
) -> ReportPeriod:
    start, end = period_bounds(period_type, anchor=anchor)
    holiday_set = holidays or set()
    return ReportPeriod(
        period_type=period_type,
        label=f"{PERIOD_LABELS.get(period_type, period_type.title())} — {start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}",
        start_date=start,
        end_date=end,
        working_days=count_working_days(start, end, holiday_set),
    )
