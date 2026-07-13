"""Extract tabular data from PDF uploads for import pipelines."""

from __future__ import annotations

import io
from typing import Any

from app.core.exceptions import ProTrackValidationError


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value: Any) -> str:
    text = _cell_text(value)
    return " ".join(text.lower().replace("_", " ").split())


def extract_tables_as_matrix(content: bytes) -> list[list[str]]:
    """
    Return the first usable table from a PDF as a matrix (header + data rows).
    Raises ProTrackValidationError when no table is found.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ProTrackValidationError(
            "PDF import requires pdfplumber. Install dependencies or upload Excel instead."
        ) from exc

    if not content:
        raise ProTrackValidationError("PDF file is empty.")

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    matrix: list[list[str]] = []
                    for row in table:
                        if row is None:
                            continue
                        cells = [_cell_text(cell) for cell in row]
                        if any(cells):
                            matrix.append(cells)
                    if len(matrix) >= 2 and any(_normalize_header(h) for h in matrix[0]):
                        return matrix
    except ProTrackValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface parse failures cleanly
        raise ProTrackValidationError(
            f"Could not read PDF tables: {exc}. "
            "Use a text-based PDF with a clear header row, or upload Excel."
        ) from exc

    raise ProTrackValidationError(
        "No usable table found in PDF. "
        "Export a table with a header row, or upload Excel (.xlsx/.xlsm)."
    )


def extract_tables_as_dicts(content: bytes) -> list[dict[str, str]]:
    matrix = extract_tables_as_matrix(content)
    headers = [h if h else f"column_{idx + 1}" for idx, h in enumerate(matrix[0])]
    rows: list[dict[str, str]] = []
    for values in matrix[1:]:
        if all(not _cell_text(v) for v in values):
            continue
        row: dict[str, str] = {}
        for idx, header in enumerate(headers):
            row[header] = values[idx] if idx < len(values) else ""
        rows.append(row)
    if not rows:
        raise ProTrackValidationError("PDF table has a header but no data rows.")
    return rows


def pdf_content_to_xlsx_bytes(content: bytes) -> bytes:
    """Convert the first usable PDF table into a single-sheet .xlsx workbook."""
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise ProTrackValidationError(
            "Excel conversion requires openpyxl. Install dependencies and retry."
        ) from exc

    matrix = extract_tables_as_matrix(content)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Import"
    for row_idx, row in enumerate(matrix, start=1):
        for col_idx, value in enumerate(row, start=1):
            sheet.cell(row=row_idx, column=col_idx, value=value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
