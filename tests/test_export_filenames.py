"""Tests for timesheet export download filenames."""

from datetime import date

from app.services.reporting.export_filenames import (
    customer_timesheet_download_filename,
    sanitize_filename_part,
)


def test_sanitize_filename_part_collapses_special_chars():
    assert sanitize_filename_part("Acme / Tools!") == "Acme_Tools"
    assert sanitize_filename_part("  Redoe  Eng  ") == "Redoe_Eng"


def test_weekly_customer_filename_format():
    name = customer_timesheet_download_filename(
        customer_name="Sybridge Sale",
        period_type="weekly",
        period_start=date(2026, 7, 6),
        week_number=28,
    )
    assert name == "PP_Sybridge_Sale_Week_28_2026-07-06.xlsx"


def test_monthly_customer_filename_uses_month_token():
    name = customer_timesheet_download_filename(
        customer_name="Redoe",
        period_type="monthly",
        period_start=date(2026, 7, 1),
        week_number=None,
    )
    assert name == "PP_Redoe_Month_2026-07-01.xlsx"
