"""Download filenames for timesheet / reporting Excel exports.

Canonical pattern (user-facing):
  Prosohm_{Subject}_{Month}_{Year}.xlsx

Examples:
  Prosohm_Eng_3_Redoe_July_2026.xlsx
  Prosohm_All_Teams_July_2026.xlsx
  Prosohm_Ranjith_Karayappath_July_2026.xlsx

Week / quarter / year variants keep the same Prosohm + subject prefix.
"""

from __future__ import annotations

from calendar import month_name
from datetime import date


def sanitize_filename_part(value: str, *, max_len: int = 60) -> str:
    """Keep letters and digits; collapse spaces/hyphens/other chars to underscores."""
    normalized = (value or "").strip().replace("-", " ")
    cleaned = "".join(
        ch if ch.isalnum() or ch in (" ", "_") else "_" for ch in normalized
    )
    cleaned = "_".join(part for part in cleaned.replace(" ", "_").split("_") if part)
    return (cleaned or "Report")[:max_len]


def period_filename_token(
    *,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """Return the period segment used in download names (Month_Year, Week_N_Year, …)."""
    year = period_start.year
    month = month_name[period_start.month]
    normalized = (period_type or "monthly").lower()
    if normalized == "weekly" or week_number is not None:
        week = week_number if week_number is not None else period_start.isocalendar()[1]
        return f"Week_{week}_{year}"
    if normalized == "quarterly":
        quarter = (period_start.month - 1) // 3 + 1
        return f"Q{quarter}_{year}"
    if normalized == "yearly":
        return str(year)
    # monthly (default) and unknown → Month_Year
    return f"{month}_{year}"


def prosohm_report_download_filename(
    *,
    subject: str,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """
    Prosohm_{Subject}_{Month}_{Year}.xlsx (and week/quarter/year equivalents).

    ``subject`` is typically a team name, designer name, customer name, or report label.
    """
    subject_part = sanitize_filename_part(subject)
    period_part = period_filename_token(
        period_type=period_type,
        period_start=period_start,
        week_number=week_number,
    )
    return f"Prosohm_{subject_part}_{period_part}.xlsx"


def stream_scoped_download_filename(
    *,
    stream_name: str,
    subject: str | None = None,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """Include stream in the subject when the export is stream-scoped."""
    stream_part = sanitize_filename_part(stream_name)
    if subject:
        combined = f"{stream_part}_{sanitize_filename_part(subject)}"
    else:
        combined = stream_part
    return prosohm_report_download_filename(
        subject=combined,
        period_type=period_type,
        period_start=period_start,
        week_number=week_number,
    )


def customer_timesheet_download_filename(
    *,
    customer_name: str,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """Customer timesheet pack — same Prosohm naming as other reports."""
    return prosohm_report_download_filename(
        subject=customer_name,
        period_type=period_type,
        period_start=period_start,
        week_number=week_number,
    )


def team_timesheet_download_filename(
    *,
    team_name: str | None,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """Designer / team timesheet report download name."""
    return prosohm_report_download_filename(
        subject=team_name or "All_Teams",
        period_type=period_type,
        period_start=period_start,
        week_number=week_number,
    )


def designer_timesheet_download_filename(
    *,
    designer_name: str,
    period_start: date,
    period_end: date | None = None,
    period_type: str = "monthly",
) -> str:
    """Individual designer timesheet export."""
    # Infer period type from span when not provided by the UI.
    resolved_type = period_type
    if period_end is not None and period_type == "monthly":
        span_days = (period_end - period_start).days
        if span_days >= 360:
            resolved_type = "yearly"
        elif span_days >= 80:
            resolved_type = "quarterly"
        elif span_days <= 8:
            resolved_type = "weekly"
    return prosohm_report_download_filename(
        subject=designer_name,
        period_type=resolved_type,
        period_start=period_start,
        week_number=period_start.isocalendar()[1] if resolved_type == "weekly" else None,
    )


def engineering_report_download_filename(
    *,
    report_id: str,
    period_type: str,
    period_start: date,
    subject: str | None = None,
    week_number: int | None = None,
) -> str:
    """Generic engineering engine report download name."""
    label = subject or report_id.replace("-", " ").replace("_", " ").title()
    return prosohm_report_download_filename(
        subject=label,
        period_type=period_type,
        period_start=period_start,
        week_number=week_number,
    )
