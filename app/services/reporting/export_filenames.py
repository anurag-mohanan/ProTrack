"""Download filenames for timesheet / reporting Excel exports."""

from __future__ import annotations

from datetime import date


def sanitize_filename_part(value: str, *, max_len: int = 60) -> str:
    """Keep letters, digits, spaces, hyphen, underscore; collapse other chars to underscore."""
    cleaned = "".join(
        ch if ch.isalnum() or ch in (" ", "-", "_") else "_" for ch in (value or "").strip()
    )
    cleaned = "_".join(part for part in cleaned.replace(" ", "_").split("_") if part)
    return (cleaned or "Report")[:max_len]


def customer_timesheet_download_filename(
    *,
    customer_name: str,
    period_type: str,
    period_start: date,
    week_number: int | None = None,
) -> str:
    """
    Prosohm export naming:
      PP_{Customer Name}_Week_{Week number}_{Date}.xlsx
    Monthly uses Month instead of Week when no week number applies.
    """
    customer = sanitize_filename_part(customer_name)
    date_bit = period_start.isoformat()
    if period_type == "weekly" or week_number is not None:
        week = week_number if week_number is not None else period_start.isocalendar()[1]
        return f"PP_{customer}_Week_{week}_{date_bit}.xlsx"
    if period_type == "monthly":
        return f"PP_{customer}_Month_{date_bit}.xlsx"
    if period_type == "quarterly":
        return f"PP_{customer}_Quarter_{date_bit}.xlsx"
    if period_type == "yearly":
        return f"PP_{customer}_Year_{date_bit}.xlsx"
    return f"PP_{customer}_{period_type}_{date_bit}.xlsx"
