"""Excel export for customer weekly/monthly timesheet packs."""

from __future__ import annotations

from io import BytesIO

from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.schemas.reporting import CustomerTimesheetPackPayload
from app.services.reporting.excel.styles import (
    BODY_FONT,
    SUBTITLE_FONT,
    TITLE_FONT,
    autofit_columns,
    style_body_rows,
    style_header_row,
)


def generate_customer_timesheet_excel(payload: CustomerTimesheetPackPayload) -> bytes:
    workbook = Workbook()
    _write_associate_sheet(workbook, payload)
    _write_tool_sheet(workbook, payload)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_associate_sheet(workbook: Workbook, payload: CustomerTimesheetPackPayload) -> None:
    sheet = workbook.active
    sheet.title = "Weekly Timesheet"[:31] if payload.period.period_type == "weekly" else "Monthly Timesheet"

    sheet["A1"] = payload.company_name
    sheet["A1"].font = TITLE_FONT
    sheet["A2"] = payload.title
    sheet["A2"].font = SUBTITLE_FONT
    sheet["A3"] = f"Customer: {payload.customer_name}"
    sheet["A3"].font = BODY_FONT

    period_label = (
        f"{payload.period.start_date.strftime('%d-%m-%y')} to "
        f"{payload.period.end_date.strftime('%d-%m-%y')}"
    )
    sheet["A4"] = f"Period: {period_label}"
    if payload.week_number is not None:
        sheet["C4"] = f"WEEK of {payload.week_number}"
        sheet["C4"].font = Font(bold=True, size=14)
    sheet["E4"] = f"Working Hrs. {payload.working_hours_target}"
    sheet["E4"].font = Font(bold=True)

    headers = [
        "Sl No.",
        "Name of the associate",
        "Designation",
        "Productive hours",
        "Non Productive hours",
        "TOTAL",
        "Utilization",
        "Remarks",
    ]
    header_row = 6
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=col, value=header)
        if header == "Utilization":
            cell.fill = PatternFill("solid", fgColor="F4A261")
            cell.font = Font(bold=True, color="FFFFFF")
        else:
            cell.fill = PatternFill("solid", fgColor="AED6F1")
            cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, horizontal="center")

    for offset, row in enumerate(payload.associates):
        excel_row = header_row + 1 + offset
        values = [
            row.serial_no,
            row.associate_name,
            row.designation or "",
            float(row.productive_hours),
            float(row.non_productive_hours),
            float(row.total_hours),
            f"{float(row.utilization_percent):.0f}%",
            row.remarks or "",
        ]
        for col, value in enumerate(values, start=1):
            sheet.cell(row=excel_row, column=col, value=value)

    total_row = header_row + 1 + len(payload.associates)
    sheet.cell(row=total_row, column=1, value="")
    sheet.cell(row=total_row, column=2, value="TOTAL").font = Font(bold=True)
    sheet.cell(row=total_row, column=4, value=float(payload.total_productive_hours)).font = Font(bold=True)
    sheet.cell(row=total_row, column=5, value=float(payload.total_non_productive_hours)).font = Font(bold=True)
    sheet.cell(row=total_row, column=6, value=float(payload.total_hours)).font = Font(bold=True)
    sheet.cell(
        row=total_row,
        column=7,
        value=f"{float(payload.overall_utilization_percent):.0f}%",
    ).font = Font(bold=True)

    if payload.associates:
        style_body_rows(sheet, header_row + 1, total_row, len(headers))
    style_header_row(sheet, header_row, len(headers))
    autofit_columns(sheet, min_width=12)


def _write_tool_sheet(workbook: Workbook, payload: CustomerTimesheetPackPayload) -> None:
    sheet = workbook.create_sheet("By Tool")
    headers = ["TOOL No.", "Sum of HOURS", "Comments"]
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.fill = PatternFill("solid", fgColor="1B4F72")
        cell.font = Font(bold=True, color="FFFFFF")

    for offset, row in enumerate(payload.tools):
        excel_row = 2 + offset
        sheet.cell(row=excel_row, column=1, value=row.tool_number)
        sheet.cell(row=excel_row, column=2, value=float(row.hours))
        sheet.cell(row=excel_row, column=3, value=row.comments or "")

    total_row = 2 + len(payload.tools)
    sheet.cell(row=total_row, column=1, value="Total").font = Font(bold=True)
    sheet.cell(
        row=total_row,
        column=2,
        value=float(sum((row.hours for row in payload.tools), Decimal("0"))),
    ).font = Font(bold=True)

    if payload.tools:
        style_body_rows(sheet, 2, total_row, len(headers))
    style_header_row(sheet, 1, len(headers))
    autofit_columns(sheet, min_width=14)
