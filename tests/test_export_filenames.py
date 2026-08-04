"""Tests for timesheet export download filenames."""

from datetime import date

from app.services.reporting.export_filenames import (
    customer_timesheet_download_filename,
    designer_timesheet_download_filename,
    engineering_report_download_filename,
    sanitize_filename_part,
    team_timesheet_download_filename,
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
    assert name == "Prosohm_Sybridge_Sale_Week_28_2026.xlsx"


def test_monthly_customer_filename_uses_month_year():
    name = customer_timesheet_download_filename(
        customer_name="Redoe",
        period_type="monthly",
        period_start=date(2026, 7, 1),
        week_number=None,
    )
    assert name == "Prosohm_Redoe_July_2026.xlsx"


def test_team_timesheet_filename_month_year():
    name = team_timesheet_download_filename(
        team_name="Eng 3 - Redoe",
        period_type="monthly",
        period_start=date(2026, 7, 1),
    )
    assert name == "Prosohm_Eng_3_Redoe_July_2026.xlsx"


def test_team_timesheet_filename_all_teams():
    name = team_timesheet_download_filename(
        team_name=None,
        period_type="monthly",
        period_start=date(2026, 8, 1),
    )
    assert name == "Prosohm_All_Teams_August_2026.xlsx"


def test_designer_timesheet_filename():
    name = designer_timesheet_download_filename(
        designer_name="Ranjith Karayappath",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
    )
    assert name == "Prosohm_Ranjith_Karayappath_July_2026.xlsx"


def test_engineering_report_filename_with_team_subject():
    name = engineering_report_download_filename(
        report_id="designer-productivity",
        period_type="monthly",
        period_start=date(2026, 7, 1),
        subject="Eng 1 - Prosohm Eng",
    )
    assert name == "Prosohm_Eng_1_Prosohm_Eng_July_2026.xlsx"


def test_stream_scoped_download_filename_includes_stream():
    from app.services.reporting.export_filenames import stream_scoped_download_filename

    name = stream_scoped_download_filename(
        stream_name="CAD Development",
        subject="Eng 1",
        period_type="monthly",
        period_start=date(2026, 8, 1),
    )
    assert name == "Prosohm_CAD_Development_Eng_1_August_2026.xlsx"


def test_quarterly_and_yearly_tokens():
    q = team_timesheet_download_filename(
        team_name="Prosohm Eng",
        period_type="quarterly",
        period_start=date(2026, 7, 1),
    )
    y = team_timesheet_download_filename(
        team_name="Prosohm Eng",
        period_type="yearly",
        period_start=date(2026, 1, 1),
    )
    assert q == "Prosohm_Prosohm_Eng_Q3_2026.xlsx"
    assert y == "Prosohm_Prosohm_Eng_2026.xlsx"
