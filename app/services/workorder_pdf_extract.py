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
        r"(\d{2,4}(?:[.,]\d+)?)\s*(t|ton|tons|tonne|tonnes)?\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        cleaned = _clean(value)
        return cleaned[:50] if cleaned else None
    amount = match.group(1).replace(",", "")
    unit = (match.group(2) or "T").upper()
    if unit.startswith("T"):
        unit = "T"
    return f"{amount}{unit}"


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
        match = re.search(
            r"(?:press\s*)?tonnage\s*[:\-#]?\s*(\d{2,4}(?:[.,]\d+)?\s*t(?:on(?:ne)?s?)?)",
            text,
            re.IGNORECASE,
        ) or re.search(r"\b(\d{2,4})\s*t(?:on(?:ne)?s?)?\b", text, re.IGNORECASE)
        if match:
            _apply_field(result, "press_tonnage", match.group(1))

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


def extract_pdf_text(content: bytes) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ProTrackValidationError(
            "PDF import requires pdfplumber. Install dependencies or enter details manually."
        ) from exc

    chunks: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if not pdf.pages:
                raise ProTrackValidationError("PDF has no pages.")
            for page in pdf.pages[:12]:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text)
    except ProTrackValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProTrackValidationError(f"Could not read workorder PDF: {exc}") from exc

    combined = "\n".join(chunks).strip()
    if not combined:
        raise ProTrackValidationError(
            "No extractable text found. Use a text-based PDF (not a scanned image) or enter details manually."
        )
    return combined


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
    _scan_table_cells(content, result)
    return result
