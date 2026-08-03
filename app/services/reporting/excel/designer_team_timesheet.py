"""Excel export for simplified designer-by-team timesheet reports."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.schemas.reporting import DesignerTeamTimesheetPayload
from app.services.reporting.excel.letterhead import (
    set_print_layout,
    style_total_row,
    write_report_letterhead,
)
from app.services.reporting.excel.styles import (
    autofit_columns,
    freeze_and_filter,
    style_body_rows,
    style_header_row,
)


def generate_designer_team_timesheet_excel(payload: DesignerTeamTimesheetPayload) -> bytes:
    workbook = Workbook()
    _write_designers_sheet(workbook, payload)
    _write_projects_sheet(workbook, payload)
    _write_cross_team_sheet(workbook, payload)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_designers_sheet(workbook: Workbook, payload: DesignerTeamTimesheetPayload) -> None:
    sheet = workbook.active
    sheet.title = "Designer Hours by Team"[:31]

    include_customer = payload.include_customer_columns
    headers = [
        "Team",
        "Designer",
        "Productive hours",
        "Non-productive hours",
        "Leave days",
        "Total hours",
        "Utilization %",
        "Projects",
    ]
    if include_customer:
        headers.append("Customers")

    next_row = write_report_letterhead(
        sheet,
        company_name=payload.company_name,
        report_title=payload.title,
        period_label=f"Period: {payload.period.label}",
        extra_lines=[
            f"Generated (UTC): {payload.generated_at.strftime('%Y-%m-%d %H:%M')}",
            (
                f"Summary — Designers: {payload.designer_count} · Teams: {payload.team_count} · "
                f"Period hours: {float(payload.total_designer_hours):.2f}"
            ),
        ],
        col_span=len(headers),
    )

    header_row = next_row
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
        ]
        if include_customer:
            values.append(row.customer_count)
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row=excel_row, column=col, value=value)
            if col >= 3:
                cell.alignment = Alignment(horizontal="right")

    last_data_row = header_row + len(payload.designers)
    if payload.designers:
        style_body_rows(sheet, header_row + 1, last_data_row, len(headers))
        total_row = last_data_row + 1
        sheet.cell(row=total_row, column=1, value="TOTAL")
        sheet.cell(row=total_row, column=3, value=float(payload.total_designer_hours))
        style_total_row(sheet, total_row, len(headers), emphasize_cols={1, 3, 6})

    freeze_and_filter(sheet, header_row, len(headers))
    autofit_columns(sheet)
    set_print_layout(sheet)


def _write_projects_sheet(workbook: Workbook, payload: DesignerTeamTimesheetPayload) -> None:
    sheet = workbook.create_sheet("Project Hours To Date"[:31])

    include_customer = payload.include_customer_columns
    headers = ["Tool #"]
    if include_customer:
        headers.append("Customer")
    headers.extend(
        [
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
    )
    next_row = write_report_letterhead(
        sheet,
        company_name=payload.company_name,
        report_title="Project Hours To Date",
        period_label=f"As of (UTC): {payload.generated_at.strftime('%Y-%m-%d %H:%M')}",
        extra_lines=[
            f"Projects in scope: {payload.project_count}",
            f"Total actual hours to date: {float(payload.total_project_actual_hours):.2f}",
        ],
        col_span=len(headers),
    )

    header_row = next_row
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=header_row, column=col, value=header)
    style_header_row(sheet, header_row, len(headers))

    # Column indexes after optional Customer: quoted/actual/variance shift by 1 when included.
    money_cols = {4, 5, 6, 7, 8} if include_customer else {3, 4, 5, 6, 7}
    variance_col = 6 if include_customer else 5

    for offset, row in enumerate(payload.projects):
        excel_row = header_row + 1 + offset
        values = [row.tool_number]
        if include_customer:
            values.append(row.customer_name)
        values.extend(
            [
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
        )
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row=excel_row, column=col, value=value)
            if col in money_cols:
                cell.alignment = Alignment(horizontal="right")
            # Highlight overruns
            if col == variance_col and isinstance(value, (int, float)) and value > 0:
                cell.font = Font(name="Calibri", size=10, color="B42318", bold=True)
            if col == variance_col and isinstance(value, (int, float)) and value < 0:
                cell.font = Font(name="Calibri", size=10, color="1B7F4B")

    if payload.projects:
        style_body_rows(
            sheet,
            header_row + 1,
            header_row + len(payload.projects),
            len(headers),
        )
        total_row = header_row + len(payload.projects) + 1
        sheet.cell(row=total_row, column=1, value="TOTAL")
        actual_col = 5 if include_customer else 4
        sheet.cell(row=total_row, column=actual_col, value=float(payload.total_project_actual_hours))
        style_total_row(sheet, total_row, len(headers), emphasize_cols={1, actual_col})

    freeze_and_filter(sheet, header_row, len(headers))
    autofit_columns(sheet)
    set_print_layout(sheet)


def _write_cross_team_sheet(workbook: Workbook, payload: DesignerTeamTimesheetPayload) -> None:
    sheet = workbook.create_sheet("Cross-Team Hours"[:31])
    headers = [
        "Direction",
        "Designer",
        "Home team",
        "Tool #",
        "Project team",
        "Customer",
        "Hours",
        "Contribution reason",
    ]
    next_row = write_report_letterhead(
        sheet,
        company_name=payload.company_name,
        report_title="Cross-Team Hours (extra effort)",
        period_label=f"Period: {payload.period.label}",
        extra_lines=[
            (
                f"Outbound (our people on other teams' projects): "
                f"{float(payload.cross_team_hours_outbound):.2f} · "
                f"Inbound (other teams on our projects): "
                f"{float(payload.cross_team_hours_inbound):.2f}"
            ),
        ],
        col_span=len(headers),
    )
    header_row = next_row
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=header_row, column=col, value=header)
    style_header_row(sheet, header_row, len(headers))

    for offset, row in enumerate(payload.cross_team_hours):
        excel_row = header_row + 1 + offset
        values = [
            row.direction,
            row.designer_name,
            row.home_team_name or "—",
            row.tool_number,
            row.project_team_name or "—",
            row.customer_name or "—",
            float(row.hours),
            row.contribution_reason or "",
        ]
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row=excel_row, column=col, value=value)
            if col == 7:
                cell.alignment = Alignment(horizontal="right")

    if payload.cross_team_hours:
        style_body_rows(
            sheet,
            header_row + 1,
            header_row + len(payload.cross_team_hours),
            len(headers),
        )

    freeze_and_filter(sheet, header_row, len(headers))
    autofit_columns(sheet)
    set_print_layout(sheet)
