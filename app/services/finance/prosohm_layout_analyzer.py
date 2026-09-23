"""Layout-aware Prosohm finance document analyzer (visual word coordinates).

Uses pdfplumber word/line geometry — not flat-string regex alone — so labels
map to values via position (same line to the right, or block below a header).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.finance.prosohm_document_intelligence import parse_prosohm_date


@dataclass
class FieldHit:
    value: str | None
    confidence: float = 0.0
    source: str = "document_visual"
    evidence: str | None = None


@dataclass
class LayoutAnalysis:
    document_type: str = "UNKNOWN"
    document_type_confidence: float = 0.0
    fields: dict[str, FieldHit] = field(default_factory=dict)
    line_items: list[dict[str, Any]] = field(default_factory=list)
    work_breakdown: list[dict[str, Any]] = field(default_factory=list)
    raw_description: str | None = None
    warnings: list[str] = field(default_factory=list)
    page_count: int = 0
    word_count: int = 0
    method: str = "layout_visual"


def _dec(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def _words_from_pdf(content: bytes) -> tuple[list[dict], int, str]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required for layout-aware Finance PDF import. "
            "On the API host run: python -m pip install -r requirements.txt "
            "(or .\\scripts\\install_pdf_deps.ps1), then restart the API."
        ) from exc

    all_words: list[dict] = []
    texts: list[str] = []
    pages = 0
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages[:6]):
            text = page.extract_text() or ""
            if text.strip():
                texts.append(text)
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=True,
                extra_attrs=["size"],
            ) or []
            for w in words:
                all_words.append(
                    {
                        "text": w.get("text") or "",
                        "x0": float(w.get("x0") or 0),
                        "x1": float(w.get("x1") or 0),
                        "top": float(w.get("top") or 0),
                        "bottom": float(w.get("bottom") or 0),
                        "page": page_index,
                    }
                )
    return all_words, pages, "\n".join(texts)


def _cluster_lines(words: list[dict], *, y_tol: float = 3.5) -> list[list[dict]]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w["page"], w["top"], w["x0"]))
    lines: list[list[dict]] = []
    current: list[dict] = []
    current_top: float | None = None
    current_page: int | None = None
    for w in ordered:
        if not current:
            current = [w]
            current_top = w["top"]
            current_page = w["page"]
            continue
        if w["page"] != current_page or abs(w["top"] - (current_top or 0)) > y_tol:
            lines.append(sorted(current, key=lambda item: item["x0"]))
            current = [w]
            current_top = w["top"]
            current_page = w["page"]
        else:
            current.append(w)
    if current:
        lines.append(sorted(current, key=lambda item: item["x0"]))
    return lines


def _line_text(line: list[dict]) -> str:
    return " ".join(w["text"] for w in line).strip()


def _find_label_value(
    lines: list[list[dict]],
    label_patterns: list[re.Pattern[str]],
    *,
    value_re: re.Pattern[str] | None = None,
) -> FieldHit | None:
    """Find a label on a line; take value to the right of the label on same line."""
    for line in lines:
        text = _line_text(line)
        for pattern in label_patterns:
            match = pattern.search(text)
            if not match:
                continue
            # Value after label match on same line
            after = text[match.end() :].strip(" :\t")
            # Drop trailing sibling labels that share the line (common Prosohm layout)
            after = re.split(
                r"\s{2,}|(?=\b(?:Sales\s+person|Customer\s+Project|Quote\s*Date|Invoice\s+Date|"
                r"Terms|Due\s+Date|P\.?O\.?|Bill\s+To|Prepared\s+For)\b)",
                after,
                maxsplit=1,
            )[0].strip(" :\t")
            if value_re:
                vm = value_re.search(after) or value_re.search(text)
                if vm:
                    return FieldHit(
                        value=vm.group(1) if vm.lastindex else vm.group(0),
                        confidence=0.96,
                        evidence=text,
                    )
            if after:
                return FieldHit(value=after, confidence=0.92, evidence=text)
    return None


def _block_after_header(
    lines: list[list[dict]],
    header_re: re.Pattern[str],
    *,
    stop_re: re.Pattern[str],
    max_lines: int = 8,
) -> list[str]:
    out: list[str] = []
    capturing = False
    for line in lines:
        text = _line_text(line)
        if not capturing:
            if header_re.search(text):
                capturing = True
                # Same-line value after header?
                after = header_re.split(text, maxsplit=1)
                if len(after) > 1 and after[1].strip(" :"):
                    candidate = after[1].strip(" :")
                    if candidate and not stop_re.search(candidate):
                        out.append(candidate)
                continue
            continue
        if stop_re.search(text):
            break
        if text:
            out.append(text)
        if len(out) >= max_lines:
            break
    return out


def _extract_table_row(lines: list[list[dict]]) -> dict[str, Any] | None:
    """Find data row under Qty/Rate/Amount header using numeric columns."""
    header_idx = None
    for i, line in enumerate(lines):
        text = _line_text(line).lower()
        prev = _line_text(lines[i - 1]).lower() if i > 0 else ""
        combined = f"{prev} {text}"
        has_qty = "qty" in text or "hrs" in text or "qty/hrs" in text
        has_amount = "amount" in text
        has_rate = "rate" in text or "rate" in prev or "usd)" in text
        if has_qty and has_amount and (has_rate or "qty/hrs" in text):
            header_idx = i
            break
        if has_qty and has_amount and "item" in combined:
            header_idx = i
            break
    if header_idx is None:
        # Fallback: scan for a numbered line-item with 3 money/qty decimals
        for line in lines:
            text = _line_text(line)
            if not re.match(r"^\s*\d+\s+\S+", text):
                continue
            nums = re.findall(r"[\d,]+\.\d{2}", text)
            if len(nums) >= 3 and "full tool" in text.lower():
                header_idx = max(0, lines.index(line) - 1)
                break
    if header_idx is None:
        return None

    for line in lines[header_idx + 1 : header_idx + 8]:
        text = _line_text(line)
        # Typical: 1 Full Tool Design (...) 240.00 25.00 6,000.00
        nums = re.findall(r"[\d,]+\.\d{2}", text)
        if len(nums) < 3:
            continue
        qty, rate, amount = nums[0], nums[1], nums[2]
        desc = re.sub(r"^\s*\d+\s+", "", text)
        for n in nums:
            desc = desc.replace(n, "")
        desc = re.sub(r"\s+", " ", desc).strip(" -")
        return {
            "item_number": "1",
            "description": desc or None,
            "quantity": float(_dec(qty) or 0) or None,
            "unit": "Hrs",
            "rate": float(_dec(rate) or 0) or None,
            "currency": "USD" if "$" in text or "USD" in text.upper() else None,
            "amount": float(_dec(amount) or 0) or None,
            "raw_description": text,
            "evidence": text,
        }
    return None


def _extract_stages(lines: list[list[dict]]) -> tuple[list[dict[str, Any]], Decimal | None, str | None]:
    stages: list[dict[str, Any]] = []
    stated_total: Decimal | None = None
    raw_bits: list[str] = []
    stage_re = re.compile(
        r"^([A-Za-z][A-Za-z0-9+/\s&\-]{2,80}?)\s*[:\-–—=]\s*([\d,]+\.?\d*)\s*(?:hrs?\.?)?\s*$",
        re.IGNORECASE,
    )
    total_re = re.compile(r"^TOTAL\s*[:\-–—=]?\s*([\d,]+\.?\d*)\s*(?:hrs?\.?)?\s*$", re.IGNORECASE)
    skip = {"sub total", "subtotal", "balance due", "amount", "rate"}

    for line in lines:
        text = _line_text(line)
        if not text:
            continue
        tm = total_re.match(text)
        if tm:
            stated_total = _dec(tm.group(1))
            raw_bits.append(text)
            continue
        sm = stage_re.match(text)
        if not sm:
            continue
        label = re.sub(r"\s+", " ", sm.group(1)).strip(" :")
        if label.lower() in skip or label.lower().startswith("total"):
            continue
        hours = _dec(sm.group(2))
        if hours is None or hours <= 0 or hours > 5000:
            continue
        stages.append({"stage": label, "hours": float(hours), "evidence": text})
        raw_bits.append(text)
    return stages, stated_total, "\n".join(raw_bits) if raw_bits else None


def analyze_prosohm_layout(content: bytes, *, filename: str | None = None) -> LayoutAnalysis:
    """Visual layout analysis for Prosohm quote/invoice PDFs."""
    try:
        words, page_count, flat_text = _words_from_pdf(content)
    except ImportError as exc:
        result = LayoutAnalysis(method="layout_unavailable")
        result.warnings.append(str(exc))
        return result
    except Exception as exc:  # noqa: BLE001
        result = LayoutAnalysis(method="layout_error")
        result.warnings.append(f"Layout analysis failed: {type(exc).__name__}: {exc}")
        return result

    result = LayoutAnalysis(page_count=page_count, word_count=len(words))
    if not words:
        result.warnings.append("No positioned words found in PDF text layer.")
        return result

    lines = _cluster_lines(words)
    upper = flat_text.upper()

    # Classification from visual title words + text
    has_invoice = bool(re.search(r"\bINVOICE\b", flat_text, re.IGNORECASE))
    has_quote = bool(re.search(r"\bQUOTE\b", flat_text, re.IGNORECASE)) and not has_invoice
    if has_invoice and ("INVOICE #" in upper or "INVOICE#" in upper or "INVOICE DATE" in upper):
        result.document_type = "INVOICE"
        result.document_type_confidence = 0.99
    elif has_quote or re.search(r"Quote\s*#", flat_text, re.IGNORECASE):
        result.document_type = "QUOTE"
        result.document_type_confidence = 0.99
    elif has_invoice:
        result.document_type = "INVOICE"
        result.document_type_confidence = 0.9
    else:
        result.document_type = "UNKNOWN"
        result.document_type_confidence = 0.3

    # Document numbers
    inv_no = _find_label_value(
        lines,
        [re.compile(r"Invoice\s*#\s*", re.IGNORECASE)],
        value_re=re.compile(r"(INV-[A-Z0-9\-]+)", re.IGNORECASE),
    )
    qt_no = _find_label_value(
        lines,
        [re.compile(r"Quote\s*#\s*", re.IGNORECASE)],
        value_re=re.compile(r"(QT-[A-Z0-9\-]+)", re.IGNORECASE),
    )
    if inv_no:
        result.fields["invoice_number"] = inv_no
    if qt_no:
        result.fields["quote_number"] = qt_no

    # Dates / terms / sales / PO / project
    inv_date = _find_label_value(
        lines,
        [re.compile(r"Invoice\s+Date\s*", re.IGNORECASE)],
    )
    quote_date = _find_label_value(
        lines,
        [re.compile(r"Quote\s+Date\s*", re.IGNORECASE)],
    )
    due_date = _find_label_value(
        lines,
        [re.compile(r"Due\s+Date\s*", re.IGNORECASE)],
    )
    terms = _find_label_value(
        lines,
        [re.compile(r"Terms\s*", re.IGNORECASE)],
    )
    sales = _find_label_value(
        lines,
        [re.compile(r"Sales\s+person\s*", re.IGNORECASE)],
    )
    po = _find_label_value(
        lines,
        [re.compile(r"P\.?\s*O\.?\s*#\s*", re.IGNORECASE)],
        value_re=re.compile(r"([A-Z0-9][A-Z0-9\-_/]+)", re.IGNORECASE),
    )
    project = _find_label_value(
        lines,
        [re.compile(r"Customer\s+Project\s*#\s*", re.IGNORECASE)],
        value_re=re.compile(r"([A-Za-z0-9\-_/]+)"),
    )

    def _normalize_date(hit: FieldHit | None, key: str) -> None:
        if not hit or not hit.value:
            return
        iso = parse_prosohm_date(hit.value)
        result.fields[key] = FieldHit(
            value=iso or hit.value,
            confidence=0.95 if iso else 0.6,
            evidence=hit.evidence,
            source="document_visual",
        )

    _normalize_date(inv_date, "invoice_date")
    _normalize_date(quote_date, "quote_date")
    _normalize_date(due_date, "due_date")
    if terms and terms.value:
        # Trim sibling fields that leaked
        val = re.split(r"\s+Customer\s+Project", terms.value, maxsplit=1)[0].strip()
        result.fields["payment_terms"] = FieldHit(value=val, confidence=0.9, evidence=terms.evidence)
    if sales and sales.value:
        val = re.split(r"\s+Customer\s+Project|\s+Quote\s+Date", sales.value, maxsplit=1)[0].strip()
        result.fields["sales_person"] = FieldHit(value=val, confidence=0.92, evidence=sales.evidence)
    if po and po.value:
        result.fields["po_number"] = FieldHit(
            value=po.value.strip(), confidence=0.93, evidence=po.evidence
        )
    if project and project.value:
        result.fields["customer_project_number"] = FieldHit(
            value=project.value.strip(), confidence=0.98, evidence=project.evidence
        )

    # Customer blocks
    if result.document_type == "INVOICE":
        bill_lines = _block_after_header(
            lines,
            re.compile(r"^Bill\s+To\b", re.IGNORECASE),
            stop_re=re.compile(
                r"Billing\s+Attention|^#\s*Item|Qty|Sub\s*Total|Balance\s+Due",
                re.IGNORECASE,
            ),
        )
        if bill_lines:
            result.fields["customer_name"] = FieldHit(
                value=bill_lines[0].strip(),
                confidence=0.95,
                evidence="Bill To → " + bill_lines[0],
            )
            if len(bill_lines) > 1:
                result.fields["customer_address"] = FieldHit(
                    value="\n".join(bill_lines[1:]),
                    confidence=0.85,
                    evidence="Bill To block",
                )
        attn = _find_label_value(
            lines,
            [re.compile(r"Billing\s+Attention\s*", re.IGNORECASE)],
        )
        if attn and attn.value:
            result.fields["billing_attention"] = FieldHit(
                value=attn.value.strip(), confidence=0.9, evidence=attn.evidence
            )
    else:
        prep_lines = _block_after_header(
            lines,
            re.compile(r"^Prepared\s+For\b", re.IGNORECASE),
            stop_re=re.compile(r"Kind\s+Attention|^#\s*Item|Qty/Hrs|Rate|Sub\s*Total", re.IGNORECASE),
        )
        if prep_lines:
            result.fields["customer_name"] = FieldHit(
                value=prep_lines[0],
                confidence=0.95,
                evidence="Prepared For → " + prep_lines[0],
            )
            if len(prep_lines) > 1:
                result.fields["customer_address"] = FieldHit(
                    value="\n".join(prep_lines[1:]),
                    confidence=0.85,
                    evidence="Prepared For block",
                )
        attn = _find_label_value(
            lines,
            [re.compile(r"Kind\s+Attention\s*", re.IGNORECASE)],
        )
        if attn and attn.value:
            result.fields["customer_contact"] = FieldHit(
                value=attn.value.strip(), confidence=0.9, evidence=attn.evidence
            )

    # Commercial table + totals
    row = _extract_table_row(lines)
    if row:
        result.line_items = [row]
        if row.get("quantity") is not None:
            result.fields["quantity"] = FieldHit(
                value=str(row["quantity"]),
                confidence=0.95,
                evidence=row.get("evidence"),
            )
        if row.get("rate") is not None:
            result.fields["rate"] = FieldHit(
                value=str(row["rate"]), confidence=0.95, evidence=row.get("evidence")
            )
        if row.get("amount") is not None:
            result.fields["line_amount"] = FieldHit(
                value=str(row["amount"]), confidence=0.95, evidence=row.get("evidence")
            )
        if row.get("description"):
            result.fields["line_description"] = FieldHit(
                value=row["description"], confidence=0.9, evidence=row.get("evidence")
            )
        if row.get("currency"):
            result.fields["currency"] = FieldHit(
                value=row["currency"], confidence=0.85, evidence=row.get("evidence")
            )

    # Money totals — prefer last high-signal labels
    for key, patterns in (
        ("subtotal", [re.compile(r"Sub\s*Total\s*", re.IGNORECASE)]),
        ("tax", [re.compile(r"(?:IGST|GST|Tax)\s*", re.IGNORECASE)]),
        ("total", [re.compile(r"(?<!\w)Total\s*", re.IGNORECASE)]),
        ("balance_due", [re.compile(r"Balance\s+Due\s*", re.IGNORECASE)]),
    ):
        for line in reversed(lines):
            text = _line_text(line)
            for pat in patterns:
                if not pat.search(text):
                    continue
                # Avoid "Total In Words"
                if key == "total" and re.search(r"Total\s+In\s+Words", text, re.IGNORECASE):
                    continue
                money = re.findall(r"\$?\s*([\d,]+\.\d{2})", text)
                if not money and key == "subtotal":
                    # Sub Total often on next line
                    idx = lines.index(line)
                    if idx + 1 < len(lines):
                        money = re.findall(r"\$?\s*([\d,]+\.\d{2})", _line_text(lines[idx + 1]))
                        if money:
                            text = text + " / " + _line_text(lines[idx + 1])
                if money:
                    result.fields[key] = FieldHit(
                        value=str(_dec(money[-1])),
                        confidence=0.94,
                        evidence=text,
                    )
                    break
            if key in result.fields:
                break

    if "currency" not in result.fields:
        if "$" in flat_text or "United States Dollar" in flat_text:
            result.fields["currency"] = FieldHit(
                value="USD", confidence=0.9, evidence="currency hint in document"
            )

    stages, stated_total, raw_desc = _extract_stages(lines)
    result.work_breakdown = stages
    result.raw_description = raw_desc
    if stages:
        stage_sum = sum((Decimal(str(s["hours"])) for s in stages), Decimal("0"))
        result.fields["stage_hours_sum"] = FieldHit(
            value=str(stage_sum), confidence=0.9, evidence="sum of stage lines"
        )
    if stated_total is not None:
        result.fields["stated_total_hours"] = FieldHit(
            value=str(stated_total), confidence=0.9, evidence="TOTAL: line in description"
        )

    # Advance terms (quote)
    for line in lines:
        text = _line_text(line)
        if re.search(r"ADVANCE\s+OF\s+50%", text, re.IGNORECASE):
            result.fields["payment_terms"] = FieldHit(
                value=text.strip(), confidence=0.9, evidence=text
            )
        if re.search(r"SUBJECT\s+TO\s+STANDARD\s+DELIVER", text, re.IGNORECASE):
            result.fields["delivery_terms"] = FieldHit(
                value=text.strip(), confidence=0.85, evidence=text
            )

    # Filename validation signal (never primary)
    if filename:
        fn = filename.upper()
        m = re.search(r"(INV-[A-Z0-9\-]+)", fn)
        if m:
            result.fields["invoice_number_filename"] = FieldHit(
                value=m.group(1), confidence=0.4, source="filename", evidence=filename
            )
            doc_inv = result.fields.get("invoice_number")
            if doc_inv and doc_inv.value and doc_inv.value.upper() != m.group(1).upper():
                result.warnings.append(
                    f"Invoice number conflict: document={doc_inv.value} filename={m.group(1)}"
                )
        m = re.search(r"(QT-[A-Z0-9\-]+)", fn)
        if m:
            result.fields["quote_number_filename"] = FieldHit(
                value=m.group(1), confidence=0.4, source="filename", evidence=filename
            )

    # Hours mismatch warning
    qty = _dec(result.fields["quantity"].value) if "quantity" in result.fields else None
    stage_sum = (
        _dec(result.fields["stage_hours_sum"].value)
        if "stage_hours_sum" in result.fields
        else None
    )
    stated = (
        _dec(result.fields["stated_total_hours"].value)
        if "stated_total_hours" in result.fields
        else None
    )
    present = [v for v in (qty, stage_sum, stated) if v is not None]
    if len({round(float(v), 2) for v in present}) > 1:
        result.warnings.append(
            "DATA REVIEW REQUIRED: Document contains different hour totals "
            f"(table={qty}, stages={stage_sum}, stated={stated})."
        )

    return result


__all__ = ["FieldHit", "LayoutAnalysis", "analyze_prosohm_layout"]
