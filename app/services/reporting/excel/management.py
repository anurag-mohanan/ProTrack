"""Excel workbooks for management reporting.

Each workbook is written from the payload the management screens use (same filters, same
redaction), so an export never shows a figure the screen would hide. KPI rows carry their kind
(actual, approved plan, forecast, target) so values of different kinds are never read as one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook

from app.services.reporting.excel.letterhead import write_report_letterhead
from app.services.reporting.excel.styles import (
    NOTES_FONT,
    SECTION_FONT,
    autofit_columns,
    style_body_rows,
    style_header_row,
)

KIND_LABELS = {"actual": "Actual", "approved_plan": "Approved plan", "forecast": "Forecast", "target": "Target",
               "manual": "Manual entry", "baseline": "Baseline"}


@dataclass
class SheetTable:
    title: str
    headers: list[str]
    rows: list[list[object]]


@dataclass
class SheetSpec:
    name: str
    title: str
    lines: list[str] = field(default_factory=list)
    kpis: list[dict] = field(default_factory=list)
    tables: list[SheetTable] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def kpi_rows(kpis: list[dict]) -> list[list[object]]:
    return [[k.get("label"), "-" if k.get("value") is None else k.get("value"), k.get("unit"),
             KIND_LABELS.get(k.get("kind"), k.get("kind")), k.get("status"), k.get("sample"), k.get("note")]
            for k in kpis]


def _table(sheet, row: int, table: SheetTable) -> int:
    sheet.cell(row=row, column=1, value=table.title).font = SECTION_FONT
    row += 1
    for col, header in enumerate(table.headers, start=1):
        sheet.cell(row=row, column=col, value=header)
    style_header_row(sheet, row, len(table.headers))
    for offset, values in enumerate(table.rows, start=1):
        for col, value in enumerate(values, start=1):
            sheet.cell(row=row + offset, column=col, value=value if not isinstance(value, (dict, list)) else str(value))
    if table.rows:
        style_body_rows(sheet, row + 1, row + len(table.rows), len(table.headers))
    else:
        sheet.cell(row=row + 1, column=1, value="No rows for these filters.").font = NOTES_FONT
    return row + max(len(table.rows), 1) + 2


def generate_management_excel(sheets: list[SheetSpec], *, company_name: str) -> bytes:
    workbook = Workbook()
    for index, spec in enumerate(sheets):
        sheet = workbook.active if index == 0 else workbook.create_sheet()
        sheet.title = spec.name[:31]
        row = write_report_letterhead(sheet, company_name=company_name, report_title=spec.title,
                                      extra_lines=spec.lines, col_span=8)
        if spec.kpis:
            row = _table(sheet, row, SheetTable("Key figures",
                                                ["Measure", "Value", "Unit", "Kind", "Status", "Sample", "Note"],
                                                kpi_rows(spec.kpis)))
        for table in spec.tables:
            row = _table(sheet, row, table)
        if spec.notes:
            sheet.cell(row=row, column=1, value="Notes").font = SECTION_FONT
            row += 1
            for note in spec.notes:
                sheet.cell(row=row, column=1, value=note).font = NOTES_FONT
                row += 1
        autofit_columns(sheet)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
