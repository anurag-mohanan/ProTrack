"""Professional Excel styling for engineering reports."""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

PRIMARY = "0066B3"
PRIMARY_SOFT = "D9EAF7"
SUCCESS = "1B7F4B"
WARNING = "C47F00"
DANGER = "B42318"
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=PRIMARY)
SUBTITLE_FONT = Font(name="Calibri", size=11, color="555555")
BODY_FONT = Font(name="Calibri", size=10)
KPI_LABEL_FONT = Font(name="Calibri", size=9, color="666666")
KPI_VALUE_FONT = Font(name="Calibri", size=12, bold=True, color=PRIMARY)
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D7DE"),
    right=Side(style="thin", color="D0D7DE"),
    top=Side(style="thin", color="D0D7DE"),
    bottom=Side(style="thin", color="D0D7DE"),
)
HEADER_FILL = PatternFill("solid", fgColor=PRIMARY)
ALT_FILL = PatternFill("solid", fgColor="F6F8FA")
KPI_FILL = PatternFill("solid", fgColor=PRIMARY_SOFT)


def style_header_row(sheet, row: int, col_count: int) -> None:
    for col in range(1, col_count + 1):
        cell = sheet.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def style_body_rows(sheet, start_row: int, end_row: int, col_count: int) -> None:
    for row in range(start_row, end_row + 1):
        for col in range(1, col_count + 1):
            cell = sheet.cell(row=row, column=col)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            if (row - start_row) % 2 == 1:
                cell.fill = ALT_FILL


def autofit_columns(sheet, min_width: int = 10, max_width: int = 42) -> None:
    for col_cells in sheet.columns:
        letter = get_column_letter(col_cells[0].column)
        length = max(len(str(cell.value or "")) for cell in col_cells)
        sheet.column_dimensions[letter].width = min(max(length + 2, min_width), max_width)


def freeze_and_filter(sheet, header_row: int, last_col: int) -> None:
    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(last_col)}{sheet.max_row}"
