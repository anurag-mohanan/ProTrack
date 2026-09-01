"""Reusable ProTrack Excel report template — brand header, metadata, KPIs, tables, footer.

All branded Excel exporters should prefer these helpers over ad-hoc cell styling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from app.core.config import COMPANY_LOGO_DIR
from app.services.reporting.excel.styles import (
    ACCENT_BAR_HEIGHT,
    ACCENT_FILL,
    BODY_FONT,
    CARD_BG,
    CARD_BORDER,
    CARD_DETAIL_FONT,
    CARD_HEADER_BG,
    CARD_ROW_HEIGHT,
    CARD_TITLE_FONT,
    CARD_VALUE_FONT,
    CENTER,
    CENTER_NO_WRAP,
    COMPANY_ROW_HEIGHT,
    DEFAULT_THEME,
    HOURS_FORMAT,
    KPI_LABEL_FONT,
    KPI_VALUE_FONT,
    KPI_VALUE_ROW_HEIGHT,
    LEFT,
    NOTES_FONT,
    PRIMARY_SOFT,
    RIGHT,
    SECTION_FONT,
    SECTION_ROW_HEIGHT,
    SOFT_BAND_FILL,
    SOFT_BAND_HEIGHT,
    SUCCESS,
    THIN_BORDER,
    TITLE_ROW_HEIGHT,
    TOTAL_BG,
    TOTAL_EMPHASIS_FILL,
    TOTAL_EMPHASIS_FONT,
    TOTAL_FONT,
    TOTAL_TOP_BORDER,
    UTIL_HIGH_FILL,
    UTIL_LOW_FILL,
    WARNING,
    ReportTheme,
)

_LOGO_MAX_WIDTH = 118
_LOGO_MAX_HEIGHT = 50
_LOGO_NAMES = (
    "company-logo.png",
    "company-logo.jpg",
    "company-logo.jpeg",
    "company-logo.webp",
    "Prosohm_Logo.png",
    "logo.png",
    "logo.jpg",
)


@dataclass
class MetadataCard:
    title: str
    primary: str
    details: list[str] = field(default_factory=list)


@dataclass
class KpiCard:
    label: str
    value: str


@dataclass
class ReportHeaderContext:
    company_name: str
    report_title: str
    audience: str = "internal"  # internal | customer
    theme: ReportTheme = field(default_factory=lambda: DEFAULT_THEME)


def resolve_company_logo_path() -> Path | None:
    """Resolve company logo for Excel exports (uploads folder or env override)."""
    override = (os.environ.get("PROTRACK_REPORT_LOGO_PATH") or "").strip()
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate

    if not COMPANY_LOGO_DIR.exists():
        return None
    for name in _LOGO_NAMES:
        candidate = COMPANY_LOGO_DIR / name
        if candidate.is_file():
            return candidate
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        matches = sorted(COMPANY_LOGO_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def _fit_logo(image: XLImage) -> None:
    width = float(getattr(image, "width", 0) or _LOGO_MAX_WIDTH)
    height = float(getattr(image, "height", 0) or _LOGO_MAX_HEIGHT)
    if width <= 0 or height <= 0:
        image.width = _LOGO_MAX_WIDTH
        image.height = _LOGO_MAX_HEIGHT
        return
    scale = min(_LOGO_MAX_WIDTH / width, _LOGO_MAX_HEIGHT / height, 1.0)
    image.width = max(int(width * scale), 24)
    image.height = max(int(height * scale), 16)


def render_report_logo(sheet, *, col_span: int = 8) -> bool:
    """Place company logo in the upper-right area. Returns True when placed."""
    logo_path = resolve_company_logo_path()
    if logo_path is None:
        return False
    try:
        image = XLImage(str(logo_path))
        _fit_logo(image)
        # Anchor near the right edge, leaving breathing room.
        anchor_col = max(col_span - 1, 4)
        sheet.add_image(image, f"{get_column_letter(anchor_col)}1")
        sheet.row_dimensions[1].height = max(
            float(sheet.row_dimensions[1].height or 15), COMPANY_ROW_HEIGHT
        )
        sheet.column_dimensions[get_column_letter(anchor_col)].width = max(
            float(sheet.column_dimensions[get_column_letter(anchor_col)].width or 10),
            14,
        )
        sheet.column_dimensions[get_column_letter(col_span)].width = max(
            float(sheet.column_dimensions[get_column_letter(col_span)].width or 10),
            14,
        )
        return True
    except Exception:
        return False


def render_report_header(
    sheet,
    *,
    company_name: str,
    report_title: str,
    col_span: int = 8,
    theme: ReportTheme | None = None,
) -> int:
    """
    Brand header block.

    Layout:
      Rows 1–2: company name (merged, centered) + logo top-right
      Row 3: report title (centered)
      Row 4: accent bar
      Row 5: soft band

    Returns next free row (1-based).
    """
    theme = theme or DEFAULT_THEME
    logo_placed = render_report_logo(sheet, col_span=col_span)
    # Keep rightmost columns freer when a logo is present so text does not collide.
    text_end = max(col_span - (2 if logo_placed else 0), 4)
    display_name = (company_name or theme.company_name_fallback).strip().upper()

    sheet.merge_cells(start_row=1, start_column=1, end_row=2, end_column=text_end)
    company_cell = sheet.cell(row=1, column=1, value=display_name)
    company_cell.font = Font(
        name=theme.font_name,
        size=theme.company_font_size,
        bold=True,
        color=theme.primary_color,
    )
    company_cell.alignment = CENTER
    sheet.row_dimensions[1].height = COMPANY_ROW_HEIGHT
    sheet.row_dimensions[2].height = COMPANY_ROW_HEIGHT

    sheet.merge_cells(start_row=3, start_column=1, end_row=3, end_column=text_end)
    title_cell = sheet.cell(row=3, column=1, value=report_title)
    title_cell.font = Font(
        name=theme.font_name,
        size=theme.title_font_size,
        bold=True,
        color=theme.secondary_color,
    )
    title_cell.alignment = CENTER_NO_WRAP
    sheet.row_dimensions[3].height = TITLE_ROW_HEIGHT

    bar_row = 4
    for col in range(1, col_span + 1):
        cell = sheet.cell(row=bar_row, column=col, value="")
        cell.fill = ACCENT_FILL
    sheet.row_dimensions[bar_row].height = ACCENT_BAR_HEIGHT

    soft_row = 5
    for col in range(1, col_span + 1):
        cell = sheet.cell(row=soft_row, column=col, value="")
        cell.fill = SOFT_BAND_FILL
    sheet.row_dimensions[soft_row].height = SOFT_BAND_HEIGHT

    sheet.column_dimensions["A"].width = max(
        float(sheet.column_dimensions["A"].width or 12), 16
    )
    return soft_row + 1


def _paint_card_block(
    sheet,
    *,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
) -> None:
    for row in range(start_row, end_row + 1):
        for col in range(start_col, end_col + 1):
            cell = sheet.cell(row=row, column=col)
            cell.fill = CARD_HEADER_BG if row == start_row else CARD_BG
            cell.border = CARD_BORDER


def render_metadata_cards(
    sheet,
    cards: list[MetadataCard],
    *,
    start_row: int,
    col_span: int,
) -> int:
    """Render 1–4 metadata cards in a single row of merged blocks. Returns next free row."""
    if not cards:
        return start_row

    usable = cards[:4]
    count = len(usable)
    # Distribute columns as evenly as possible.
    widths: list[int] = []
    base = col_span // count
    remainder = col_span % count
    for index in range(count):
        widths.append(base + (1 if index < remainder else 0))

    card_height = 4  # title + primary + up to 2 detail lines
    end_row = start_row + card_height - 1
    col = 1
    for index, card in enumerate(usable):
        width = max(widths[index], 1)
        start_col = col
        end_col = col + width - 1
        _paint_card_block(
            sheet,
            start_row=start_row,
            end_row=end_row,
            start_col=start_col,
            end_col=end_col,
        )
        sheet.merge_cells(
            start_row=start_row,
            start_column=start_col,
            end_row=start_row,
            end_column=end_col,
        )
        title_cell = sheet.cell(row=start_row, column=start_col, value=card.title.upper())
        title_cell.font = CARD_TITLE_FONT
        title_cell.alignment = LEFT

        sheet.merge_cells(
            start_row=start_row + 1,
            start_column=start_col,
            end_row=start_row + 1,
            end_column=end_col,
        )
        primary_cell = sheet.cell(
            row=start_row + 1, column=start_col, value=card.primary or "Not Available"
        )
        primary_cell.font = CARD_VALUE_FONT
        primary_cell.alignment = LEFT

        details = (card.details or [])[:2]
        for detail_offset, detail in enumerate(details):
            detail_row = start_row + 2 + detail_offset
            sheet.merge_cells(
                start_row=detail_row,
                start_column=start_col,
                end_row=detail_row,
                end_column=end_col,
            )
            detail_cell = sheet.cell(row=detail_row, column=start_col, value=detail)
            detail_cell.font = CARD_DETAIL_FONT
            detail_cell.alignment = LEFT

        for row in range(start_row, end_row + 1):
            sheet.row_dimensions[row].height = CARD_ROW_HEIGHT + 2
        col = end_col + 1

    return end_row + 2


def render_section_title(sheet, title: str, *, row: int, col_span: int) -> int:
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_span)
    cell = sheet.cell(row=row, column=1, value=title.upper())
    cell.font = SECTION_FONT
    cell.alignment = LEFT
    sheet.row_dimensions[row].height = SECTION_ROW_HEIGHT
    return row + 1


def render_kpi_cards(
    sheet,
    kpis: list[KpiCard],
    *,
    start_row: int,
    col_span: int,
    per_row: int = 4,
) -> int:
    """Render KPI metric cards. Returns next free row."""
    if not kpis:
        return start_row

    row = start_row
    for batch_start in range(0, len(kpis), per_row):
        batch = kpis[batch_start : batch_start + per_row]
        count = len(batch)
        widths: list[int] = []
        base = col_span // count
        remainder = col_span % count
        for index in range(count):
            widths.append(base + (1 if index < remainder else 0))

        col = 1
        for index, kpi in enumerate(batch):
            width = max(widths[index], 1)
            start_col = col
            end_col = col + width - 1
            for r in (row, row + 1):
                for c in range(start_col, end_col + 1):
                    cell = sheet.cell(row=r, column=c)
                    cell.fill = PatternFill("solid", fgColor=PRIMARY_SOFT)
                    cell.border = THIN_BORDER

            sheet.merge_cells(
                start_row=row, start_column=start_col, end_row=row, end_column=end_col
            )
            label_cell = sheet.cell(row=row, column=start_col, value=kpi.label.upper())
            label_cell.font = KPI_LABEL_FONT
            label_cell.alignment = CENTER

            sheet.merge_cells(
                start_row=row + 1,
                start_column=start_col,
                end_row=row + 1,
                end_column=end_col,
            )
            value_cell = sheet.cell(row=row + 1, column=start_col, value=kpi.value)
            value_cell.font = KPI_VALUE_FONT
            value_cell.alignment = CENTER

            col = end_col + 1

        sheet.row_dimensions[row].height = 16
        sheet.row_dimensions[row + 1].height = KPI_VALUE_ROW_HEIGHT
        row += 3

    return row


def render_notes_section(
    sheet,
    notes: list[tuple[str, str]],
    *,
    start_row: int,
    col_span: int,
) -> int:
    if not notes:
        return start_row
    row = render_section_title(sheet, "Notes / Definitions", row=start_row, col_span=col_span)
    for label, text in notes:
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_span)
        cell = sheet.cell(row=row, column=1, value=f"{label}: {text}")
        cell.font = NOTES_FONT
        cell.alignment = LEFT
        sheet.row_dimensions[row].height = 16
        row += 1
    return row + 1


def style_total_row(
    sheet,
    row: int,
    col_count: int,
    *,
    emphasize_cols: set[int] | None = None,
) -> None:
    sheet.row_dimensions[row].height = 20
    for col in range(1, col_count + 1):
        cell = sheet.cell(row=row, column=col)
        cell.border = TOTAL_TOP_BORDER
        if emphasize_cols and col in emphasize_cols:
            cell.font = TOTAL_EMPHASIS_FONT
            cell.fill = TOTAL_EMPHASIS_FILL
        else:
            cell.font = TOTAL_FONT
            cell.fill = TOTAL_BG


def apply_utilization_conditional_format(
    sheet,
    *,
    start_row: int,
    end_row: int,
    col: int,
    high: float = 80.0,
    low: float = 50.0,
) -> None:
    if end_row < start_row:
        return
    letter = get_column_letter(col)
    cell_range = f"{letter}{start_row}:{letter}{end_row}"
    sheet.conditional_formatting.add(
        cell_range,
        CellIsRule(
            operator="greaterThanOrEqual",
            formula=[str(high)],
            fill=UTIL_HIGH_FILL,
            font=Font(name="Calibri", size=10, color=SUCCESS),
        ),
    )
    sheet.conditional_formatting.add(
        cell_range,
        CellIsRule(
            operator="lessThan",
            formula=[str(low)],
            fill=UTIL_LOW_FILL,
            font=Font(name="Calibri", size=10, color=WARNING),
        ),
    )


def set_print_layout(
    sheet,
    *,
    landscape: bool = True,
    header_rows: str | None = None,
    company_name: str | None = None,
    audience: str = "internal",
    theme: ReportTheme | None = None,
    generated_label: str | None = None,
) -> None:
    """Professional print setup: A4, fit width, repeating headers, branded footer."""
    theme = theme or DEFAULT_THEME
    sheet.page_setup.orientation = "landscape" if landscape else "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_margins = PageMargins(
        left=0.5, right=0.5, top=0.6, bottom=0.7, header=0.2, footer=0.3
    )
    if header_rows:
        sheet.print_title_rows = header_rows

    confidentiality = (
        theme.confidentiality_customer
        if audience == "customer"
        else theme.confidentiality_internal
    )
    company = company_name or theme.company_name_fallback
    left = f"{theme.footer_product} | {company}"
    center = confidentiality
    right_parts = [f"Report {theme.report_version}"]
    if generated_label:
        right_parts.append(generated_label)
    right_parts.append("Page &P of &N")
    right = " | ".join(right_parts)

    sheet.oddFooter.left.text = left
    sheet.oddFooter.left.font = "Calibri"
    sheet.oddFooter.left.size = 8
    sheet.oddFooter.center.text = center
    sheet.oddFooter.center.font = "Calibri"
    sheet.oddFooter.center.size = 8
    sheet.oddFooter.right.text = right
    sheet.oddFooter.right.font = "Calibri"
    sheet.oddFooter.right.size = 8
    sheet.evenFooter = sheet.oddFooter


def format_report_datetime(
    value: datetime,
    *,
    timezone_name: str = "Asia/Kolkata",
) -> str:
    """Professional local timestamp, e.g. 31 Aug 2026, 09:02 AM IST."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
        timezone_name = "UTC"
    if value.tzinfo is None:
        # Treat naive timestamps as UTC (how payloads are typically stamped).
        from datetime import timezone as dt_timezone

        value = value.replace(tzinfo=dt_timezone.utc)
    local = value.astimezone(tz)
    # Prefer short zone abbreviation when available.
    abbrev = local.tzname() or timezone_name
    return f"{local.strftime('%d %b %Y, %I:%M %p')} {abbrev}"


def format_period_month_year(start: date, end: date | None = None) -> tuple[str, int, str]:
    """Return (MONTH_NAME, year, period_display) derived from the report window."""
    end = end or start
    month_name = start.strftime("%B").upper()
    year = start.year
    period_display = f"{start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"
    return month_name, year, period_display


def format_hours(value: float | int) -> float:
    return round(float(value), 1)


def format_hours_display(value: float | int) -> str:
    return f"{format_hours(value):,.1f}"


def format_percent_display(value: float | int) -> str:
    return f"{round(float(value), 1):.1f}%"


def write_aligned_value(cell, value, *, numeric: bool = False, percent: bool = False) -> None:
    cell.value = value
    if percent:
        cell.alignment = RIGHT
        cell.number_format = HOURS_FORMAT
    elif numeric:
        cell.alignment = RIGHT
        cell.number_format = HOURS_FORMAT
    else:
        cell.alignment = LEFT


# Backward-compatible re-exports used by older letterhead callers
def write_simple_extras(
    sheet,
    *,
    start_row: int,
    lines: list[str],
    col_span: int,
) -> int:
    row = start_row
    for line in lines:
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_span)
        cell = sheet.cell(row=row, column=1, value=line)
        cell.font = BODY_FONT
        cell.alignment = LEFT
        sheet.row_dimensions[row].height = 16
        row += 1
    return row + 1 if lines else row
