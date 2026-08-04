"""Branded Excel letterhead — logo (top-right), title block, borders."""

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

_LOGO_MAX_WIDTH = 120
_LOGO_MAX_HEIGHT = 52


def resolve_company_logo_path() -> Path | None:
    """Resolve the uploaded company logo from the Company Information settings folder."""
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
    # Fallback: first raster image in the folder (matches /settings/company/logo)
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        matches = sorted(COMPANY_LOGO_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def _fit_logo(image: XLImage) -> None:
    """Scale logo to fit branding box while preserving aspect ratio."""
    width = float(getattr(image, "width", 0) or _LOGO_MAX_WIDTH)
    height = float(getattr(image, "height", 0) or _LOGO_MAX_HEIGHT)
    if width <= 0 or height <= 0:
        image.width = _LOGO_MAX_WIDTH
        image.height = _LOGO_MAX_HEIGHT
        return
    scale = min(_LOGO_MAX_WIDTH / width, _LOGO_MAX_HEIGHT / height, 1.0)
    image.width = max(int(width * scale), 24)
    image.height = max(int(height * scale), 16)


def add_company_logo_top_right(sheet, *, col_span: int = 8) -> bool:
    """Embed company logo in the top-right of the sheet. Returns True when added."""
    logo_path = resolve_company_logo_path()
    if logo_path is None:
        return False
    try:
        image = XLImage(str(logo_path))
        _fit_logo(image)
        anchor_col = max(col_span, 4)
        sheet.add_image(image, f"{get_column_letter(anchor_col)}1")
        sheet.row_dimensions[1].height = max(float(sheet.row_dimensions[1].height or 15), 40)
        sheet.column_dimensions[get_column_letter(anchor_col)].width = max(
            float(sheet.column_dimensions[get_column_letter(anchor_col)].width or 10),
            18,
        )
        return True
    except Exception:
        # Missing Pillow or unsupported image format must not break exports.
        return False


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
      Left: company name / report title / period
      Top-right: company logo (from Company Information upload)
      Accent bar under letterhead, then content
    """
    logo_placed = add_company_logo_top_right(sheet, col_span=col_span)
    # Leave the rightmost columns free so the logo is not covered by merged title text.
    text_end = max(col_span - (2 if logo_placed else 0), 4)

    sheet.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=text_end,
    )
    title_cell = sheet.cell(row=1, column=1, value=company_name or "Prosohm")
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(vertical="center")

    sheet.merge_cells(
        start_row=2,
        start_column=1,
        end_row=2,
        end_column=text_end,
    )
    report_cell = sheet.cell(row=2, column=1, value=report_title)
    report_cell.font = Font(name="Calibri", size=13, bold=True, color="1F2937")
    report_cell.alignment = Alignment(vertical="center")

    line = 3
    if period_label:
        sheet.merge_cells(
            start_row=line,
            start_column=1,
            end_row=line,
            end_column=text_end,
        )
        period_cell = sheet.cell(row=line, column=1, value=period_label)
        period_cell.font = SUBTITLE_FONT
        line += 1

    for extra in extra_lines or []:
        sheet.merge_cells(
            start_row=line,
            start_column=1,
            end_row=line,
            end_column=text_end,
        )
        cell = sheet.cell(row=line, column=1, value=extra)
        cell.font = BODY_FONT
        line += 1

    # Accent bar under letterhead
    bar_row = max(line, 4 if logo_placed else line)
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

    sheet.column_dimensions["A"].width = max(sheet.column_dimensions["A"].width or 12, 14)

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
