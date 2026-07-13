"""Shared import file-format policy: Excel + PDF are the defaults."""

from __future__ import annotations

from pathlib import Path

DEFAULT_IMPORT_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xlsm", ".pdf"})
CSV_EXTENSIONS: frozenset[str] = frozenset({".csv"})
EXCEL_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xlsm"})
PDF_EXTENSIONS: frozenset[str] = frozenset({".pdf"})


def with_csv(base: frozenset[str] = DEFAULT_IMPORT_EXTENSIONS) -> frozenset[str]:
    return frozenset(set(base) | set(CSV_EXTENSIONS))


def normalize_suffix(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def format_supported_list(extensions: frozenset[str]) -> str:
    ordered = sorted(extensions)
    return ", ".join(ordered)


def assert_supported_suffix(
    filename: str | None,
    *,
    allowed: frozenset[str] = DEFAULT_IMPORT_EXTENSIONS,
) -> str:
    suffix = normalize_suffix(filename)
    if suffix not in allowed:
        raise ValueError(
            f"Unsupported file type '{suffix or '(none)'}'. "
            f"Supported formats: {format_supported_list(allowed)}."
        )
    return suffix


def is_excel(suffix: str) -> bool:
    return suffix.lower() in EXCEL_EXTENSIONS


def is_pdf(suffix: str) -> bool:
    return suffix.lower() in PDF_EXTENSIONS


def is_csv(suffix: str) -> bool:
    return suffix.lower() in CSV_EXTENSIONS


def normalize_import_bytes(filename: str, content: bytes) -> tuple[str, bytes]:
    """
    Convert PDF table content to an .xlsx workbook so existing Excel parsers can run.
    Non-PDF files are returned unchanged. Parent directories in the relative path are preserved
    (important for folder imports such as DesignerName/file.pdf).
    """
    from app.services.pdf_table_import import pdf_content_to_xlsx_bytes

    suffix = normalize_suffix(filename)
    if suffix in PDF_EXTENSIONS:
        xlsx_bytes = pdf_content_to_xlsx_bytes(content)
        # Keep nested relative paths; only swap the suffix.
        stored = str(Path(filename).with_suffix(".xlsx")).replace("\\", "/")
        return stored, xlsx_bytes
    return filename, content
