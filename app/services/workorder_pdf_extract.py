"""Heuristic workorder PDF text extraction for Overview autofill (RC5).

Customer layouts differ; this returns suggested fields for human review — it does not
persist. Per-customer templates / OCR can replace heuristics later.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from app.core.exceptions import ProTrackValidationError

_MAX_PDF_BYTES = 12 * 1024 * 1024

_LABEL_VALUE = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 /#\.\-]{1,40}?)\s*[:\-–]\s*(?P<value>[^\n\r]{1,120})",
    re.IGNORECASE,
)


@dataclass
class WorkorderExtract:
    part_description: str | None = None
    work_order_number: str | None = None
    press_tonnage: str | None = None
    plastic_material: str | None = None
    cavity_count: int | None = None
    tool_type: str | None = None
    customer_specs: str | None = None
    warnings: list[str] = field(default_factory=list)
    source_chars: int = 0


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("\u00a0", " ").split()).strip(" -:;")
    return cleaned or None


def _norm_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _match_label_bucket(label: str) -> str | None:
    n = _norm_label(label)
    if any(token in n for token in ("work order", "workorder", " wo ", "wo no", "wo number", "order no", "order number", "customer order")):
        return "work_order_number"
    if n in {"wo", "w o"} or n.startswith("wo "):
        return "work_order_number"
    if any(token in n for token in ("tonnage", "press ton", "clamp", "press size", "machine ton")):
        return "press_tonnage"
    if any(token in n for token in ("plastic", "material", "resin", "polymer", "grade")):
        return "plastic_material"
    if any(token in n for token in ("cavity", "cavities", "no of cav", "number of cavity")):
        return "cavity_count"
    if any(token in n for token in ("tool type", "mould type", "mold type", "tooling type", "type of tool")):
        return "tool_type"
    if any(
        token in n
        for token in (
            "part description",
            "part name",
            "component",
            "description",
            "product name",
            "part no description",
        )
    ):
        return "part_description"
    if any(token in n for token in ("specification", "specs", "requirement", "special note", "remarks")):
        return "customer_specs"
    return None


def _parse_cavity(value: str) -> int | None:
    match = re.search(r"(\d{1,3})", value)
    if not match:
        return None
    count = int(match.group(1))
    return count if 0 <= count <= 128 else None


def _parse_tonnage(value: str) -> str | None:
    match = re.search(
        r"(\d{2,5}(?:[.,]\d+)?)\s*(t|ton|tons|tonne|tonnes)?\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        cleaned = _clean(value)
        return cleaned[:50] if cleaned else None
    amount = match.group(1).replace(",", "")
    # Press sizes are whole tons (e.g. 650, 2200) — drop stray decimals from OCR.
    if "." in amount:
        amount = amount.split(".", 1)[0]
    if not amount.isdigit():
        return None
    tons = int(amount)
    # Guard against tool-size noise (e.g. 1.25" bolt text partials misread as tonnage).
    if tons < 50 or tons > 10000:
        return None
    return f"{tons}T"


def _find_press_tonnage(text: str) -> str | None:
    """
    Customer notes often write freeform lines like ``2200T Press 308`` rather than
    ``Press Tonnage: 2200T``. Prefer press-context matches, then labelled tonnage.
    """
    patterns = (
        # "2200T Press 308" / "2200 T Press"
        r"\b(\d{3,5})\s*[Tt]\s+[Pp]ress\b",
        # "Press 2200T" / "Press: 2200 T" / "Press tonnage 2200T"
        r"\b[Pp]ress(?:\s*tonnage)?\s*[:#\-]?\s*(\d{3,5})\s*[Tt]\b",
        # "Tonnage: 2200T" / "Press Tonnage - 2200 ton"
        r"(?:press\s*)?tonnage\s*[:\-#]?\s*(\d{2,5}(?:[.,]\d+)?)\s*[Tt](?:on(?:ne)?s?)?\b",
        # Same line contains both press + NNNNT
        r"(?im)^(?=.*\bpress\b).{0,80}?\b(\d{3,5})\s*[Tt]\b",
        r"(?im)^.{0,80}?\b(\d{3,5})\s*[Tt]\b(?=.*\bpress\b).{0,40}$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not match:
            continue
        parsed = _parse_tonnage(match.group(1) + "T")
        if parsed:
            return parsed
    return None


def _apply_field(result: WorkorderExtract, bucket: str, raw: str) -> None:
    value = _clean(raw)
    if not value:
        return
    if bucket == "work_order_number" and not result.work_order_number:
        result.work_order_number = value[:100]
    elif bucket == "press_tonnage" and not result.press_tonnage:
        result.press_tonnage = (_parse_tonnage(value) or value)[:50]
    elif bucket == "plastic_material" and not result.plastic_material:
        result.plastic_material = value[:150]
    elif bucket == "cavity_count" and result.cavity_count is None:
        result.cavity_count = _parse_cavity(value)
    elif bucket == "tool_type" and not result.tool_type:
        result.tool_type = value[:100]
    elif bucket == "part_description" and not result.part_description:
        result.part_description = value[:255]
    elif bucket == "customer_specs":
        if result.customer_specs:
            if value not in result.customer_specs:
                result.customer_specs = f"{result.customer_specs}\n{value}"[:4000]
        else:
            result.customer_specs = value[:4000]


def _scan_label_value_pairs(text: str, result: WorkorderExtract) -> None:
    for match in _LABEL_VALUE.finditer(text):
        bucket = _match_label_bucket(match.group("label"))
        if bucket:
            _apply_field(result, bucket, match.group("value"))


def _scan_loose_patterns(text: str, result: WorkorderExtract) -> None:
    if not result.work_order_number:
        match = re.search(
            r"(?:work\s*order|w\.?\s*o\.?|wo)\s*(?:no|number|#)?\s*[:\-#]?\s*([A-Za-z0-9][\w\-/.]{1,40})",
            text,
            re.IGNORECASE,
        )
        if match:
            _apply_field(result, "work_order_number", match.group(1))

    if not result.press_tonnage:
        found = _find_press_tonnage(text)
        if found:
            result.press_tonnage = found

    if not result.plastic_material:
        match = re.search(
            r"(?:plastic\s*)?material\s*[:\-#]?\s*([A-Za-z0-9][A-Za-z0-9 \-/%+.]{1,80})",
            text,
            re.IGNORECASE,
        )
        if match:
            _apply_field(result, "plastic_material", match.group(1))

    if result.cavity_count is None:
        match = re.search(
            r"(?:no\.?\s*of\s*)?cavit(?:y|ies)\s*[:\-#]?\s*(\d{1,3})",
            text,
            re.IGNORECASE,
        )
        if match:
            _apply_field(result, "cavity_count", match.group(1))


def _scan_table_cells(content: bytes, result: WorkorderExtract) -> None:
    try:
        import pdfplumber
    except ImportError:
        return

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:8]:
                for table in page.extract_tables() or []:
                    for row in table or []:
                        if not row:
                            continue
                        cells = [str(cell or "").strip() for cell in row]
                        if len(cells) >= 2:
                            bucket = _match_label_bucket(cells[0])
                            if bucket:
                                _apply_field(result, bucket, " ".join(cells[1:]))
                        # flattened "Label Value" in one cell handled by text scan
    except Exception:  # noqa: BLE001 — tables are optional enrichment
        result.warnings.append("Could not read some PDF tables; used page text only.")


def _unescape_pdf_literal(raw: bytes) -> str:
    text = raw.decode("latin-1", errors="ignore")
    text = text.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")
    text = text.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return text


def _extract_text_stdlib(content: bytes) -> str:
    """
    Best-effort text scrape with no third-party PDF libs.
    Works for many simple text workorders; not a substitute for pdfplumber on complex PDFs.
    """
    parts: list[str] = []
    for match in re.finditer(rb"\(((?:\\.|[^\\()\r\n])*)\)", content):
        value = _unescape_pdf_literal(match.group(1)).strip()
        if len(value) >= 2 and any(ch.isalnum() for ch in value):
            parts.append(value)

    # TJ arrays: [(Hello) 10 (World)] style
    for match in re.finditer(rb"\[(.*?)\]\s*TJ", content, flags=re.IGNORECASE | re.DOTALL):
        chunk_parts: list[str] = []
        for inner in re.finditer(rb"\(((?:\\.|[^\\()])*)\)", match.group(1)):
            value = _unescape_pdf_literal(inner.group(1)).strip()
            if value:
                chunk_parts.append(value)
        if chunk_parts:
            parts.append("".join(chunk_parts))

    # Readable ASCII lines embedded in the file (helps some exporters)
    latin = content.decode("latin-1", errors="ignore")
    for line in latin.splitlines():
        cleaned = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in line)
        cleaned = " ".join(cleaned.split())
        if len(cleaned) < 8:
            continue
        lower = cleaned.lower()
        if any(
            token in lower
            for token in (
                "work order",
                "tonnage",
                "material",
                "cavity",
                "tool type",
                "part description",
                "plastic",
                "general notes",
                "press",
            )
        ) or re.search(r"\b\d{3,5}\s*t\b", cleaned, re.IGNORECASE):
            parts.append(cleaned)

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(part)
    return "\n".join(ordered).strip()


def _extract_text_pdfplumber(content: bytes) -> str:
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        if not pdf.pages:
            raise ProTrackValidationError("PDF has no pages.")
        for page in pdf.pages[:12]:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_text_pypdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    if not reader.pages:
        raise ProTrackValidationError("PDF has no pages.")
    chunks: list[str] = []
    for page in reader.pages[:12]:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return "\n".join(chunks).strip()


def extract_pdf_text(content: bytes) -> str:
    """Extract page text; prefer pdfplumber, then pypdf, then stdlib scrape."""
    errors: list[str] = []

    try:
        combined = _extract_text_pdfplumber(content)
        if combined:
            return combined
        errors.append("pdfplumber found no text")
    except ImportError:
        errors.append("pdfplumber not installed")
    except ProTrackValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pdfplumber failed: {exc}")

    try:
        combined = _extract_text_pypdf(content)
        if combined:
            return combined
        errors.append("pypdf found no text")
    except ImportError:
        errors.append("pypdf not installed")
    except ProTrackValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pypdf failed: {exc}")

    try:
        combined = _extract_text_stdlib(content)
        if combined:
            return combined
        errors.append("stdlib scrape found no text")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"stdlib scrape failed: {exc}")

    if any("found no text" in item for item in errors):
        raise ProTrackValidationError(
            "No extractable text found. Use a text-based PDF (not a scanned image) or enter details manually."
            + (
                " Tip: on the API host run `pip install -r requirements.txt` then restart for better PDF support."
                if any("not installed" in item for item in errors)
                else ""
            )
        )

    raise ProTrackValidationError(
        f"Could not read workorder PDF ({'; '.join(errors)}). "
        "On the API host run: pip install -r requirements.txt  then restart the API, "
        "or enter details manually."
    )


def extract_workorder_fields_from_text(text: str) -> WorkorderExtract:
    result = WorkorderExtract(source_chars=len(text))
    _scan_label_value_pairs(text, result)
    _scan_loose_patterns(text, result)
    if not any(
        [
            result.part_description,
            result.work_order_number,
            result.press_tonnage,
            result.plastic_material,
            result.cavity_count is not None,
            result.tool_type,
            result.customer_specs,
        ]
    ):
        result.warnings.append(
            "No labelled fields matched. Review the PDF and fill details manually, or adjust wording (Work Order, Tonnage, Material, Cavity)."
        )
    return result


def extract_workorder_fields_from_pdf(content: bytes) -> WorkorderExtract:
    if not content:
        raise ProTrackValidationError("PDF file is empty.")
    if len(content) > _MAX_PDF_BYTES:
        raise ProTrackValidationError("PDF exceeds the 12 MB limit.")

    text = extract_pdf_text(content)
    result = extract_workorder_fields_from_text(text)
    # Note stdlib fallback quality for UI/ops.
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        result.warnings.append(
            "pdfplumber is not installed on the API host; used built-in PDF text scrape. "
            "Install requirements for better accuracy: pip install -r requirements.txt"
        )
    _scan_table_cells(content, result)
    return result
