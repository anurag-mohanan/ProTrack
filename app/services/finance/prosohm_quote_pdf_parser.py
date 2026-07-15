"""Parse Prosohm commercial QT-* quote PDFs (not flat finance table packs)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.exceptions import ProTrackValidationError


@dataclass
class ProsohmQuoteExtract:
    external_quote_number: str
    tool_number: str
    quote_date: str | None = None
    prepared_for: str | None = None
    sales_person: str | None = None
    kind_attention: str | None = None
    line_description: str | None = None
    quoted_hours: Decimal = Decimal("0")
    rate: Decimal | None = None
    quoted_revenue: Decimal = Decimal("0")
    currency_code: str = "USD"
    line_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_import_row(self) -> dict[str, object]:
        notes_parts = [part for part in (self.line_notes, self.kind_attention) if part]
        if self.sales_person:
            notes_parts.append(f"Sales person: {self.sales_person}")
        if self.external_quote_number:
            notes_parts.append(f"Quote#: {self.external_quote_number}")
        return {
            "customer": self.prepared_for or "",
            "tool_number": self.tool_number,
            "quoted_hours": self.quoted_hours,
            "estimated_cost": Decimal("0"),
            "quoted_revenue": self.quoted_revenue,
            "currency": self.currency_code,
            "start_date": self.quote_date,
            "version": 1,
            "revision": "A",
            "external_quote_number": self.external_quote_number,
            "notes": "\n".join(notes_parts).strip() or None,
            "line_description": self.line_description,
            "_soft_customer_match": True,
            "_rate": self.rate,
            "_warnings": list(self.warnings),
        }


_QUOTE_NUM_RE = re.compile(
    r"Quote\s*#\s*[:：]?\s*(QT-[A-Z0-9\-]+)",
    re.IGNORECASE,
)
_PROJECT_RE = re.compile(
    r"Customer\s+Project\s*#\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"Quote\s+Date\s*[:：]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)
_SALES_RE = re.compile(
    r"Sales\s+person\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
_KIND_RE = re.compile(
    r"Kind\s+Attention\s*[:：]?\s*(.+)",
    re.IGNORECASE,
)
_TOTAL_MONEY_RE = re.compile(
    r"Total\s+(\$?)\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_SUBTOTAL_RE = re.compile(
    r"Sub\s*Total\s+([\d,]+\.?\d*)\s+(\$?)\s*([\d,]+\.?\d*)?",
    re.IGNORECASE,
)
_LINE_RE = re.compile(
    r"^\s*\d+\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
    re.MULTILINE,
)
_FILENAME_QT_RE = re.compile(r"QT-[A-Z0-9\-]+", re.IGNORECASE)
_FILENAME_HASH_RE = re.compile(r"(?:SY)?#(\d+)", re.IGNORECASE)


def looks_like_prosohm_qt_pdf(*, filename: str | None, text: str) -> bool:
    name = (filename or "").upper()
    if "QT-" in name:
        return True
    has_quote = bool(re.search(r"quote\s*#", text, re.IGNORECASE))
    has_project = bool(re.search(r"customer\s+project\s*#", text, re.IGNORECASE))
    return has_quote and has_project


def _to_decimal(raw: str | None) -> Decimal:
    if raw is None or str(raw).strip() == "":
        return Decimal("0")
    cleaned = str(raw).strip().replace(",", "").replace("$", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ProTrackValidationError(f"Invalid number in quote PDF: {raw}") from exc


def _looks_like_address_line(line: str) -> bool:
    lower = line.lower()
    if re.search(r"\d{3,}", line) and any(
        token in lower for token in ("street", "st ", "road", "rd ", "ave", "suite", "floor", "india", "canada", "usa")
    ):
        return True
    if re.match(r"^\d+[\w\s,.\-/#]*$", line) and len(line) < 80:
        return True
    if re.search(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", line):  # Canadian postal
        return True
    return False


def _clean_customer_candidate(line: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", line).strip(" :\t-")
    if not cleaned or len(cleaned) < 2:
        return None
    if _looks_like_address_line(cleaned):
        return None
    if re.match(r"^(kind\s+attention|#\s*item|quote\s*#)", cleaned, re.IGNORECASE):
        return None
    return cleaned


def _extract_prepared_for(text: str) -> str | None:
    """Extract customer from Prepared For block across common QT PDF layouts."""
    patterns = [
        # Classic multiline until Kind Attention / # Item
        r"Prepared\s+For\s*[:：]?\s*\n(.+?)(?:\n\s*Kind\s+Attention|\n\s*#\s*Item|\n\s*Quote\s*#)",
        # Same-line colon form
        r"Prepared\s+For\s*[:：]\s*([^\n]+)",
        # Label then next non-empty line without requiring Kind Attention
        r"Prepared\s+For\s*[:：]?\s*\n([^\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        block = match.group(1).strip()
        for raw in block.splitlines():
            candidate = _clean_customer_candidate(raw)
            if candidate:
                return candidate
    return None


def recover_customer_from_candidates(
    text: str,
    candidates: list[tuple[str, str]],
) -> str | None:
    """Pick longest active customer name/code appearing in QT text near Prepared For."""
    if not text or not candidates:
        return None
    prepared_idx = text.lower().find("prepared")
    window = text if prepared_idx < 0 else text[max(0, prepared_idx - 40) : prepared_idx + 600]
    haystacks = (window, text)
    best: tuple[int, str] | None = None
    for name, code in candidates:
        for label in (name, code):
            label = (label or "").strip()
            if len(label) < 3:
                continue
            for hay in haystacks:
                if label.lower() in hay.lower():
                    score = len(label) + (50 if hay is window else 0)
                    if best is None or score > best[0]:
                        best = (score, name)
    return best[1] if best else None


def _detect_currency(text: str, amount_has_dollar: bool) -> str:
    if re.search(r"United\s+States\s+Dollar", text, re.IGNORECASE) or amount_has_dollar:
        return "USD"
    if re.search(r"\bINR\b|Indian\s+Rupee|₹", text, re.IGNORECASE):
        return "INR"
    if re.search(r"\bEUR\b|Euro", text, re.IGNORECASE):
        return "EUR"
    if re.search(r"\bCAD\b|Canadian\s+Dollar", text, re.IGNORECASE):
        return "CAD"
    return "USD" if "$" in text else "INR"


def _hints_from_filename(filename: str | None) -> tuple[str | None, str | None]:
    if not filename:
        return None, None
    stem = Path(filename).name
    quote_num = None
    qt_match = _FILENAME_QT_RE.search(stem)
    if qt_match:
        quote_num = qt_match.group(0).upper()
    tool = None
    hash_match = _FILENAME_HASH_RE.search(stem)
    if hash_match:
        tool = hash_match.group(1)
    return quote_num, tool


def extract_prosohm_quote_text(content: bytes) -> str:
    """Reuse workorder PDF text extractors (pdfplumber → pypdf → stdlib)."""
    from app.services.workorder_pdf_extract import extract_pdf_text

    return extract_pdf_text(content)


def parse_prosohm_quote_text(
    text: str,
    *,
    filename: str | None = None,
    customer_candidates: list[tuple[str, str]] | None = None,
) -> ProsohmQuoteExtract:
    if not text or not text.strip():
        raise ProTrackValidationError("Prosohm QT PDF has no extractable text.")

    file_quote, file_tool = _hints_from_filename(filename)
    warnings: list[str] = []

    quote_match = _QUOTE_NUM_RE.search(text)
    external_quote_number = (
        quote_match.group(1).strip().upper() if quote_match else (file_quote or "")
    )
    if not external_quote_number:
        raise ProTrackValidationError("Could not find Quote# on Prosohm QT PDF.")

    project_match = _PROJECT_RE.search(text)
    tool_number = (
        project_match.group(1).strip() if project_match else (file_tool or "")
    )
    if not tool_number:
        raise ProTrackValidationError(
            "Could not find Customer Project # on Prosohm QT PDF."
        )

    date_match = _DATE_RE.search(text)
    quote_date = date_match.group(1).strip() if date_match else None

    sales_match = _SALES_RE.search(text)
    sales_person = sales_match.group(1).strip() if sales_match else None
    if sales_person:
        sales_person = re.split(r"\s{2,}|Customer\s+Project", sales_person)[0].strip()

    prepared_for = _extract_prepared_for(text)
    if not prepared_for and customer_candidates:
        prepared_for = recover_customer_from_candidates(text, customer_candidates)
        if prepared_for:
            warnings.append("Prepared For recovered via customer AI match against directory")
    if not prepared_for:
        raise ProTrackValidationError(
            "Could not find Prepared For customer on Prosohm QT PDF."
        )

    kind_match = _KIND_RE.search(text)
    kind_attention = kind_match.group(1).strip() if kind_match else None

    line_match = _LINE_RE.search(text)
    line_description = None
    hours = Decimal("0")
    rate: Decimal | None = None
    amount = Decimal("0")
    if line_match:
        line_description = line_match.group(1).strip()
        hours = _to_decimal(line_match.group(2))
        rate = _to_decimal(line_match.group(3))
        amount = _to_decimal(line_match.group(4))

    dollar_flag = False
    total_match = _TOTAL_MONEY_RE.search(text)
    if total_match:
        dollar_flag = bool(total_match.group(1)) or "$" in total_match.group(0)
        total_amount = _to_decimal(total_match.group(2))
        if total_amount > 0:
            amount = total_amount

    sub_match = _SUBTOTAL_RE.search(text)
    if sub_match and amount == 0:
        amount = _to_decimal(sub_match.group(1))
        dollar_flag = dollar_flag or bool(sub_match.group(2))

    if hours == 0 or amount == 0:
        raise ProTrackValidationError(
            "Could not find Qty/Hrs and Amount/Total on Prosohm QT PDF."
        )

    if rate is not None and hours and amount:
        expected = (hours * rate).quantize(Decimal("0.01"))
        if abs(expected - amount) > Decimal("0.05"):
            warnings.append(
                f"Hours × rate ({expected}) does not match amount ({amount}); imported amount as printed."
            )

    phase_lines = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"\d+\s*hrs?", line, re.IGNORECASE)
        and not re.match(r"^\s*\d+\s+", line)
    ]
    notes_bits: list[str] = []
    if line_description:
        notes_bits.append(line_description)
    notes_bits.extend(phase_lines[:8])

    currency = _detect_currency(text, amount_has_dollar=dollar_flag or "$" in text)

    return ProsohmQuoteExtract(
        external_quote_number=external_quote_number,
        tool_number=tool_number,
        quote_date=quote_date,
        prepared_for=prepared_for,
        sales_person=sales_person,
        kind_attention=kind_attention,
        line_description=line_description,
        quoted_hours=hours,
        rate=rate,
        quoted_revenue=amount,
        currency_code=currency,
        line_notes="\n".join(notes_bits),
        warnings=warnings,
    )


def parse_prosohm_quote_pdf(
    content: bytes,
    *,
    filename: str | None = None,
) -> ProsohmQuoteExtract:
    text = extract_prosohm_quote_text(content)
    if not looks_like_prosohm_qt_pdf(filename=filename, text=text):
        raise ProTrackValidationError("PDF is not a Prosohm QT quote layout.")
    return parse_prosohm_quote_text(text, filename=filename)
