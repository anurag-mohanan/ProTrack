"""Deterministic Prosohm quote/invoice field extractors (normalized text).

Small label+nearby-value extractors — not one giant regex, not LLM-dependent.
Operates on normalized PDF text; preserves original separately.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.finance.prosohm_document_intelligence import parse_prosohm_date


@dataclass
class ExtractedField:
    value: Any = None
    confidence: float = 0.0
    source: str = "document_text"
    evidence: str | None = None


@dataclass
class DeterministicDocumentResult:
    document_type: str = "UNKNOWN"
    document_type_confidence: float = 0.0
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    work_breakdown: list[dict[str, Any]] = field(default_factory=list)
    line_items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_text: str = ""
    raw_text: str = ""


def normalize_pdf_text(text: str) -> str:
    """Normalize PDF extraction noise while keeping readable structure."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    t = t.replace("\t", " ")
    # Collapse spaces but keep newlines
    t = re.sub(r"[^\S\n]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _money(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _nearby_after_label(text: str, label_re: str, *, value_re: str | None = None, flags=re.IGNORECASE) -> ExtractedField | None:
    pattern = re.compile(
        rf"(?P<label>{label_re})\s*[:：]?\s*(?P<after>[^\n]+)",
        flags,
    )
    m = pattern.search(text)
    if not m:
        # Label on one line, value on next
        pattern2 = re.compile(
            rf"(?P<label>{label_re})\s*[:：]?\s*\n\s*(?P<after>[^\n]+)",
            flags,
        )
        m = pattern2.search(text)
    if not m:
        return None
    after = m.group("after").strip()
    # Cut sibling labels sharing the line
    after = re.split(
        r"\s{2,}|(?=\b(?:Sales\s+person|Customer\s+Project|Quote\s*Date|Invoice\s+Date|"
        r"Terms|Due\s+Date|P\.?\s*O\.?|Bill\s+To|Prepared\s+For|Kind\s+Attention|"
        r"Billing\s+Attention)\b)",
        after,
        maxsplit=1,
    )[0].strip(" :\t")
    evidence = m.group(0).strip()
    if value_re:
        vm = re.search(value_re, after, flags) or re.search(value_re, evidence, flags)
        if not vm:
            return None
        return ExtractedField(
            value=vm.group(1) if vm.lastindex else vm.group(0),
            confidence=0.97,
            evidence=evidence,
        )
    if not after:
        return None
    return ExtractedField(value=after, confidence=0.93, evidence=evidence)


def classify_document_type(text: str, *, filename: str | None = None) -> tuple[str, float]:
    body = text or ""
    upper = body.upper()
    name = (filename or "").upper()
    inv_score = 0.0
    qt_score = 0.0
    if re.search(r"\bINVOICE\b", body, re.IGNORECASE):
        inv_score += 40
    if re.search(r"Invoice\s*#", body, re.IGNORECASE):
        inv_score += 40
    if "BALANCE DUE" in upper:
        inv_score += 15
    if re.search(r"\bQUOTE\b", body, re.IGNORECASE):
        qt_score += 40
    if re.search(r"Quote\s*#", body, re.IGNORECASE):
        qt_score += 40
    if "PREPARED FOR" in upper:
        qt_score += 10
    if "INV-" in name:
        inv_score += 5
    if "QT-" in name:
        qt_score += 5
    if inv_score >= 50 and inv_score >= qt_score:
        return "INVOICE", min(0.99, inv_score / 100)
    if qt_score >= 50 and qt_score > inv_score:
        return "QUOTE", min(0.99, qt_score / 100)
    return "UNKNOWN", max(inv_score, qt_score) / 100


def extract_invoice_number(text: str) -> ExtractedField | None:
    return _nearby_after_label(
        text,
        r"Invoice\s*(?:#|No\.?|Number)",
        value_re=r"(INV-[A-Z0-9\-]+)",
    )


def extract_quote_number(text: str) -> ExtractedField | None:
    return _nearby_after_label(
        text,
        r"Quote\s*(?:#|No\.?|Number)",
        value_re=r"(QT-[A-Z0-9\-]+)",
    )


def extract_invoice_date(text: str) -> ExtractedField | None:
    hit = _nearby_after_label(text, r"Invoice\s+Date")
    if not hit or not hit.value:
        return hit
    iso = parse_prosohm_date(hit.value)
    if iso:
        return ExtractedField(value=iso, confidence=0.96, evidence=hit.evidence)
    return ExtractedField(value=hit.value, confidence=0.5, evidence=hit.evidence)


def extract_quote_date(text: str) -> ExtractedField | None:
    hit = _nearby_after_label(text, r"Quote\s+Date")
    if not hit or not hit.value:
        return hit
    iso = parse_prosohm_date(hit.value)
    if iso:
        return ExtractedField(value=iso, confidence=0.96, evidence=hit.evidence)
    return ExtractedField(value=hit.value, confidence=0.5, evidence=hit.evidence)


def extract_due_date(text: str) -> ExtractedField | None:
    hit = _nearby_after_label(text, r"Due\s+Date")
    if not hit or not hit.value:
        return hit
    iso = parse_prosohm_date(hit.value)
    if iso:
        return ExtractedField(value=iso, confidence=0.95, evidence=hit.evidence)
    return hit


def extract_payment_terms(text: str) -> ExtractedField | None:
    hit = _nearby_after_label(text, r"Terms(?!\s*&?\s*Conditions)")
    if hit and hit.value:
        val = re.split(r"\s+Customer\s+Project", hit.value, maxsplit=1)[0].strip()
        if val.lower() not in {"& conditions", "and conditions", "conditions"} and "authorized" not in val.lower():
            return ExtractedField(value=val, confidence=0.9, evidence=hit.evidence)
    # Quote advance terms
    m = re.search(
        r"(ADVANCE\s+OF\s+50%\s+ALONG\s+WITH\s+PO[^\n]*)",
        text,
        re.IGNORECASE,
    )
    if m:
        return ExtractedField(value=m.group(1).strip(), confidence=0.92, evidence=m.group(1))
    return None


def extract_sales_person(text: str) -> ExtractedField | None:
    hit = _nearby_after_label(text, r"Sales\s+person")
    if not hit or not hit.value:
        return hit
    val = re.split(r"\s+Customer\s+Project|\s+Quote\s+Date", hit.value, maxsplit=1)[0].strip()
    return ExtractedField(value=val, confidence=0.94, evidence=hit.evidence)


def extract_po_number(text: str) -> ExtractedField | None:
    # Require explicit P.O. # / PO Number — avoid matching random "Po..." words
    hit = _nearby_after_label(
        text,
        r"P\.?\s*O\.?\s*(?:#|No\.?|Number)",
        value_re=r"([0-9][A-Z0-9\-_/]*)",
    )
    if hit:
        return hit
    m = re.search(
        r"P\.?\s*O\.?\s*#\s*[:：]?\s*([0-9][A-Z0-9\-_/]*)",
        text,
        re.IGNORECASE,
    )
    if m:
        return ExtractedField(value=m.group(1), confidence=0.95, evidence=m.group(0).strip())
    return None


def extract_customer_project_number(text: str) -> ExtractedField | None:
    return _nearby_after_label(
        text,
        r"Customer\s+Project\s*#",
        value_re=r"([A-Za-z0-9\-_/]+)",
    )


def _section_block(text: str, header: str, stop_labels: tuple[str, ...]) -> list[str]:
    pattern = re.compile(
        rf"(?:^|\n)\s*{header}\s*[:：]?\s*\n(?P<body>.*?)(?=\n\s*(?:{'|'.join(stop_labels)})\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        # Same-line header
        pattern2 = re.compile(
            rf"(?:^|\n)\s*{header}\s*[:：]\s*(?P<body>[^\n]+)",
            re.IGNORECASE,
        )
        m = pattern2.search(text)
        if not m:
            return []
        return [m.group("body").strip()]
    lines = [ln.strip() for ln in m.group("body").splitlines() if ln.strip()]
    return lines


def extract_invoice_customer(text: str) -> tuple[ExtractedField | None, ExtractedField | None]:
    lines = _section_block(
        text,
        r"Bill\s+To",
        ("Billing\\s+Attention", "#\\s*Item", "Qty", "Sub\\s*Total", "Balance\\s+Due", "Invoice"),
    )
    customer = None
    if lines:
        name = lines[0].strip()
        # Never treat seller as customer
        if "prosohm" not in name.lower():
            customer = ExtractedField(value=name, confidence=0.95, evidence="Bill To → " + name)
    attn = _nearby_after_label(text, r"Billing\s+Attention")
    return customer, attn


def extract_quote_customer(text: str) -> tuple[ExtractedField | None, ExtractedField | None]:
    lines = _section_block(
        text,
        r"Prepared\s+For",
        ("Kind\\s+Attention", "#\\s*Item", "Qty/Hrs", "Rate", "Sub\\s*Total", "Quote"),
    )
    customer = None
    if lines:
        name = lines[0].strip()
        if "prosohm" not in name.lower():
            customer = ExtractedField(value=name, confidence=0.95, evidence="Prepared For → " + name)
    attn = _nearby_after_label(text, r"Kind\s+Attention")
    return customer, attn


def extract_currency(text: str) -> ExtractedField | None:
    if re.search(r"\bUSD\b|United States Dollar|\$", text, re.IGNORECASE):
        return ExtractedField(value="USD", confidence=0.9, evidence="currency markers")
    if re.search(r"\bINR\b|₹", text, re.IGNORECASE):
        return ExtractedField(value="INR", confidence=0.9, evidence="currency markers")
    return None


def extract_commercial_line(text: str) -> dict[str, Any] | None:
    """Main Qty/Rate/Amount row — ignore stage hour lines."""
    # Prefer numbered Full Tool Design line
    m = re.search(
        r"(?m)^\s*\d+\s+(Full\s+Tool\s+Design[^\n]*?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"(?m)^\s*\d+\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
            text,
        )
    if not m:
        return None
    desc = re.sub(r"\s+", " ", m.group(1)).strip()
    qty, rate, amount = _money(m.group(2)), _money(m.group(3)), _money(m.group(4))
    return {
        "item_number": "1",
        "description": desc,
        "quantity": float(qty) if qty is not None else None,
        "unit": "Hrs",
        "rate": float(rate) if rate is not None else None,
        "amount": float(amount) if amount is not None else None,
        "raw_description": m.group(0).strip(),
        "evidence": m.group(0).strip(),
    }


def extract_money_labeled(text: str, label: str, *, avoid: str | None = None) -> ExtractedField | None:
    candidates: list[ExtractedField] = []
    for m in re.finditer(
        rf"(?im){label}\s*[:：]?\s*(?:\$|USD|INR|₹)?\s*([\d,]+\.?\d*)",
        text,
    ):
        snippet = m.group(0)
        if avoid and re.search(avoid, snippet, re.IGNORECASE):
            continue
        if re.search(r"total\s+in\s+words", snippet, re.IGNORECASE):
            continue
        # Skip stage hour totals like "TOTAL: 320 Hrs"
        if re.search(r"hrs?\.?\s*$", snippet, re.IGNORECASE):
            continue
        money = _money(m.group(1))
        if money is None:
            continue
        # Prefer currency-marked money lines
        conf = 0.96 if "$" in snippet or "USD" in snippet.upper() else 0.9
        candidates.append(ExtractedField(value=str(money), confidence=conf, evidence=snippet.strip()))
    # Sub Total often followed by amount on next line
    if "sub" in label.lower():
        m = re.search(
            rf"(?im){label}\s*\n\s*(?:\$|USD)?\s*([\d,]+\.\d{{2}})",
            text,
        )
        if m:
            money = _money(m.group(1))
            if money is not None:
                candidates.append(
                    ExtractedField(value=str(money), confidence=0.93, evidence=m.group(0).strip())
                )
    if not candidates:
        return None
    # Prefer larger commercial totals over small hour totals misread as money
    candidates.sort(key=lambda c: (float(c.confidence), float(Decimal(str(c.value)))), reverse=True)
    return candidates[0]


def extract_work_breakdown(text: str) -> tuple[list[dict[str, Any]], ExtractedField | None, ExtractedField | None]:
    stages: list[dict[str, Any]] = []
    stated: ExtractedField | None = None
    stage_re = re.compile(
        r"(?m)^\s*([A-Za-z][A-Za-z0-9+/\s&\-]{2,80}?)\s*[:\-–—=]\s*([\d,]+\.?\d*)\s*(?:hrs?\.?)?\s*$",
        re.IGNORECASE,
    )
    skip = {"sub total", "subtotal", "balance due", "amount", "rate", "qty", "qty/hrs"}
    for m in stage_re.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" :")
        if label.lower() in skip or label.lower().startswith("total"):
            continue
        if "united states dollar" in label.lower():
            continue
        hours = _money(m.group(2))
        if hours is None or hours <= 0 or hours > 5000:
            continue
        stages.append({"stage": label, "hours": float(hours), "evidence": m.group(0).strip()})
    tm = re.search(r"(?im)^\s*TOTAL\s*[:\-–—=]?\s*([\d,]+\.?\d*)\s*(?:hrs?\.?)?\s*$", text)
    if tm:
        hours = _money(tm.group(1))
        if hours is not None:
            stated = ExtractedField(value=str(hours), confidence=0.9, evidence=tm.group(0).strip())
    stage_sum = None
    if stages:
        total = sum((Decimal(str(s["hours"])) for s in stages), Decimal("0"))
        stage_sum = ExtractedField(value=str(total), confidence=0.9, evidence="sum of stages")
    return stages, stage_sum, stated


def extract_deterministic_document(
    raw_text: str,
    *,
    filename: str | None = None,
    expected_kind: str | None = None,
) -> DeterministicDocumentResult:
    normalized = normalize_pdf_text(raw_text)
    result = DeterministicDocumentResult(raw_text=raw_text or "", normalized_text=normalized)
    doc_type, conf = classify_document_type(normalized, filename=filename)
    if expected_kind and doc_type == "UNKNOWN":
        doc_type = expected_kind.upper()
        conf = max(conf, 0.8)
    if expected_kind and expected_kind.upper() in {"INVOICE", "QUOTE"}:
        # Strong override when caller knows document kind from upload action
        if doc_type == "UNKNOWN" or (
            expected_kind.upper() == "INVOICE" and doc_type != "INVOICE" and conf < 0.7
        ):
            pass
        if expected_kind.upper() == "INVOICE" and (
            "INVOICE" in normalized.upper() or "INV-" in (filename or "").upper()
        ):
            doc_type, conf = "INVOICE", max(conf, 0.95)
        if expected_kind.upper() == "QUOTE" and (
            "QUOTE" in normalized.upper() or "QT-" in (filename or "").upper()
        ):
            doc_type, conf = "QUOTE", max(conf, 0.95)
    result.document_type = doc_type
    result.document_type_confidence = conf

    def put(key: str, hit: ExtractedField | None) -> None:
        if hit and hit.value not in (None, ""):
            result.fields[key] = hit

    if doc_type == "INVOICE":
        put("invoice_number", extract_invoice_number(normalized))
        put("invoice_date", extract_invoice_date(normalized))
        put("due_date", extract_due_date(normalized))
        put("payment_terms", extract_payment_terms(normalized))
        put("sales_person", extract_sales_person(normalized))
        put("po_number", extract_po_number(normalized))
        put("customer_project_number", extract_customer_project_number(normalized))
        cust, attn = extract_invoice_customer(normalized)
        put("customer_name", cust)
        put("billing_attention", attn)
        put("balance_due", extract_money_labeled(normalized, r"Balance\s+Due"))
        put("tax", extract_money_labeled(normalized, r"(?:IGST|GST|Tax)"))
    else:
        put("quote_number", extract_quote_number(normalized))
        put("quote_date", extract_quote_date(normalized))
        put("payment_terms", extract_payment_terms(normalized))
        put("sales_person", extract_sales_person(normalized))
        put("customer_project_number", extract_customer_project_number(normalized))
        cust, attn = extract_quote_customer(normalized)
        put("customer_name", cust)
        put("customer_contact", attn)

    put("currency", extract_currency(normalized))
    put("subtotal", extract_money_labeled(normalized, r"Sub\s*Total"))
    # Prefer explicit money Total / Grand Total — never stage "TOTAL: N Hrs"
    put(
        "total",
        extract_money_labeled(normalized, r"(?:Grand\s+Total|(?<![A-Za-z])Total(?!\s*[:\-–—]?\s*[\d,]+\.?\d*\s*hrs?))"),
    )
    # Fallback: Total $X.XX
    if "total" not in result.fields:
        m = re.search(r"Total\s*\$\s*([\d,]+\.\d{2})", normalized, re.IGNORECASE)
        if m:
            money = _money(m.group(1))
            if money is not None:
                put("total", ExtractedField(value=str(money), confidence=0.97, evidence=m.group(0)))

    line = extract_commercial_line(normalized)
    if line:
        result.line_items = [line]
        if line.get("quantity") is not None:
            put("quantity", ExtractedField(value=str(line["quantity"]), confidence=0.95, evidence=line.get("evidence")))
        if line.get("rate") is not None:
            put("rate", ExtractedField(value=str(line["rate"]), confidence=0.95, evidence=line.get("evidence")))
        if line.get("amount") is not None:
            put("line_amount", ExtractedField(value=str(line["amount"]), confidence=0.95, evidence=line.get("evidence")))
            # Commercial line amount is authoritative for total when Total was stage hours
            existing_total = result.fields.get("total")
            if existing_total is None or float(Decimal(str(existing_total.value))) < float(line["amount"]):
                put(
                    "total",
                    ExtractedField(
                        value=str(line["amount"]),
                        confidence=0.96,
                        evidence=line.get("evidence"),
                    ),
                )
        if line.get("description"):
            put("line_description", ExtractedField(value=line["description"], confidence=0.9, evidence=line.get("evidence")))

    stages, stage_sum, stated = extract_work_breakdown(normalized)
    result.work_breakdown = stages
    put("stage_hours_sum", stage_sum)
    put("stated_total_hours", stated)

    # Hours conflict warning
    qty = result.fields.get("quantity")
    if qty and stage_sum and stated:
        try:
            values = {
                float(Decimal(str(qty.value))),
                float(Decimal(str(stage_sum.value))),
                float(Decimal(str(stated.value))),
            }
            if len(values) > 1:
                result.warnings.append(
                    "HOURS_VALUE_CONFLICT: commercial quantity, stage sum, and stated TOTAL differ."
                )
        except Exception:
            pass

    # Filename only as secondary signal
    if filename:
        fm = re.search(r"(INV-[A-Z0-9\-]+)", filename, re.IGNORECASE)
        if fm and "invoice_number" not in result.fields:
            put(
                "invoice_number",
                ExtractedField(value=fm.group(1).upper(), confidence=0.35, source="filename", evidence=filename),
            )
            result.warnings.append("Invoice number taken from filename only — confirm against document.")
        qm = re.search(r"(QT-[A-Z0-9\-]+)", filename, re.IGNORECASE)
        if qm and "quote_number" not in result.fields:
            put(
                "quote_number",
                ExtractedField(value=qm.group(1).upper(), confidence=0.35, source="filename", evidence=filename),
            )

    return result


def deterministic_to_review_fields(result: DeterministicDocumentResult) -> dict[str, dict]:
    """Map to existing review DTO field keys."""
    f = result.fields
    out: dict[str, dict] = {}

    def cand(hit: ExtractedField | None) -> dict:
        if hit is None or hit.value in (None, ""):
            return {"value": None, "confidence": 0, "source": None, "needs_review": True, "evidence": None}
        conf = float(hit.confidence)
        if conf <= 1:
            conf *= 100
        return {
            "value": str(hit.value),
            "confidence": conf,
            "source": hit.source,
            "needs_review": conf < 60,
            "evidence": hit.evidence,
        }

    if result.document_type == "INVOICE":
        mapping = {
            "invoice_number": "invoice_number",
            "invoice_date": "invoice_date",
            "due_date": "due_date",
            "payment_terms": "payment_terms",
            "sales_person": "sales_person",
            "po_number": "po_number",
            "customer_project_number": "customer_project_number",
            "project_ref": "customer_project_number",
            "customer_name": "customer_name",
            "billing_attention": "billing_attention",
            "currency_code": "currency",
            "quantity": "quantity",
            "raw_table_quantity": "quantity",
            "rate": "rate",
            "subtotal": "subtotal",
            "tax_amount": "tax",
            "amount": "total",
            "balance_due": "balance_due",
            "line_description": "line_description",
            "stage_hours_sum": "stage_hours_sum",
            "raw_description_total_hours": "stated_total_hours",
        }
    else:
        mapping = {
            "external_quote_number": "quote_number",
            "quote_number": "quote_number",
            "quoted_date": "quote_date",
            "sales_person": "sales_person",
            "customer_project_number": "customer_project_number",
            "tool_number": "customer_project_number",
            "customer_name": "customer_name",
            "customer_contact": "customer_contact",
            "currency_code": "currency",
            "quoted_hours": "quantity",
            "raw_table_quantity": "quantity",
            "rate": "rate",
            "subtotal": "subtotal",
            "quoted_revenue": "total",
            "line_description": "line_description",
            "payment_terms": "payment_terms",
            "stage_hours_sum": "stage_hours_sum",
            "raw_description_total_hours": "stated_total_hours",
        }
    for out_key, src_key in mapping.items():
        if src_key in f:
            out[out_key] = cand(f[src_key])
    if "amount" not in out and "line_amount" in f:
        out["amount"] = cand(f["line_amount"])
    if "quoted_revenue" not in out and "line_amount" in f:
        out["quoted_revenue"] = cand(f["line_amount"])
    return out


__all__ = [
    "DeterministicDocumentResult",
    "ExtractedField",
    "deterministic_to_review_fields",
    "extract_deterministic_document",
    "normalize_pdf_text",
]
