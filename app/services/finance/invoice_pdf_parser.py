"""Invoice PDF text extraction — candidates only; never invent missing values."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


@dataclass
class FieldCandidate:
    value: str | None = None
    confidence: float = 0.0
    source: str | None = None
    needs_review: bool = False


@dataclass
class InvoicePdfExtract:
    invoice_number: FieldCandidate = field(default_factory=FieldCandidate)
    invoice_date: FieldCandidate = field(default_factory=FieldCandidate)
    due_date: FieldCandidate = field(default_factory=FieldCandidate)
    amount: FieldCandidate = field(default_factory=FieldCandidate)
    currency_code: FieldCandidate = field(default_factory=FieldCandidate)
    customer_name: FieldCandidate = field(default_factory=FieldCandidate)
    project_ref: FieldCandidate = field(default_factory=FieldCandidate)
    po_number: FieldCandidate = field(default_factory=FieldCandidate)
    quote_ref: FieldCandidate = field(default_factory=FieldCandidate)
    tax_amount: FieldCandidate = field(default_factory=FieldCandidate)
    subtotal: FieldCandidate = field(default_factory=FieldCandidate)
    notes: FieldCandidate = field(default_factory=FieldCandidate)
    warnings: list[str] = field(default_factory=list)
    source_chars: int = 0
    text_extractable: bool = True
    ocr_used: bool = False
    content_sha256: str | None = None
    filename: str | None = None


_INVOICE_NO_RE = re.compile(
    r"(?:Invoice\s*(?:No\.?|Number|#)|Inv\.?\s*#)\s*[:：]?\s*([A-Z0-9][A-Z0-9\-_/]+)",
    re.IGNORECASE,
)
_DATE_LABEL_RE = re.compile(
    r"(?:Invoice\s*Date|Date\s*of\s*Invoice|Inv\.?\s*Date)\s*[:：]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_DUE_DATE_RE = re.compile(
    r"(?:Due\s*Date|Payment\s*Due)\s*[:：]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_TOTAL_RE = re.compile(
    r"(?:Grand\s*Total|Invoice\s*Total|Total\s*Amount|Amount\s*Due|Total)\s*"
    r"[:：]?\s*(₹|INR|USD|\$|€)?\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_SUBTOTAL_RE = re.compile(
    r"(?:Sub\s*Total|Subtotal)\s*[:：]?\s*(₹|INR|USD|\$)?\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_TAX_RE = re.compile(
    r"(?:GST|IGST|CGST\s*\+\s*SGST|Tax)\s*(?:Amount)?\s*[:：]?\s*(₹|INR|USD|\$)?\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_CUSTOMER_RE = re.compile(
    r"(?:Bill\s*To|Billed\s*To|Customer|Buyer|Prepared\s*For)\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
_PO_RE = re.compile(
    r"(?:P\.?O\.?\s*(?:No\.?|Number|#)|Purchase\s*Order)\s*[:：]?\s*([A-Z0-9][A-Z0-9\-_/]+)",
    re.IGNORECASE,
)
_PROJECT_RE = re.compile(
    r"(?:Project\s*(?:No\.?|Number|#|Ref)|Tool\s*(?:No\.?|#)|Customer\s+Project\s*#)\s*[:：]?\s*"
    r"([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)
_QUOTE_RE = re.compile(
    r"(?:Quote\s*(?:No\.?|Number|#)|QT-)\s*[:：]?\s*((?:QT-)?[A-Z0-9\-]+)",
    re.IGNORECASE,
)
_CURRENCY_HINT_RE = re.compile(r"\b(INR|USD|EUR|GBP)\b", re.IGNORECASE)


def _parse_money(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _parse_date(raw: str) -> str | None:
    text = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _currency_from_symbol(symbol: str | None, text: str) -> FieldCandidate:
    sym = (symbol or "").strip()
    if sym in {"₹", "INR"} or "₹" in text:
        return FieldCandidate(value="INR", confidence=90, source="symbol")
    if sym in {"$", "USD"}:
        return FieldCandidate(value="USD", confidence=75, source="symbol")
    if sym in {"€", "EUR"}:
        return FieldCandidate(value="EUR", confidence=75, source="symbol")
    hint = _CURRENCY_HINT_RE.search(text)
    if hint:
        return FieldCandidate(
            value=hint.group(1).upper(), confidence=70, source="text_hint"
        )
    return FieldCandidate(value=None, confidence=0, needs_review=True)


def content_fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_invoice_pdf_text(
    text: str,
    *,
    filename: str | None = None,
    content_sha256: str | None = None,
) -> InvoicePdfExtract:
    """Extract invoice candidates. Missing fields stay empty — never invented."""
    result = InvoicePdfExtract(
        source_chars=len(text or ""),
        filename=filename,
        content_sha256=content_sha256,
    )
    if not (text or "").strip():
        result.text_extractable = False
        result.warnings.append(
            "No extractable text. Use a text-based PDF (OCR for scanned PDFs is not enabled yet) "
            "or enter the invoice manually."
        )
        return result

    inv = _INVOICE_NO_RE.search(text)
    if inv:
        result.invoice_number = FieldCandidate(
            value=inv.group(1).strip(), confidence=92, source="regex_invoice_no"
        )
    else:
        result.invoice_number.needs_review = True
        result.warnings.append("Invoice number not detected — needs review.")

    date_m = _DATE_LABEL_RE.search(text)
    if date_m:
        iso = _parse_date(date_m.group(1))
        if iso:
            result.invoice_date = FieldCandidate(
                value=iso, confidence=90, source="regex_invoice_date"
            )
        else:
            result.invoice_date = FieldCandidate(
                value=date_m.group(1), confidence=40, source="regex_raw_date", needs_review=True
            )
            result.warnings.append("Invoice date found but format needs confirmation.")
    else:
        result.invoice_date.needs_review = True
        result.warnings.append(
            "Invoice date not detected. Do not invent a date — enter it manually."
        )

    due_m = _DUE_DATE_RE.search(text)
    if due_m:
        iso = _parse_date(due_m.group(1))
        if iso:
            result.due_date = FieldCandidate(value=iso, confidence=80, source="regex_due_date")

    # Prefer "Grand Total" / "Invoice Total" over bare "Total" — scan all, take last high-signal
    totals = list(_TOTAL_RE.finditer(text))
    if totals:
        best = totals[-1]
        money = _parse_money(best.group(2))
        if money is not None and money > 0:
            result.amount = FieldCandidate(
                value=str(money), confidence=88, source="regex_total"
            )
            result.currency_code = _currency_from_symbol(best.group(1), text)
    if not result.amount.value:
        result.amount.needs_review = True
        result.warnings.append("Invoice total not detected confidently — needs review.")

    sub = _SUBTOTAL_RE.search(text)
    if sub:
        money = _parse_money(sub.group(2))
        if money is not None:
            result.subtotal = FieldCandidate(
                value=str(money), confidence=75, source="regex_subtotal"
            )

    tax = _TAX_RE.search(text)
    if tax:
        money = _parse_money(tax.group(2))
        if money is not None:
            result.tax_amount = FieldCandidate(
                value=str(money), confidence=70, source="regex_tax"
            )

    if result.subtotal.value and result.tax_amount.value and result.amount.value:
        try:
            expected = Decimal(result.subtotal.value) + Decimal(result.tax_amount.value)
            actual = Decimal(result.amount.value)
            if abs(expected - actual) > Decimal("1.00"):
                result.warnings.append(
                    f"Subtotal + tax ({expected}) does not equal total ({actual}) — verify before import."
                )
                result.amount.needs_review = True
        except InvalidOperation:
            pass

    cust = _CUSTOMER_RE.search(text)
    if cust:
        name = re.sub(r"\s+", " ", cust.group(1)).strip(" .:;\t")
        if name and len(name) > 1:
            result.customer_name = FieldCandidate(
                value=name[:200], confidence=78, source="regex_customer"
            )
    else:
        result.customer_name.needs_review = True
        result.warnings.append("Customer not detected — select manually.")

    po = _PO_RE.search(text)
    if po:
        result.po_number = FieldCandidate(
            value=po.group(1).strip(), confidence=85, source="regex_po"
        )

    proj = _PROJECT_RE.search(text)
    if proj:
        result.project_ref = FieldCandidate(
            value=proj.group(1).strip(), confidence=80, source="regex_project"
        )

    quote = _QUOTE_RE.search(text)
    if quote:
        ref = quote.group(1).strip()
        if not ref.upper().startswith("QT-") and "QT-" in text.upper():
            # keep as-is
            pass
        result.quote_ref = FieldCandidate(value=ref, confidence=82, source="regex_quote")

    note_bits = []
    if result.invoice_number.value:
        note_bits.append(f"Invoice#: {result.invoice_number.value}")
    if result.po_number.value:
        note_bits.append(f"PO: {result.po_number.value}")
    if note_bits:
        result.notes = FieldCandidate(
            value=" | ".join(note_bits), confidence=60, source="composed"
        )

    if filename and not result.invoice_number.value:
        stem = re.sub(r"[^A-Za-z0-9\-_/]+", "-", filename.rsplit(".", 1)[0])
        if stem:
            result.invoice_number = FieldCandidate(
                value=stem[:80], confidence=25, source="filename", needs_review=True
            )
            result.warnings.append("Invoice number guessed from filename — confirm or clear.")

    return result
