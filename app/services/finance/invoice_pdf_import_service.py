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
from app.services.finance.invoice_pdf_parser import content_fingerprint
from app.services.finance.quote_cash_ledger_service import add_invoice_line, load_quote_with_ledger
from app.services.finance.quote_import_service import _find_customer


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
    """Visual document intelligence → matching → review DTO. Never auto-saves."""
    from app.services.finance.document_intelligence_service import (
        get_document_intelligence_service,
    )

    sha = content_fingerprint(content)
    analyzed = get_document_intelligence_service().analyze_invoice_document(
        content, filename=filename
    )
    fields = analyzed.get("fields") or {}
    amount = _parse_amount((fields.get("amount") or {}).get("value"))
    inv_date = _parse_iso_date((fields.get("invoice_date") or {}).get("value"))
    customer_name = (fields.get("customer_name") or {}).get("value")
    project_ref = (fields.get("customer_project_number") or fields.get("project_ref") or {}).get(
        "value"
    )

    customer_matches = suggest_customer_matches(db, customer_name)
    top_customer_id: UUID | None = None
    if customer_matches:
        try:
            top_customer_id = UUID(str(customer_matches[0]["customer_id"]))
        except (ValueError, TypeError, KeyError):
            customer_matches = []

    # Prefer project master lookup via Customer Project #
    if project_ref:
        from app.services.finance.quote_pdf_import_service import suggest_project_matches

        project_matches = suggest_project_matches(db, tool_number=project_ref, customer_id=None)
        if project_matches and project_matches[0].get("customer_id") and not top_customer_id:
            try:
                top_customer_id = UUID(str(project_matches[0]["customer_id"]))
                project_customer = db.get(Customer, top_customer_id)
                if project_customer is not None:
                    customer_matches = [
                        {
                            "customer_id": str(project_customer.id),
                            "name": project_customer.name,
                            "code": project_customer.code,
                            "confidence": 98.0,
                            "match_reason": "project_customer",
                        }
                    ] + [
                        m
                        for m in customer_matches
                        if m["customer_id"] != str(project_customer.id)
                    ]
            except (ValueError, TypeError):
                pass
    else:
        project_matches = []

    quote_matches = suggest_quote_matches(
        db,
        tool_or_project_ref=project_ref,
        quote_ref=(fields.get("quote_ref") or {}).get("value"),
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
        invoice_number=(fields.get("invoice_number") or {}).get("value"),
        amount=amount,
        line_date=inv_date,
        content_sha256=sha,
    )
    warnings = list(analyzed.get("warnings") or [])
    if duplicates:
        warnings.append(
            "Possible duplicate invoice detected — review existing record before importing."
        )

    suggested_quote_id = quote_matches[0]["quote_id"] if quote_matches else None
    if suggested_quote_id and quote_matches[0]["confidence"] < 70:
        warnings.append("Project/quote match confidence is low — confirm before import.")
        suggested_quote_id = None if quote_id is None else str(quote_id)

    notes_bits = []
    if (fields.get("invoice_number") or {}).get("value"):
        notes_bits.append(f"Invoice#: {fields['invoice_number']['value']}")
    if (fields.get("po_number") or {}).get("value"):
        notes_bits.append(f"PO: {fields['po_number']['value']}")
    if project_ref:
        notes_bits.append(f"Customer Project #: {project_ref}")
    stages = analyzed.get("stage_hours") or []
    if stages:
        notes_bits.append(
            "Stages: "
            + "; ".join(f"{s.get('label')}: {s.get('hours')}" for s in stages[:8])
        )
    if notes_bits:
        fields = {
            **fields,
            "notes": {
                "value": " | ".join(notes_bits),
                "confidence": 60,
                "source": "composed",
                "needs_review": False,
            },
        }

    hours_balance = None
    preview_quote_id = suggested_quote_id or (str(quote_id) if quote_id else None)
    this_hours = None
    qty_raw = (fields.get("quantity") or fields.get("raw_table_quantity") or {}).get("value")
    if qty_raw is not None and str(qty_raw).strip() != "":
        try:
            this_hours = Decimal(str(qty_raw).replace(",", "").strip())
        except Exception:
            this_hours = None
    if preview_quote_id and this_hours is not None:
        try:
            from app.services.finance.quote_hours_balance_service import (
                preview_partial_invoice_for_import,
                serialize_hours_balance,
            )

            hours_balance = serialize_hours_balance(
                preview_partial_invoice_for_import(
                    db,
                    quote_id=UUID(str(preview_quote_id)),
                    this_invoice_hours=this_hours,
                )
            )
            if hours_balance and hours_balance.get("is_partial_invoice"):
                warnings.append(
                    f"Partial invoice detected — remaining "
                    f"{hours_balance.get('remaining_hours_before_closure')} commercial hours."
                )
            if hours_balance and hours_balance.get("is_over_invoiced_hours"):
                warnings.append(
                    hours_balance.get("message") or "Invoice hours exceed quoted hours."
                )
        except Exception:
            hours_balance = None

    payment_terms_preview = None
    try:
        from app.models.models import Customer as CustModel
        from app.services.finance.payment_terms_service import (
            normalize_payment_terms,
            resolve_invoice_payment_terms,
        )

        terms_raw = (fields.get("payment_terms") or {}).get("value")
        due_raw = (fields.get("due_date") or {}).get("value")
        inv_date_raw = (fields.get("invoice_date") or {}).get("value")
        inv_date = None
        doc_due = None
        if inv_date_raw:
            try:
                inv_date = date.fromisoformat(str(inv_date_raw)[:10])
            except Exception:
                inv_date = None
        if due_raw:
            try:
                doc_due = date.fromisoformat(str(due_raw)[:10])
            except Exception:
                doc_due = None
        cust_terms = None
        cust_days = None
        cust_id = None
        project_terms = None
        project_days = None
        qrow = None
        if customer_matches:
            cust_id = customer_matches[0].get("customer_id")
        elif preview_quote_id:
            qrow = db.get(Quote, UUID(str(preview_quote_id)))
            if qrow:
                cust_id = qrow.customer_id
        if preview_quote_id and qrow is None:
            qrow = db.get(Quote, UUID(str(preview_quote_id)))
        if qrow is not None:
            project_terms = getattr(qrow, "payment_terms", None)
            project_days = getattr(qrow, "payment_terms_days", None)
            if cust_id is None:
                cust_id = qrow.customer_id
        if cust_id:
            cust = db.get(
                CustModel,
                UUID(str(cust_id)) if not isinstance(cust_id, UUID) else cust_id,
            )
            if cust:
                cust_terms = getattr(cust, "default_payment_terms", None)
                cust_days = getattr(cust, "default_payment_terms_days", None)
        terms_preview = resolve_invoice_payment_terms(
            document_terms=terms_raw,
            document_due_date=doc_due,
            invoice_date=inv_date,
            customer_default_terms=cust_terms,
            customer_default_days=cust_days,
            project_terms=project_terms,
            project_days=project_days,
        )
        label, days = normalize_payment_terms(terms_raw)
        payment_terms_preview = {
            **{
                k: (v.isoformat() if isinstance(v, date) else v)
                for k, v in terms_preview.items()
            },
            "document_terms_raw": terms_raw,
            "normalized_label": label,
            "normalized_days": days,
        }
        for w in terms_preview.get("warnings") or []:
            if w not in warnings:
                warnings.append(w)
    except Exception:
        payment_terms_preview = None

    return {
        "pipeline": analyzed.get("pipeline", "document_intelligence_v2"),
        "text_extractable": analyzed.get("text_extractable", True),
        "ocr_used": analyzed.get("ocr_used", False),
        "source_chars": analyzed.get("source_chars", 0),
        "content_sha256": sha,
        "filename": filename,
        "warnings": warnings,
        "document_type": analyzed.get("document_type", "invoice"),
        "document_type_confidence": analyzed.get("document_type_confidence", 0),
        "text_extraction_method": analyzed.get("text_extraction_method"),
        "raw_text": analyzed.get("raw_text"),
        "normalized_text": analyzed.get("normalized_text"),
        "extraction_quality": analyzed.get("extraction_quality"),
        "fields": fields,
        "stage_hours": stages,
        "line_items": analyzed.get("line_items") or [],
        "work_breakdown": analyzed.get("work_breakdown") or [],
        "structured_warnings": analyzed.get("structured_warnings") or [],
        "extraction_status": analyzed.get("extraction_status"),
        "quality_gate": analyzed.get("quality_gate"),
        "page_preview_data_url": analyzed.get("page_preview_data_url"),
        "page_count": analyzed.get("page_count"),
        "analysis": analyzed.get("analysis"),
        "customer_matches": customer_matches,
        "project_matches": project_matches if project_ref else [],
        "quote_matches": quote_matches,
        "duplicates": [
            {
                **dup,
                "amount": float(dup["amount"]) if dup.get("amount") is not None else None,
            }
            for dup in duplicates
        ],
        "suggested_quote_id": suggested_quote_id,
        "source": "document_intelligence",
        "hours_balance": hours_balance,
        "payment_terms_preview": payment_terms_preview,
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
    quantity_hours: Decimal | None = None,
    remaining_balance_action: str | None = None,
    acknowledge_over_hours: bool = False,
    close_balance_reason: str | None = None,
    payment_terms: str | None = None,
    payment_terms_days: int | None = None,
    payment_terms_source: str | None = None,
) -> Quote:
    """Create invoice line from reviewed fields. Optional PDF stored against quote.

    When commercial hours leave a remaining balance, ``remaining_balance_action`` must be
    ``keep_balance`` (default) or ``close_remaining_balance``. Closing does not alter the
    original quote — it records an explicit QuoteBalanceClosure.
    """
    from app.models.models import Customer
    from app.services.finance.payment_terms_service import resolve_invoice_payment_terms
    from app.services.finance.quote_hours_balance_service import (
        close_remaining_balance,
        preview_partial_invoice_for_import,
    )

    quote = load_quote_with_ledger(db, quote_id)
    if quote is None or not quote.is_active:
        raise ProTrackValidationError("Quote not found")

    customer = db.get(Customer, quote.customer_id) if quote.customer_id else None
    source_key = (payment_terms_source or "").strip().upper() or None
    if source_key == "USER_OVERRIDE":
        terms_resolved = resolve_invoice_payment_terms(
            invoice_date=line_date,
            customer_default_terms=getattr(customer, "default_payment_terms", None)
            if customer
            else None,
            customer_default_days=getattr(customer, "default_payment_terms_days", None)
            if customer
            else None,
            user_terms=payment_terms,
            user_terms_days=payment_terms_days,
            user_due_date=due_date,
        )
    else:
        terms_resolved = resolve_invoice_payment_terms(
            document_terms=payment_terms,
            document_due_date=due_date,
            invoice_date=line_date,
            customer_default_terms=getattr(customer, "default_payment_terms", None)
            if customer
            else None,
            customer_default_days=getattr(customer, "default_payment_terms_days", None)
            if customer
            else None,
            project_terms=getattr(quote, "payment_terms", None),
            project_days=getattr(quote, "payment_terms_days", None),
        )
    final_terms = terms_resolved.get("payment_terms")
    final_terms_days = terms_resolved.get("payment_terms_days")
    final_due = terms_resolved.get("due_date")
    final_terms_source = terms_resolved.get("payment_terms_source")
    final_due_source = terms_resolved.get("due_date_source")

    qty = None
    if quantity_hours is not None:
        try:
            qty = Decimal(str(quantity_hours))
        except Exception as exc:
            raise ProTrackValidationError("Invalid quantity_hours") from exc
        if qty < 0:
            raise ProTrackValidationError("quantity_hours cannot be negative")

    action = (remaining_balance_action or "").strip().lower() or None
    if action in ("", "none"):
        action = None
    if action not in (None, "keep_balance", "close_remaining_balance"):
        raise ProTrackValidationError(
            "remaining_balance_action must be keep_balance or close_remaining_balance"
        )

    hours_preview = preview_partial_invoice_for_import(
        db, quote_id=quote_id, this_invoice_hours=qty
    )
    if hours_preview:
        if hours_preview.get("is_over_invoiced_hours") and not acknowledge_over_hours:
            raise ProTrackValidationError(
                hours_preview.get("message")
                or "Invoice quantity exceeds quoted quantity. Acknowledge over-hours to continue."
            )
        if hours_preview.get("decision_required"):
            if action is None:
                # Default KEEP BALANCE when decision required but omitted
                action = "keep_balance"
            if action not in ("keep_balance", "close_remaining_balance"):
                raise ProTrackValidationError(
                    "Partial invoice detected — choose keep_balance or close_remaining_balance."
                )
        elif action == "close_remaining_balance":
            raise ProTrackValidationError(
                "Cannot close remaining balance — no billable hours remain to close."
            )

    note_parts = [part for part in (notes, ) if part]
    if invoice_number:
        tag = f"Invoice#: {invoice_number.strip()}"
        if tag not in (notes or ""):
            note_parts.insert(0, tag)
    note_parts.append("Source: PDF Import")
    if action == "keep_balance" and hours_preview and hours_preview.get("decision_required"):
        rem = hours_preview.get("remaining_hours_before_closure")
        note_parts.append(f"Balance decision: KEEP ({rem} hrs remaining)")
    elif action == "close_remaining_balance":
        rem = (hours_preview or {}).get("remaining_hours_before_closure")
        note_parts.append(f"Balance decision: CLOSE ({rem} hrs waived)")
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

    line = add_invoice_line(
        db,
        quote=quote,
        amount=amount,
        line_date=line_date,
        notes=final_notes,
        invoice_number=invoice_number,
        due_date=final_due,
        tax_amount=tax_amount,
        subtotal_amount=subtotal_amount,
        content_sha256=content_sha256,
        quantity_hours=qty,
        payment_terms=final_terms,
        payment_terms_days=final_terms_days,
        payment_terms_source=final_terms_source,
        payment_model=getattr(quote, "payment_model", None),
        due_date_source=final_due_source,
    )
    db.flush()

    if action == "close_remaining_balance":
        close_remaining_balance(
            db,
            quote=quote,
            related_invoice_line=line,
            user=user,
            reason=close_balance_reason,
        )

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
