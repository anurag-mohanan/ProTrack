"""Invoice PDF import — extract → review → confirm (never auto-save)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteInvoiceLine, QuoteRevision
from app.models.models import Customer, Project, User
from app.services.document_asset_service import store_document
from app.services.finance.invoice_pdf_parser import (
    FieldCandidate,
    content_fingerprint,
    parse_invoice_pdf_text,
)
from app.services.finance.quote_cash_ledger_service import add_invoice_line, load_quote_with_ledger
from app.services.finance.quote_import_service import _find_customer


def _candidate_dict(field: FieldCandidate) -> dict:
    return {
        "value": field.value,
        "confidence": field.confidence,
        "source": field.source,
        "needs_review": field.needs_review or field.confidence < 60 or not field.value,
    }


def _parse_amount(raw: str | None) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _score_customer_match(extracted: str, customer: Customer) -> float:
    a = extracted.lower().strip()
    name = (customer.name or "").lower()
    code = (customer.code or "").lower()
    if a == name or a == code:
        return 98.0
    if name.startswith(a) or a.startswith(name):
        return 88.0
    if a in name or name in a:
        return 75.0
    if code and (a in code or code in a):
        return 70.0
    return 0.0


def suggest_customer_matches(db: Session, name: str | None, *, limit: int = 5) -> list[dict]:
    if not name or not name.strip():
        return []
    try:
        exact = _find_customer(db, name, soft_match=True)
        return [
            {
                "customer_id": str(exact.id),
                "name": exact.name,
                "code": exact.code,
                "confidence": _score_customer_match(name, exact),
            }
        ]
    except ProTrackValidationError:
        pass
    customers = list(db.scalars(select(Customer).where(Customer.is_active.is_(True))).all())
    scored: list[tuple[float, Customer]] = []
    for customer in customers:
        score = _score_customer_match(name, customer)
        if score >= 70:
            scored.append((score, customer))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "customer_id": str(c.id),
            "name": c.name,
            "code": c.code,
            "confidence": score,
        }
        for score, c in scored[:limit]
    ]


def suggest_quote_matches(
    db: Session,
    *,
    tool_or_project_ref: str | None,
    quote_ref: str | None,
    customer_id: UUID | None,
    team_id: UUID | None,
    limit: int = 8,
) -> list[dict]:
    stmt = select(Quote).where(Quote.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)
    quotes = list(db.scalars(stmt.limit(200)).all())
    scored: list[tuple[float, Quote, str]] = []
    ref = (tool_or_project_ref or "").strip().lower()
    qref = (quote_ref or "").strip().lower()
    for quote in quotes:
        score = 0.0
        reason = ""
        tool = (quote.tool_number or "").lower()
        ext = (quote.external_quote_number or "").lower()
        if qref and (qref == ext or qref in ext or ext in qref):
            score = 95.0
            reason = "quote_number"
        elif ref and (ref == tool or ref in tool or tool in ref):
            score = 90.0
            reason = "tool_number"
        elif customer_id and quote.customer_id == customer_id:
            score = 55.0
            reason = "customer_only"
        if score >= 55:
            scored.append((score, quote, reason))
    scored.sort(key=lambda item: item[0], reverse=True)
    out = []
    for score, quote, reason in scored[:limit]:
        project_name = None
        if quote.project_id:
            project = db.get(Project, quote.project_id)
            project_name = project.tool_number if project else None
        out.append(
            {
                "quote_id": str(quote.id),
                "tool_number": quote.tool_number,
                "external_quote_number": quote.external_quote_number,
                "customer_id": str(quote.customer_id),
                "project_id": str(quote.project_id) if quote.project_id else None,
                "project_label": project_name,
                "confidence": score,
                "match_reason": reason,
            }
        )
    return out


def find_duplicate_invoices(
    db: Session,
    *,
    invoice_number: str | None,
    amount: Decimal | None,
    line_date: date | None,
    content_sha256: str | None,
) -> list[dict]:
    from app.models.enterprise import DocumentAsset

    duplicates: list[dict] = []
    seen_line_ids: set[str] = set()

    def _append(row: QuoteInvoiceLine, reason: str) -> None:
        key = str(row.id)
        if key in seen_line_ids:
            return
        seen_line_ids.add(key)
        duplicates.append(
            {
                "invoice_line_id": key,
                "quote_id": str(row.quote_id),
                "amount": row.amount,
                "line_date": row.line_date.isoformat(),
                "invoice_number": row.invoice_number,
                "notes": row.notes,
                "reason": reason,
            }
        )

    if content_sha256:
        sha = content_sha256.strip().lower()
        if sha:
            for row in db.scalars(
                select(QuoteInvoiceLine).where(QuoteInvoiceLine.content_sha256 == sha)
            ).all():
                _append(row, "same_document_hash")
            for asset in db.scalars(
                select(DocumentAsset).where(
                    DocumentAsset.checksum == sha,
                    DocumentAsset.entity_type == "quote",
                )
            ).all():
                # Match invoice lines on the same quote that may lack content_sha256.
                for row in db.scalars(
                    select(QuoteInvoiceLine).where(
                        QuoteInvoiceLine.quote_id == asset.entity_id
                    )
                ).all():
                    notes = (row.notes or "").lower()
                    if "pdf import" in notes or (row.invoice_number and row.content_sha256 == sha):
                        _append(row, "same_document_hash")

    if invoice_number:
        key = invoice_number.strip()
        if key:
            for row in db.scalars(
                select(QuoteInvoiceLine)
                .where(func.lower(QuoteInvoiceLine.invoice_number) == key.lower())
                .order_by(QuoteInvoiceLine.line_date.desc())
                .limit(50)
            ).all():
                _append(row, "same_invoice_number")
            # Legacy: invoice number stored only in notes.
            rows = db.scalars(
                select(QuoteInvoiceLine)
                .where(QuoteInvoiceLine.notes.is_not(None))
                .order_by(QuoteInvoiceLine.line_date.desc())
                .limit(500)
            ).all()
            for row in rows:
                notes = row.notes or ""
                if key.lower() in notes.lower():
                    _append(row, "invoice_number_in_notes")

    if amount is not None and line_date is not None and not duplicates:
        rows = db.scalars(
            select(QuoteInvoiceLine).where(
                QuoteInvoiceLine.amount == amount,
                QuoteInvoiceLine.line_date == line_date,
            )
        ).all()
        for row in rows:
            _append(row, "same_amount_and_date")

    return duplicates[:10]


def extract_invoice_pdf(
    db: Session,
    *,
    content: bytes,
    filename: str,
    team_id: UUID | None = None,
    quote_id: UUID | None = None,
) -> dict:
    """Parse PDF into review DTO. Does not create financial records.

    Always retains raw_text + extraction_quality for the review screen.
    """
    from app.services.finance.document_import_extract import (
        build_line_item,
        extract_raw_document_text,
        extraction_quality_dict,
        hours_mismatch_warning,
    )

    sha = content_fingerprint(content)
    raw = extract_raw_document_text(content, document_kind="invoice", filename=filename)
    text = raw.raw_text

    base: dict = {
        "text_extractable": raw.text_extractable,
        "ocr_used": raw.ocr_used,
        "source_chars": raw.character_count,
        "content_sha256": sha,
        "filename": filename,
        "warnings": list(raw.warnings),
        "document_type": "invoice",
        "document_type_confidence": 0.0,
        "text_extraction_method": raw.text_extraction_method,
        "raw_text": text,
        "extraction_quality": extraction_quality_dict(raw),
        "fields": {},
        "stage_hours": [],
        "line_items": [],
        "structured_warnings": [],
        "customer_matches": [],
        "quote_matches": [],
        "duplicates": [],
        "suggested_quote_id": str(quote_id) if quote_id else None,
        "source": "pdf_import",
    }

    if not text.strip():
        return base

    parsed = parse_invoice_pdf_text(text, filename=filename, content_sha256=sha)
    parsed.ocr_used = raw.ocr_used
    parsed.warnings = list(dict.fromkeys(list(base["warnings"]) + list(parsed.warnings)))
    amount = _parse_amount(parsed.amount.value)
    inv_date = _parse_iso_date(parsed.invoice_date.value)

    customer_matches = suggest_customer_matches(db, parsed.customer_name.value)
    top_customer_id: UUID | None = None
    if customer_matches:
        try:
            top_customer_id = UUID(str(customer_matches[0]["customer_id"]))
        except (ValueError, TypeError, KeyError):
            customer_matches = []
            top_customer_id = None

    quote_matches = suggest_quote_matches(
        db,
        tool_or_project_ref=parsed.project_ref.value,
        quote_ref=parsed.quote_ref.value,
        customer_id=top_customer_id,
        team_id=team_id,
    )
    if quote_id is not None:
        quote_matches = [m for m in quote_matches if m["quote_id"] != str(quote_id)]
        quote = db.get(Quote, quote_id)
        if quote is not None:
            quote_matches.insert(
                0,
                {
                    "quote_id": str(quote.id),
                    "tool_number": quote.tool_number,
                    "external_quote_number": quote.external_quote_number,
                    "customer_id": str(quote.customer_id),
                    "project_id": str(quote.project_id) if quote.project_id else None,
                    "project_label": None,
                    "confidence": 100.0,
                    "match_reason": "user_selected_quote",
                },
            )

    duplicates = find_duplicate_invoices(
        db,
        invoice_number=parsed.invoice_number.value,
        amount=amount,
        line_date=inv_date,
        content_sha256=sha,
    )
    if duplicates:
        parsed.warnings.append(
            "Possible duplicate invoice detected — review existing record before importing."
        )

    suggested_quote_id = quote_matches[0]["quote_id"] if quote_matches else None
    if suggested_quote_id and quote_matches[0]["confidence"] < 70:
        parsed.warnings.append("Project/quote match confidence is low — confirm before import.")
        suggested_quote_id = None if quote_id is None else str(quote_id)

    table_qty = _parse_amount(parsed.raw_table_quantity.value or parsed.quantity.value)
    stage_sum = _parse_amount(parsed.stage_hours_sum.value)
    stated = _parse_amount(parsed.raw_description_total_hours.value)
    mismatch = hours_mismatch_warning(
        table_quantity=float(table_qty) if table_qty is not None else None,
        stage_breakdown_total=float(stage_sum) if stage_sum is not None else None,
        stated_total=float(stated) if stated is not None else None,
    )
    rate_val = _parse_amount(parsed.rate.value)
    amt_val = _parse_amount(parsed.amount.value)
    line_items = [
        build_line_item(
            description=parsed.line_description.value,
            quantity=float(table_qty) if table_qty is not None else None,
            rate=float(rate_val) if rate_val is not None else None,
            amount=float(amt_val) if amt_val is not None else None,
            stage_hours=parsed.stage_hours,
            stated_total_hours=float(stated) if stated is not None else None,
        )
    ]

    return {
        "text_extractable": parsed.text_extractable,
        "ocr_used": parsed.ocr_used,
        "source_chars": parsed.source_chars or raw.character_count,
        "content_sha256": sha,
        "filename": filename,
        "warnings": parsed.warnings,
        "fields": {
            "invoice_number": _candidate_dict(parsed.invoice_number),
            "invoice_date": _candidate_dict(parsed.invoice_date),
            "due_date": _candidate_dict(parsed.due_date),
            "amount": _candidate_dict(parsed.amount),
            "currency_code": _candidate_dict(parsed.currency_code),
            "customer_name": _candidate_dict(parsed.customer_name),
            "project_ref": _candidate_dict(parsed.project_ref),
            "customer_project_number": _candidate_dict(parsed.project_ref),
            "po_number": _candidate_dict(parsed.po_number),
            "quote_ref": _candidate_dict(parsed.quote_ref),
            "tax_amount": _candidate_dict(parsed.tax_amount),
            "subtotal": _candidate_dict(parsed.subtotal),
            "balance_due": _candidate_dict(parsed.balance_due),
            "payment_terms": _candidate_dict(parsed.payment_terms),
            "sales_person": _candidate_dict(parsed.sales_person),
            "billing_attention": _candidate_dict(parsed.billing_attention),
            "quantity": _candidate_dict(parsed.quantity),
            "rate": _candidate_dict(parsed.rate),
            "line_description": _candidate_dict(parsed.line_description),
            "raw_table_quantity": _candidate_dict(parsed.raw_table_quantity),
            "raw_description_total_hours": _candidate_dict(parsed.raw_description_total_hours),
            "stage_hours_sum": _candidate_dict(parsed.stage_hours_sum),
            "notes": _candidate_dict(parsed.notes),
        },
        "stage_hours": parsed.stage_hours,
        "line_items": line_items,
        "structured_warnings": [mismatch] if mismatch else [],
        "document_type": parsed.document_type,
        "document_type_confidence": parsed.document_type_confidence,
        "text_extraction_method": raw.text_extraction_method,
        "raw_text": text,
        "extraction_quality": extraction_quality_dict(raw),
        "customer_matches": customer_matches,
        "quote_matches": quote_matches,
        "duplicates": [
            {
                **dup,
                "amount": float(dup["amount"]) if dup.get("amount") is not None else None,
            }
            for dup in duplicates
        ],
        "suggested_quote_id": suggested_quote_id,
        "source": "pdf_import",
    }


def confirm_invoice_pdf_import(
    db: Session,
    *,
    quote_id: UUID,
    amount: Decimal,
    line_date: date,
    notes: str | None,
    invoice_number: str | None,
    import_anyway: bool,
    content: bytes | None,
    filename: str | None,
    content_sha256: str | None,
    user: User,
    due_date: date | None = None,
    tax_amount: Decimal | None = None,
    subtotal_amount: Decimal | None = None,
) -> Quote:
    """Create invoice line from reviewed fields. Optional PDF stored against quote."""
    quote = load_quote_with_ledger(db, quote_id)
    if quote is None or not quote.is_active:
        raise ProTrackValidationError("Quote not found")

    note_parts = [part for part in (notes, ) if part]
    if invoice_number:
        tag = f"Invoice#: {invoice_number.strip()}"
        if tag not in (notes or ""):
            note_parts.insert(0, tag)
    note_parts.append("Source: PDF Import")
    final_notes = " | ".join(note_parts)

    duplicates = find_duplicate_invoices(
        db,
        invoice_number=invoice_number,
        amount=amount,
        line_date=line_date,
        content_sha256=content_sha256,
    )
    if duplicates and not import_anyway:
        raise ProTrackValidationError(
            "Possible duplicate invoice detected. Review existing invoice or set import_anyway=true."
        )

    add_invoice_line(
        db,
        quote=quote,
        amount=amount,
        line_date=line_date,
        notes=final_notes,
        invoice_number=invoice_number,
        due_date=due_date,
        tax_amount=tax_amount,
        subtotal_amount=subtotal_amount,
        content_sha256=content_sha256,
    )
    db.flush()

    if content and filename:
        store_document(
            db,
            entity_type="quote",
            entity_id=quote.id,
            filename=filename,
            content=content,
            content_type="application/pdf",
            uploaded_by=user,
            title=f"Invoice PDF {invoice_number or ''}".strip(),
            notes=f"sha256={content_sha256 or ''}; source=pdf_import",
        )

    db.commit()
    refreshed = load_quote_with_ledger(db, quote.id)
    assert refreshed is not None
    return refreshed
