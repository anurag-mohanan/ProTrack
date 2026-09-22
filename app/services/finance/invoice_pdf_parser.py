"""Invoice PDF text extraction — candidates only; never invent missing values."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
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
    balance_due: FieldCandidate = field(default_factory=FieldCandidate)
    payment_terms: FieldCandidate = field(default_factory=FieldCandidate)
    sales_person: FieldCandidate = field(default_factory=FieldCandidate)
    billing_attention: FieldCandidate = field(default_factory=FieldCandidate)
    quantity: FieldCandidate = field(default_factory=FieldCandidate)
    rate: FieldCandidate = field(default_factory=FieldCandidate)
    line_description: FieldCandidate = field(default_factory=FieldCandidate)
    notes: FieldCandidate = field(default_factory=FieldCandidate)
    stage_hours: list[dict] = field(default_factory=list)
    raw_table_quantity: FieldCandidate = field(default_factory=FieldCandidate)
    raw_description_total_hours: FieldCandidate = field(default_factory=FieldCandidate)
    stage_hours_sum: FieldCandidate = field(default_factory=FieldCandidate)
    document_type: str = "invoice"
    document_type_confidence: float = 0.0
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
    r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_DUE_DATE_RE = re.compile(
    r"(?:Due\s*Date|Payment\s*Due)\s*[:：]?\s*"
    r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_BALANCE_DUE_RE = re.compile(
    r"Balance\s*Due\s*[:：]?\s*(\$?|USD|INR|₹)?\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_TERMS_RE = re.compile(
    r"Terms\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
_SALES_RE = re.compile(
    r"Sales\s+person\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
_BILLING_ATTN_RE = re.compile(
    r"Billing\s+Attention\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
_LINE_RE = re.compile(
    r"^\s*\d+\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
    re.MULTILINE,
)
_BILL_TO_BLOCK_RE = re.compile(
    r"Bill\s+To\s*[:：]?\s*\n([^\n]+)",
    re.IGNORECASE,
)
_CUSTOMER_PROJECT_RE = re.compile(
    r"Customer\s+Project\s*#\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
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
    from app.services.finance.prosohm_document_intelligence import parse_prosohm_date

    return parse_prosohm_date(raw)


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
    bill_block = _BILL_TO_BLOCK_RE.search(text)
    if bill_block:
        name = re.sub(r"\s+", " ", bill_block.group(1)).strip(" :;\t")
        if name and len(name) > 1:
            result.customer_name = FieldCandidate(
                value=name[:200], confidence=90, source="bill_to"
            )
    elif cust:
        name = re.sub(r"\s+", " ", cust.group(1)).strip(" :;\t")
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

    # Prefer explicit Customer Project # (ProTrack project number).
    cust_proj = _CUSTOMER_PROJECT_RE.search(text)
    proj = _PROJECT_RE.search(text)
    if cust_proj:
        result.project_ref = FieldCandidate(
            value=cust_proj.group(1).strip(), confidence=98, source="customer_project_number"
        )
    elif proj:
        result.project_ref = FieldCandidate(
            value=proj.group(1).strip(), confidence=80, source="regex_project"
        )

    quote = _QUOTE_RE.search(text)
    if quote:
        ref = quote.group(1).strip()
        result.quote_ref = FieldCandidate(value=ref, confidence=82, source="regex_quote")

    bal = _BALANCE_DUE_RE.search(text)
    if bal:
        money = _parse_money(bal.group(2))
        if money is not None:
            result.balance_due = FieldCandidate(
                value=str(money), confidence=92, source="balance_due"
            )
            if not result.amount.value:
                result.amount = FieldCandidate(
                    value=str(money), confidence=85, source="balance_due"
                )
                result.currency_code = _currency_from_symbol(bal.group(1), text)

    terms = _TERMS_RE.search(text)
    if terms:
        term_val = re.split(r"\s{2,}|Customer\s+Project", terms.group(1))[0].strip()
        if term_val:
            result.payment_terms = FieldCandidate(
                value=term_val[:200], confidence=80, source="terms"
            )

    sales = _SALES_RE.search(text)
    if sales:
        sales_val = re.split(r"\s{2,}|Customer\s+Project", sales.group(1))[0].strip()
        if sales_val:
            result.sales_person = FieldCandidate(
                value=sales_val[:120], confidence=75, source="sales_person"
            )

    attn = _BILLING_ATTN_RE.search(text)
    if attn:
        result.billing_attention = FieldCandidate(
            value=attn.group(1).strip()[:120], confidence=75, source="billing_attention"
        )

    line = _LINE_RE.search(text)
    table_qty: Decimal | None = None
    if line:
        result.line_description = FieldCandidate(
            value=line.group(1).strip()[:200], confidence=80, source="line"
        )
        table_qty = _parse_money(line.group(2))
        rate = _parse_money(line.group(3))
        if table_qty is not None:
            result.quantity = FieldCandidate(
                value=str(table_qty), confidence=90, source="line_qty"
            )
            result.raw_table_quantity = FieldCandidate(
                value=str(table_qty), confidence=90, source="line_qty"
            )
        if rate is not None:
            result.rate = FieldCandidate(value=str(rate), confidence=88, source="line_rate")

    from app.services.finance.prosohm_document_intelligence import (
        classify_finance_document,
        detect_hours_discrepancy,
        extract_stage_hours,
        stages_as_dicts,
    )

    stages = extract_stage_hours(text)
    result.stage_hours = stages_as_dicts(stages)
    if stages.stages:
        result.stage_hours_sum = FieldCandidate(
            value=str(stages.stage_hours_sum), confidence=85, source="stage_sum"
        )
    if stages.description_total_hours is not None:
        result.raw_description_total_hours = FieldCandidate(
            value=str(stages.description_total_hours),
            confidence=85,
            source="description_total",
        )
    hours_warnings = detect_hours_discrepancy(table_quantity=table_qty, stages=stages)
    result.warnings.extend(hours_warnings)
    if hours_warnings:
        result.quantity.needs_review = True
        result.raw_description_total_hours.needs_review = True

    classification = classify_finance_document(text=text, filename=filename)
    result.document_type = classification.document_type
    result.document_type_confidence = classification.confidence

    note_bits = []
    if result.invoice_number.value:
        note_bits.append(f"Invoice#: {result.invoice_number.value}")
    if result.po_number.value:
        note_bits.append(f"PO: {result.po_number.value}")
    if result.project_ref.value:
        note_bits.append(f"Customer Project #: {result.project_ref.value}")
    if stages.stages:
        note_bits.append(
            "Stages: " + "; ".join(f"{s['label']}: {s['hours']}" for s in result.stage_hours[:8])
        )
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
