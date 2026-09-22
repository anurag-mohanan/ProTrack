"""Shared Prosohm finance document helpers — stages, dates, classification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation


@dataclass
class StageHourLine:
    label: str
    hours: Decimal
    source_line: str


@dataclass
class StageHoursExtract:
    stages: list[StageHourLine] = field(default_factory=list)
    stage_hours_sum: Decimal = Decimal("0")
    description_total_hours: Decimal | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentClassification:
    document_type: str  # quote | invoice | unknown
    confidence: float
    signals: list[str] = field(default_factory=list)


_MONTH_NAME_DATE_RE = re.compile(
    r"(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

# Stage lines like "ROUGHING STAGE DESIGN: 40" or "FEASE: 10 Hrs."
_STAGE_LINE_RE = re.compile(
    r"^[\s\-•]*"
    r"([A-Za-z][A-Za-z0-9+/\s&\-]{2,80}?)"
    r"\s*[:\-–—=]\s*"
    r"([\d,]+\.?\d*)"
    r"\s*(?:hrs?\.?)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_STAGE_TOTAL_RE = re.compile(
    r"^\s*TOTAL\s*[:\-–—=]?\s*([\d,]+\.?\d*)\s*(?:hrs?\.?)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SKIP_STAGE_LABELS = {
    "sub total",
    "subtotal",
    "grand total",
    "balance due",
    "amount",
    "rate",
    "qty",
    "qty/hrs",
}


def parse_prosohm_date(raw: str | None) -> str | None:
    """Parse Prosohm date strings to ISO YYYY-MM-DD. Returns None if unparseable."""
    if not raw:
        return None
    text = str(raw).strip()
    month_m = _MONTH_NAME_DATE_RE.search(text)
    if month_m:
        try:
            return datetime.strptime(
                f"{month_m.group(1)} {month_m.group(2)} {month_m.group(3)}",
                "%d %B %Y",
            ).date().isoformat()
        except ValueError:
            try:
                return datetime.strptime(
                    f"{month_m.group(1)} {month_m.group(2)} {month_m.group(3)}",
                    "%d %b %Y",
                ).date().isoformat()
            except ValueError:
                pass
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%m/%d/%Y",
        "%d %B %Y",
        "%d %b %Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_hours(raw: str) -> Decimal | None:
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def extract_stage_hours(text: str) -> StageHoursExtract:
    """Extract work-stage hour lines and description TOTAL from Prosohm quote/invoice text."""
    result = StageHoursExtract()
    if not text:
        return result

    total_m = _STAGE_TOTAL_RE.search(text)
    if total_m:
        hours = _to_hours(total_m.group(1))
        if hours is not None and hours > 0:
            result.description_total_hours = hours

    for match in _STAGE_LINE_RE.finditer(text):
        label = re.sub(r"\s+", " ", match.group(1)).strip(" :\t-")
        label_l = label.lower()
        if label_l in _SKIP_STAGE_LABELS or label_l.startswith("total"):
            continue
        if "united states dollar" in label_l or "looking forward" in label_l:
            continue
        hours = _to_hours(match.group(2))
        if hours is None or hours <= 0:
            continue
        # Ignore money-like lines misread as stages (e.g. large totals)
        if hours > 5000:
            continue
        result.stages.append(
            StageHourLine(label=label, hours=hours, source_line=match.group(0).strip())
        )

    result.stage_hours_sum = sum((s.hours for s in result.stages), Decimal("0"))
    return result


def detect_hours_discrepancy(
    *,
    table_quantity: Decimal | None,
    stages: StageHoursExtract,
) -> list[str]:
    """Flag conflicts between table qty, stage sum, and description TOTAL — never auto-correct."""
    warnings: list[str] = []
    qty = table_quantity if table_quantity is not None else None
    stage_sum = stages.stage_hours_sum if stages.stages else None
    desc_total = stages.description_total_hours

    if qty is not None and stage_sum is not None and stage_sum > 0 and abs(qty - stage_sum) > Decimal("0.01"):
        warnings.append(
            f"DATA REVIEW REQUIRED: Table quantity ({qty}) differs from stage-hour sum ({stage_sum}). "
            "Do not auto-correct - confirm the commercial hours."
        )
    if (
        qty is not None
        and desc_total is not None
        and abs(qty - desc_total) > Decimal("0.01")
    ):
        warnings.append(
            f"DATA REVIEW REQUIRED: Document contains multiple hour totals that do not agree "
            f"(table quantity {qty} vs description TOTAL {desc_total})."
        )
    if (
        stage_sum is not None
        and stage_sum > 0
        and desc_total is not None
        and abs(stage_sum - desc_total) > Decimal("0.01")
    ):
        warnings.append(
            f"DATA REVIEW REQUIRED: Stage breakdown sum ({stage_sum}) differs from description "
            f"TOTAL ({desc_total})."
        )
    return warnings


def classify_finance_document(*, text: str, filename: str | None = None) -> DocumentClassification:
    """Classify quote vs invoice from content signals (not filename alone)."""
    body = text or ""
    name = (filename or "").upper()
    signals: list[str] = []
    quote_score = 0.0
    invoice_score = 0.0

    if re.search(r"\bQUOTE\b", body, re.IGNORECASE) or "QT-" in name:
        quote_score += 30
        signals.append("QUOTE heading / QT filename")
    if re.search(r"Quote\s*#", body, re.IGNORECASE):
        quote_score += 35
        signals.append("Quote #")
    if re.search(r"Quote\s+Date", body, re.IGNORECASE):
        quote_score += 15
        signals.append("Quote Date")
    if re.search(r"Prepared\s+For", body, re.IGNORECASE):
        quote_score += 10
        signals.append("Prepared For")

    if re.search(r"\bINVOICE\b", body, re.IGNORECASE) or "INV-" in name:
        invoice_score += 30
        signals.append("INVOICE heading / INV filename")
    if re.search(r"Invoice\s*#", body, re.IGNORECASE):
        invoice_score += 35
        signals.append("Invoice #")
    if re.search(r"Invoice\s+Date", body, re.IGNORECASE):
        invoice_score += 15
        signals.append("Invoice Date")
    if re.search(r"Balance\s+Due", body, re.IGNORECASE):
        invoice_score += 20
        signals.append("Balance Due")
    if re.search(r"Bill\s+To", body, re.IGNORECASE):
        invoice_score += 10
        signals.append("Bill To")

    if re.search(r"Customer\s+Project\s*#", body, re.IGNORECASE):
        signals.append("Customer Project #")
        quote_score += 5
        invoice_score += 5

    if quote_score >= invoice_score and quote_score >= 40:
        return DocumentClassification(
            document_type="quote",
            confidence=min(99.0, quote_score),
            signals=signals,
        )
    if invoice_score > quote_score and invoice_score >= 40:
        return DocumentClassification(
            document_type="invoice",
            confidence=min(99.0, invoice_score),
            signals=signals,
        )
    return DocumentClassification(
        document_type="unknown",
        confidence=max(quote_score, invoice_score),
        signals=signals,
    )


def stages_as_dicts(stages: StageHoursExtract) -> list[dict]:
    return [
        {
            "label": s.label,
            "hours": float(s.hours),
            "source_line": s.source_line,
        }
        for s in stages.stages
    ]
