"""Excel export for simplified designer-by-team timesheet reports."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.schemas.reporting import DesignerTeamTimesheetPayload
from app.services.reporting.excel.styles import (
    BODY_FONT,
    SUBTITLE_FONT,
    TITLE_FONT,
    autofit_columns,
    style_body_rows,
    style_header_row,
)


def generate_designer_team_timesheet_excel(payload: DesignerTeamTimesheetPayload) -> bytes:
    workbook = Workbook()
    _write_designers_sheet(workbook, payload)
    _write_projects_sheet(workbook, payload)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_designers_sheet(workbook: Workbook, payload: DesignerTeamTimesheetPayload) -> None:
    sheet = workbook.active
    sheet.title = "Designer Hours by Team"[:31]

    sheet["A1"] = payload.company_name
    sheet["A1"].font = TITLE_FONT
    sheet["A2"] = payload.title
    sheet["A2"].font = SUBTITLE_FONT
    sheet["A3"] = f"Period: {payload.period.label}"
    sheet["A3"].font = BODY_FONT
    sheet["A4"] = f"Generated (UTC): {payload.generated_at.strftime('%Y-%m-%d %H:%M')}"
    sheet["A4"].font = BODY_FONT

    headers = [
        "Team",
        "Designer",
        "Productive hours",
        "Non-productive hours",
        "Leave days",
        "Total hours",
        "Utilization %",
        "Projects",
        "Customers",
    ]
    header_row = 6
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=header_row, column=col, value=header)
    style_header_row(sheet, header_row, len(headers))

    for offset, row in enumerate(payload.designers):
        excel_row = header_row + 1 + offset
        values = [
            row.team_name or "—",
            row.designer_name,
            float(row.productive_hours),
            float(row.non_productive_hours),
            float(row.leave_days),
            float(row.total_hours),
            float(row.utilization_percent),
            row.project_count,
            row.customer_count,
        ]
        for col, value in enumerate(values, start=1):
            sheet.cell(row=excel_row, column=col, value=value)

    if payload.designers:
        style_body_rows(sheet, header_row + 1, header_row + len(payload.designers), len(headers))
    autofit_columns(sheet)


def _write_projects_sheet(workbook: Workbook, payload: DesignerTeamTimesheetPayload) -> None:
    sheet = workbook.create_sheet("Project Hours To Date"[:31])

    sheet["A1"] = payload.company_name
    sheet["A1"].font = TITLE_FONT
    sheet["A2"] = "Total project hours up to report generation"
    sheet["A2"].font = SUBTITLE_FONT
    sheet["A3"] = f"As of (UTC): {payload.generated_at.strftime('%Y-%m-%d %H:%M')}"
    sheet["A3"].font = BODY_FONT

    headers = [
        "Tool #",
        "Customer",
        "Part description",
        "Quoted hours",
        "Actual hours to date",
        "Variance hours",
        "Variance %",
        "Completion %",
        "Designer",
        "Stage",
        "Status",
    ]
    header_row = 5
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=header_row, column=col, value=header)
    style_header_row(sheet, header_row, len(headers))

    for offset, row in enumerate(payload.projects):
        excel_row = header_row + 1 + offset
        values = [
            row.tool_number,
            row.customer_name,
            row.part_description or "",
            float(row.quoted_hours),
            float(row.actual_hours),
            float(row.variance_hours),
            float(row.variance_percent),
            float(row.completion_percent),
            row.designer_name or "",
            str(row.project_stage.value if hasattr(row.project_stage, "value") else row.project_stage),
            str(
                row.execution_status.value
                if hasattr(row.execution_status, "value")
                else row.execution_status
            ),
        ]
        for col, value in enumerate(values, start=1):
            sheet.cell(row=excel_row, column=col, value=value)

    if payload.projects:
        style_body_rows(sheet, header_row + 1, header_row + len(payload.projects), len(headers))
    autofit_columns(sheet)
