"""Company financial-year calendar — single source for Finance periodization."""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.finance.annual_plan_service import (
    current_fy_label,
    current_fy_start,
    fiscal_year_bounds,
)


def company_fy_start_month(db: Session) -> int:
    """Read configured FY start month (1–12). Default April (4)."""
    from app.models.foundation import CompanySettings

    settings = db.scalar(select(CompanySettings).limit(1))
    month = int(getattr(settings, "financial_year_start_month", None) or 4)
    if month < 1 or month > 12:
        return 4
    return month


def resolve_fy_context(
    db: Session,
    *,
    today: date | None = None,
    fy_start_year: int | None = None,
) -> dict:
    """
    Resolve the active financial year window from company settings.

    Returns fy_start, fy_end, label, start_month, and whether this is the current FY.
    """
    today = today or date.today()
    start_month = company_fy_start_month(db)
    if fy_start_year is None:
        fy_start = current_fy_start(today, fy_start_month=start_month)
    else:
        fy_start, _, _ = fiscal_year_bounds(fy_start_year, fy_start_month=start_month)
    fy_start, fy_end, short_label = fiscal_year_bounds(
        fy_start.year, fy_start_month=start_month
    )
    current_start = current_fy_start(today, fy_start_month=start_month)
    return {
        "fy_start": fy_start,
        "fy_end": fy_end,
        "fy_label": f"FY {short_label}",
        "fy_short_label": short_label,
        "fy_start_month": start_month,
        "fy_start_year": fy_start.year,
        "is_current_fy": fy_start == current_start,
        "today": today,
        "current_fy_label": current_fy_label(today, fy_start_month=start_month),
    }


def fy_month_windows(fy_start: date) -> list[dict]:
    """Twelve calendar months in FY order: index 0 = FY month 1."""
    months: list[dict] = []
    year = fy_start.year
    month = fy_start.month
    for index in range(12):
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        months.append(
            {
                "index": index,
                "month_start": start,
                "month_end": end,
                "calendar_year": year,
                "calendar_month": month,
                "label": start.strftime("%B %Y"),
                "short_label": start.strftime("%b %Y"),
            }
        )
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def elapsed_fy_months(fy_start: date, today: date, fy_end: date) -> int:
    """
    Count elapsed months in the FY including the current month.

    Future FY → 0. Past FY → 12. Current FY → months from start through today.
    """
    if today < fy_start:
        return 0
    if today > fy_end:
        return 12
    return (today.year - fy_start.year) * 12 + (today.month - fy_start.month) + 1


def month_index_for_date(fy_start: date, value: date) -> int | None:
    """Return 0–11 if date falls in this FY, else None."""
    fy_end = fy_month_windows(fy_start)[-1]["month_end"]
    if value < fy_start or value > fy_end:
        return None
    return (value.year - fy_start.year) * 12 + (value.month - fy_start.month)
