"""Branded Excel letterhead — logo, title block, borders."""

from __future__ import annotations

from pathlib import Path

from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import COMPANY_LOGO_DIR
from app.services.reporting.excel.styles import (
    BODY_FONT,
    PRIMARY,
    PRIMARY_SOFT,
    SUBTITLE_FONT,
    TITLE_FONT,
)


def resolve_company_logo_path() -> Path | None:
    if not COMPANY_LOGO_DIR.exists():
        return None
    for name in (
        "company-logo.png",
        "company-logo.jpg",
        "company-logo.jpeg",
        "company-logo.webp",
    ):
        candidate = COMPANY_LOGO_DIR / name
        if candidate.is_file():
            return candidate
    # Fallback: first raster image in the folder
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        matches = sorted(COMPANY_LOGO_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def write_report_letterhead(
    sheet,
    *,
    company_name: str,
    report_title: str,
    period_label: str | None = None,
    extra_lines: list[str] | None = None,
    col_span: int = 8,
) -> int:
    """
    Write a branded header block and return the next free row index (1-based).

    Layout:
      Row 1-3: logo (optional) + company name / report title / period
      Row 4: spacer / accent bar
      Row 5+: content starts
    """
    logo_path = resolve_company_logo_path()
    text_col = 1
    if logo_path is not None:
        try:
            image = XLImage(str(logo_path))
            # Keep logo readable but compact
            image.width = 96
            image.height = 48
            sheet.add_image(image, "A1")
            text_col = 3
            sheet.row_dimensions[1].height = 22
            sheet.row_dimensions[2].height = 20
            sheet.row_dimensions[3].height = 18
        except Exception:
            text_col = 1

    sheet.merge_cells(
        start_row=1,
        start_column=text_col,
        end_row=1,
        end_column=max(col_span, text_col + 3),
    )
    title_cell = sheet.cell(row=1, column=text_col, value=company_name or "Prosohm")
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(vertical="center")

    sheet.merge_cells(
        start_row=2,
        start_column=text_col,
        end_row=2,
        end_column=max(col_span, text_col + 3),
    )
    report_cell = sheet.cell(row=2, column=text_col, value=report_title)
    report_cell.font = Font(name="Calibri", size=13, bold=True, color="1F2937")
    report_cell.alignment = Alignment(vertical="center")

    line = 3
    if period_label:
        sheet.merge_cells(
            start_row=line,
            start_column=text_col,
            end_row=line,
            end_column=max(col_span, text_col + 3),
        )
        period_cell = sheet.cell(row=line, column=text_col, value=period_label)
        period_cell.font = SUBTITLE_FONT
        line += 1

    for extra in extra_lines or []:
        sheet.merge_cells(
            start_row=line,
            start_column=text_col,
            end_row=line,
            end_column=max(col_span, text_col + 3),
        )
        cell = sheet.cell(row=line, column=text_col, value=extra)
        cell.font = BODY_FONT
        line += 1

    # Accent bar under letterhead
    bar_row = line
    for col in range(1, col_span + 1):
        cell = sheet.cell(row=bar_row, column=col, value="")
        cell.fill = PatternFill("solid", fgColor=PRIMARY)
    sheet.row_dimensions[bar_row].height = 6

    # Soft band for visual separation
    soft_row = bar_row + 1
    for col in range(1, col_span + 1):
        cell = sheet.cell(row=soft_row, column=col, value="")
        cell.fill = PatternFill("solid", fgColor=PRIMARY_SOFT)
    sheet.row_dimensions[soft_row].height = 8

    # Ensure early columns have room for logo
    sheet.column_dimensions["A"].width = max(sheet.column_dimensions["A"].width or 12, 14)
    if text_col > 1:
        sheet.column_dimensions["B"].width = max(sheet.column_dimensions["B"].width or 3, 3)

    return soft_row + 1


def style_total_row(sheet, row: int, col_count: int, *, emphasize_cols: set[int] | None = None) -> None:
    fill = PatternFill("solid", fgColor="E8F1FA")
    bold = Font(name="Calibri", size=10, bold=True, color=PRIMARY)
    from app.services.reporting.excel.styles import THIN_BORDER

    for col in range(1, col_count + 1):
        cell = sheet.cell(row=row, column=col)
        cell.font = bold
        cell.fill = fill
        cell.border = THIN_BORDER
        if emphasize_cols and col in emphasize_cols:
            cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=PRIMARY)


def style_utilization_header(sheet, row: int, col: int) -> None:
    from app.services.reporting.excel.styles import HEADER_FONT, THIN_BORDER

    cell = sheet.cell(row=row, column=col)
    cell.fill = PatternFill("solid", fgColor="C47F00")
    cell.font = HEADER_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER


def set_print_layout(sheet, *, landscape: bool = True) -> None:
    sheet.page_setup.orientation = "landscape" if landscape else "portrait"
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = "1:6"
