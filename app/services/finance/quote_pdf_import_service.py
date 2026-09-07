"""Quote PDF import — extract → review → confirm (never auto-save)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote
from app.models.models import Customer, Project, User
from app.services.document_asset_service import store_document
from app.services.finance.invoice_pdf_parser import content_fingerprint
from app.services.finance.invoice_pdf_import_service import suggest_customer_matches
from app.services.finance.pdf_ocr import extract_text_with_optional_ocr
from app.services.finance.prosohm_quote_pdf_parser import (
    extract_prosohm_quote_text,
    looks_like_prosohm_qt_pdf,
    parse_prosohm_quote_text,
)
from app.services.finance.quote_import_service import import_quote_row
from app.services.finance.quote_field_recognizer import enrich_import_row


def _field(
    value: str | None,
    *,
    confidence: float,
    source: str,
    needs_review: bool | None = None,
) -> dict:
    empty = value is None or str(value).strip() == ""
    review = needs_review if needs_review is not None else (empty or confidence < 60)
    return {
        "value": None if empty else str(value),
        "confidence": confidence,
        "source": source,
        "needs_review": review,
    }


def _parse_quote_date_to_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def suggest_project_matches(
    db: Session,
    *,
    tool_number: str | None,
    customer_id: UUID | None = None,
    limit: int = 8,
) -> list[dict]:
    if not tool_number or not str(tool_number).strip():
        return []
    ref = str(tool_number).strip().lower()
    stmt = select(Project).where(Project.is_deleted.is_(False))
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    projects = list(db.scalars(stmt.limit(300)).all())
    scored: list[tuple[float, Project]] = []
    for project in projects:
        tool = (project.tool_number or "").lower()
        score = 0.0
        if tool == ref:
            score = 98.0
        elif ref in tool or tool in ref:
            score = 80.0
        if score >= 80:
            scored.append((score, project))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "project_id": str(p.id),
            "tool_number": p.tool_number,
            "name": p.part_description,
            "customer_id": str(p.customer_id) if p.customer_id else None,
            "confidence": score,
        }
        for score, p in scored[:limit]
    ]


def find_duplicate_quotes(
    db: Session,
    *,
    external_quote_number: str | None,
    tool_number: str | None,
    customer_id: UUID | None,
    content_sha256: str | None = None,
) -> list[dict]:
    duplicates: list[dict] = []
    if external_quote_number and external_quote_number.strip():
        key = external_quote_number.strip().lower()
        rows = db.scalars(
            select(Quote).where(
                Quote.is_active.is_(True),
                Quote.external_quote_number.is_not(None),
            )
        ).all()
        for row in rows:
            ext = (row.external_quote_number or "").strip().lower()
            if ext and (ext == key or key in ext or ext in key):
                duplicates.append(
                    {
                        "quote_id": str(row.id),
                        "tool_number": row.tool_number,
                        "external_quote_number": row.external_quote_number,
                        "customer_id": str(row.customer_id),
                        "reason": "same_quote_number",
                    }
                )
    if tool_number and customer_id is not None and not duplicates:
        row = db.scalar(
            select(Quote).where(
                Quote.is_active.is_(True),
                Quote.customer_id == customer_id,
                func.lower(Quote.tool_number) == tool_number.strip().lower(),
            )
        )
        if row is not None:
            duplicates.append(
                {
                    "quote_id": str(row.id),
                    "tool_number": row.tool_number,
                    "external_quote_number": row.external_quote_number,
                    "customer_id": str(row.customer_id),
                    "reason": "same_customer_and_project",
                }
            )
    _ = content_sha256
    return duplicates[:10]


def extract_quote_pdf(
    db: Session,
    *,
    content: bytes,
    filename: str,
    team_id: UUID | None = None,
) -> dict:
    """Parse Prosohm QT PDF into review DTO. Does not create financial records."""
    sha = content_fingerprint(content)
    empty = {
        "text_extractable": False,
        "ocr_used": False,
        "source_chars": 0,
        "content_sha256": sha,
        "filename": filename,
        "warnings": [],
        "fields": {},
        "customer_matches": [],
        "project_matches": [],
        "duplicates": [],
        "suggested_customer_id": None,
        "suggested_project_id": None,
        "source": "pdf_quote_import",
    }

    try:
        text = extract_prosohm_quote_text(content)
    except ProTrackValidationError as exc:
        text = ""
        extract_error: str | None = str(exc)
    else:
        extract_error = None

    ocr = extract_text_with_optional_ocr(content, existing_text=text)
    text = ocr.text
    ocr_warnings = ([extract_error] if extract_error else []) + ocr.warnings

    if not text.strip():
        empty["warnings"] = ocr_warnings or [
            "Unable to extract text from this PDF. Scanned image PDFs need OCR — "
            "use a text PDF or enter the quote manually."
        ]
        return empty

    empty["ocr_used"] = ocr.ocr_used

    if not looks_like_prosohm_qt_pdf(filename=filename, text=text):
        empty["text_extractable"] = True
        empty["source_chars"] = len(text)
        empty["warnings"] = ocr_warnings + [
            "PDF does not look like a Prosohm QT quote layout. "
            "Use a Prosohm Quote# PDF or enter the quote manually."
        ]
        return empty

    customers = list(db.scalars(select(Customer).where(Customer.is_active.is_(True))).all())
    candidates = [(c.name or "", c.code or "") for c in customers]

    try:
        parsed = parse_prosohm_quote_text(
            text,
            filename=filename,
            customer_candidates=candidates,
        )
    except ProTrackValidationError as exc:
        empty["text_extractable"] = True
        empty["source_chars"] = len(text)
        empty["warnings"] = ocr_warnings + [str(exc)]
        return empty

    quote_date_iso = _parse_quote_date_to_iso(parsed.quote_date)
    customer_matches = suggest_customer_matches(db, parsed.prepared_for)
    top_customer_id = (
        UUID(customer_matches[0]["customer_id"]) if customer_matches else None
    )
    project_matches = suggest_project_matches(
        db,
        tool_number=parsed.tool_number,
        customer_id=top_customer_id,
    )
    duplicates = find_duplicate_quotes(
        db,
        external_quote_number=parsed.external_quote_number,
        tool_number=parsed.tool_number,
        customer_id=top_customer_id,
        content_sha256=sha,
    )

    warnings = ocr_warnings + list(parsed.warnings)
    if duplicates:
        warnings.append(
            "Possible duplicate quote detected — review existing record before importing."
        )
    if top_customer_id is None:
        warnings.append("Customer match confidence is low — confirm customer before import.")
    if quote_date_iso is None and parsed.quote_date:
        warnings.append(f"Could not normalize quote date '{parsed.quote_date}'.")
    elif quote_date_iso is None:
        warnings.append("Quote date not detected — confirm before import.")

    _ = team_id  # reserved for future team-scoped matching

    return {
        "text_extractable": True,
        "ocr_used": ocr.ocr_used,
        "source_chars": len(text),
        "content_sha256": sha,
        "filename": filename,
        "warnings": warnings,
        "fields": {
            "external_quote_number": _field(
                parsed.external_quote_number, confidence=95, source="quote_number"
            ),
            "tool_number": _field(parsed.tool_number, confidence=95, source="project_number"),
            "quoted_date": _field(
                quote_date_iso,
                confidence=90 if quote_date_iso else 20,
                source="quote_date",
                needs_review=quote_date_iso is None,
            ),
            "customer_name": _field(
                parsed.prepared_for,
                confidence=85 if customer_matches else 40,
                source="prepared_for",
                needs_review=not customer_matches,
            ),
            "quoted_hours": _field(
                str(parsed.quoted_hours), confidence=90, source="line_qty"
            ),
            "quoted_revenue": _field(
                str(parsed.quoted_revenue), confidence=92, source="total"
            ),
            "currency_code": _field(
                parsed.currency_code, confidence=85, source="currency"
            ),
            "line_description": _field(
                parsed.line_description, confidence=70, source="line_description"
            ),
            "sales_person": _field(
                parsed.sales_person, confidence=75, source="sales_person"
            ),
            "notes": _field(parsed.line_notes or None, confidence=60, source="notes"),
        },
        "customer_matches": customer_matches,
        "project_matches": project_matches,
        "duplicates": duplicates,
        "suggested_customer_id": (
            customer_matches[0]["customer_id"] if customer_matches else None
        ),
        "suggested_project_id": (
            project_matches[0]["project_id"] if project_matches else None
        ),
        "source": "pdf_quote_import",
    }


def confirm_quote_pdf_import(
    db: Session,
    *,
    team_id: UUID,
    customer_id: UUID,
    tool_number: str,
    quoted_revenue: Decimal,
    external_quote_number: str | None,
    currency_code: str | None,
    quoted_hours: Decimal | None,
    quoted_date: date | None,
    create_project: bool,
    import_anyway: bool,
    notes: str | None,
    content: bytes | None,
    filename: str | None,
    content_sha256: str | None,
    user: User,
):
    """Create awarded quote from reviewed fields. Optional PDF stored against quote."""
    tool = tool_number.strip()
    if not tool:
        raise ProTrackValidationError("Project # is required.")
    if quoted_revenue < 0:
        raise ProTrackValidationError("Quoted revenue must be zero or greater.")

    duplicates = find_duplicate_quotes(
        db,
        external_quote_number=external_quote_number,
        tool_number=tool,
        customer_id=customer_id,
        content_sha256=content_sha256,
    )
    if duplicates and not import_anyway:
        raise ProTrackValidationError(
            "Possible duplicate quote detected. Review existing quote or set import_anyway=true."
        )

    customer = db.get(Customer, customer_id)
    if customer is None or not customer.is_active:
        raise ProTrackValidationError("Customer not found or inactive.")

    hours = quoted_hours if quoted_hours is not None else Decimal("0")
    currency = (currency_code or "").strip().upper() or (
        customer.default_currency_code or "INR"
    ).strip().upper()

    note_parts = [part for part in (notes,) if part]
    note_parts.append("Source: PDF Quote Import")
    final_notes = "\n".join(note_parts)

    row: dict[str, object] = {
        "customer": customer.name,
        "tool_number": tool,
        "quoted_hours": hours,
        "estimated_cost": Decimal("0"),
        "quoted_revenue": quoted_revenue,
        "currency": currency,
        "external_quote_number": (external_quote_number or "").strip() or None,
        "notes": final_notes,
        "_soft_customer_match": False,
        "_warnings": [],
    }
    if quoted_date is not None:
        row["quoted_date"] = quoted_date
        row["start_date"] = quoted_date

    outcome = import_quote_row(
        db,
        row=enrich_import_row(row, filename=filename),
        actor=user,
        source="pdf_qt_confirm",
        team_id=team_id,
        create_project=create_project,
    )
    db.flush()

    if content and filename:
        store_document(
            db,
            entity_type="quote",
            entity_id=outcome.quote.id,
            filename=filename,
            content=content,
            content_type="application/pdf",
            uploaded_by=user,
            title=f"Quote PDF {external_quote_number or tool}".strip(),
            notes=f"sha256={content_sha256 or ''}; source=pdf_quote_import",
        )

    return outcome
