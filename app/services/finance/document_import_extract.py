"""Raw PDF text layer + quality diagnostics for Finance document import.

Native text first; OCR only when the text layer is insufficient.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.exceptions import ProTrackValidationError
from app.services.finance.pdf_ocr import (
    MIN_TEXT_CHARS,
    extract_text_with_optional_ocr,
)
from app.services.workorder_pdf_extract import extract_pdf_text

QUOTE_KEYWORDS = (
    "QUOTE",
    "Quote #",
    "Quote#",
    "Quote Date",
    "Customer Project #",
    "Prepared For",
)
INVOICE_KEYWORDS = (
    "INVOICE",
    "Invoice #",
    "Invoice Date",
    "Customer Project #",
    "Balance Due",
    "Bill To",
)


@dataclass
class RawExtraction:
    raw_text: str = ""
    text_extraction_method: str = "none"  # native_pdf | ocr | none
    ocr_used: bool = False
    pages: int | None = None
    character_count: int = 0
    line_count: int = 0
    expected_keywords_found: bool = False
    keywords_hit: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    text_extractable: bool = False


def _count_pages(content: bytes) -> int | None:
    try:
        from pypdf import PdfReader
        import io

        return len(PdfReader(io.BytesIO(content)).pages)
    except Exception:
        return None


def extract_raw_document_text(
    content: bytes,
    *,
    document_kind: str,
    filename: str | None = None,
) -> RawExtraction:
    """STEP 1–3: native PDF text, quality check, OCR fallback only if needed."""
    result = RawExtraction(pages=_count_pages(content))
    native = ""
    try:
        native = extract_pdf_text(content) or ""
    except ProTrackValidationError as exc:
        result.warnings.append(str(exc))
        native = ""
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Native PDF text extraction failed: {exc}")
        native = ""

    ocr = extract_text_with_optional_ocr(content, existing_text=native)
    text = (ocr.text or "").strip()
    result.raw_text = text
    result.ocr_used = ocr.ocr_used
    result.warnings.extend(ocr.warnings)
    result.character_count = len(text)
    result.line_count = len([ln for ln in text.splitlines() if ln.strip()]) if text else 0
    result.text_extractable = result.character_count >= MIN_TEXT_CHARS

    if ocr.ocr_used:
        result.text_extraction_method = "ocr"
    elif native.strip():
        result.text_extraction_method = "native_pdf"
    else:
        result.text_extraction_method = "none"

    keywords = QUOTE_KEYWORDS if document_kind == "quote" else INVOICE_KEYWORDS
    hits = [kw for kw in keywords if re.search(re.escape(kw), text, re.IGNORECASE)]
    # Quote# without space also matches Quote#
    if document_kind == "quote" and re.search(r"Quote\s*#", text, re.IGNORECASE):
        if "Quote #" not in hits and "Quote#" not in hits:
            hits.append("Quote #")
    result.keywords_hit = hits
    result.expected_keywords_found = len(hits) >= 2

    if not result.text_extractable:
        result.warnings.append(
            "Extracted text is empty or too short. "
            "If this is a scanned PDF, OCR is required; otherwise check the upload."
        )
    elif not result.expected_keywords_found:
        result.warnings.append(
            f"Text extracted ({result.character_count} chars) but expected "
            f"{document_kind} labels were not found. Confirm document type."
        )

    _ = filename
    return result


def extraction_quality_dict(raw: RawExtraction) -> dict:
    return {
        "character_count": raw.character_count,
        "line_count": raw.line_count,
        "expected_keywords_found": raw.expected_keywords_found,
        "keywords_hit": list(raw.keywords_hit),
        "text_extraction_method": raw.text_extraction_method,
        "pages": raw.pages,
    }


def build_line_item(
    *,
    description: str | None,
    quantity: float | None,
    rate: float | None,
    amount: float | None,
    stage_hours: list[dict] | None,
    stated_total_hours: float | None,
    unit: str = "Hrs",
) -> dict:
    stages = []
    for row in stage_hours or []:
        stages.append(
            {
                "stage": row.get("label") or row.get("stage") or "",
                "hours": row.get("hours"),
            }
        )
    return {
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "rate": rate,
        "amount": amount,
        "stage_breakdown": stages,
        "stated_total_hours": stated_total_hours,
    }


def hours_mismatch_warning(
    *,
    table_quantity: float | None,
    stage_breakdown_total: float | None,
    stated_total: float | None,
) -> dict | None:
    values = {
        "table_quantity": table_quantity,
        "stage_breakdown_total": stage_breakdown_total,
        "stated_total": stated_total,
    }
    present = [v for v in (table_quantity, stage_breakdown_total, stated_total) if v is not None]
    if len(present) < 2:
        return None
    unique = {round(float(v), 2) for v in present}
    if len(unique) <= 1:
        return None
    return {
        "warning_type": "HOURS_MISMATCH",
        "message": "Document contains different hour totals.",
        "values": values,
    }


__all__ = [
    "RawExtraction",
    "build_line_item",
    "extract_raw_document_text",
    "extraction_quality_dict",
    "hours_mismatch_warning",
]
