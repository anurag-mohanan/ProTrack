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


MAX_CUSTOM_RANGE_DAYS = 366 * 5


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def financial_year_start(day: date, fy_start_month: int) -> date:
    year = day.year if day.month >= fy_start_month else day.year - 1
    return date(year, fy_start_month, 1)


def financial_year_label(day: date, fy_start_month: int) -> str:
    start = financial_year_start(day, fy_start_month)
    if fy_start_month == 1:
        return f"FY {start.year}"
    return f"FY {start.year}-{str(start.year + 1)[-2:]}"


def financial_period_bounds(
    period_type: str,
    *,
    anchor: date | None = None,
    fy_start_month: int = 4,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date, str]:
    """Resolve weekly/monthly/quarterly/yearly/custom periods.

    Quarters and years follow the company financial year (India: April–March),
    so Q1 is April–June and the year runs April to March.
    """
    today = anchor or date.today()
    if period_type == "custom":
        if start_date is None or end_date is None:
            raise ValueError("A custom period needs both a start date and an end date")
        if end_date < start_date:
            raise ValueError("The end date cannot be before the start date")
        if (end_date - start_date).days > MAX_CUSTOM_RANGE_DAYS:
            raise ValueError("A custom period cannot be longer than five years")
        return start_date, end_date, (
            f"Custom — {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        )
    if period_type == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end, (
            f"Week {start.isocalendar()[1]} — {start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
        )
    if period_type == "monthly":
        start = date(today.year, today.month, 1)
        return start, _month_end(today.year, today.month), start.strftime("%B %Y")
    fy_start = financial_year_start(today, fy_start_month)
    fy_label = financial_year_label(today, fy_start_month)
    if period_type == "quarterly":
        months_in = (today.year - fy_start.year) * 12 + today.month - fy_start.month
        quarter = months_in // 3
        start_index = fy_start.month - 1 + quarter * 3
        start = date(fy_start.year + start_index // 12, start_index % 12 + 1, 1)
        end_index = start_index + 2
        end = _month_end(fy_start.year + end_index // 12, end_index % 12 + 1)
        return start, end, f"Q{quarter + 1} {fy_label} ({start.strftime('%b')}–{end.strftime('%b %Y')})"
    if period_type == "yearly":
        end_index = fy_start.month - 1 + 11
        end = _month_end(fy_start.year + end_index // 12, end_index % 12 + 1)
        return fy_start, end, f"{fy_label} ({fy_start.strftime('%b %Y')}–{end.strftime('%b %Y')})"
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
