"""Optional OCR fallback for scanned PDFs (Connected ProTrack, Wave 5).

``pytesseract`` and ``pdf2image`` are soft dependencies: when they (or the
underlying tesseract / poppler binaries) are absent the caller gets
``ocr_used=False`` plus a clear message. Nothing here may raise at import time,
so a deployment without OCR still starts normally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

OCR_UNAVAILABLE_MESSAGE = "OCR not available — install tesseract/pdf2image"

# Below this, a PDF is treated as scanned/image-only rather than text-based.
MIN_TEXT_CHARS = 40

# Rendering every page of a large scan is slow; invoices and quotes we care
# about carry their key fields on the first few pages.
MAX_OCR_PAGES = 5

OCR_DPI = 300


@dataclass
class OcrOutcome:
    text: str = ""
    ocr_used: bool = False
    ocr_attempted: bool = False
    ocr_available: bool = False
    warnings: list[str] = field(default_factory=list)


def ocr_available() -> bool:
    """True when both optional OCR libraries import cleanly."""
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except Exception:
        return False
    return True


def looks_scanned(text: str | None, *, min_chars: int = MIN_TEXT_CHARS) -> bool:
    return len((text or "").strip()) < min_chars


def ocr_pdf_text(content: bytes, *, max_pages: int = MAX_OCR_PAGES) -> OcrOutcome:
    """Render PDF pages to images and OCR them. Never raises."""
    outcome = OcrOutcome(ocr_attempted=True)
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except Exception:
        outcome.warnings.append(OCR_UNAVAILABLE_MESSAGE)
        return outcome

    outcome.ocr_available = True
    try:
        images = convert_from_bytes(
            content,
            dpi=OCR_DPI,
            first_page=1,
            last_page=max(1, max_pages),
        )
    except Exception as exc:
        outcome.warnings.append(
            f"OCR could not render this PDF (poppler/pdf2image error): {exc}"
        )
        return outcome

    chunks: list[str] = []
    for image in images:
        try:
            chunks.append(pytesseract.image_to_string(image) or "")
        except Exception as exc:
            outcome.warnings.append(f"OCR failed on a page (tesseract error): {exc}")
            return outcome

    text = "\n".join(chunks).strip()
    if not text:
        outcome.warnings.append("OCR ran but found no readable text in this PDF.")
        return outcome

    outcome.text = text
    outcome.ocr_used = True
    return outcome


def extract_text_with_optional_ocr(
    content: bytes,
    *,
    existing_text: str | None,
    min_chars: int = MIN_TEXT_CHARS,
    max_pages: int = MAX_OCR_PAGES,
) -> OcrOutcome:
    """Keep extracted text when usable, otherwise fall back to OCR.

    Callers pass whatever their normal text extractor produced. When that text
    is present the OCR path is skipped entirely.
    """
    text = existing_text or ""
    if not looks_scanned(text, min_chars=min_chars):
        return OcrOutcome(text=text, ocr_available=ocr_available())

    if not ocr_available():
        return OcrOutcome(
            text=text,
            ocr_attempted=False,
            ocr_available=False,
            warnings=[OCR_UNAVAILABLE_MESSAGE],
        )

    outcome = ocr_pdf_text(content, max_pages=max_pages)
    if not outcome.ocr_used:
        outcome.text = text
    return outcome


__all__ = [
    "MIN_TEXT_CHARS",
    "OCR_UNAVAILABLE_MESSAGE",
    "OcrOutcome",
    "extract_text_with_optional_ocr",
    "looks_scanned",
    "ocr_available",
    "ocr_pdf_text",
]
