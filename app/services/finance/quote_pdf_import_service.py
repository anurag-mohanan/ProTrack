"""Quote PDF import — extract → review → confirm (never auto-save)."""

from __future__ import annotations

from datetime import date
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
    from app.services.finance.prosohm_document_intelligence import parse_prosohm_date

    return parse_prosohm_date(raw)


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
    """Visual document intelligence → matching → review DTO. Never auto-saves."""
    from app.services.finance.document_intelligence_service import (
        get_document_intelligence_service,
    )

    sha = content_fingerprint(content)
    analyzed = get_document_intelligence_service().analyze_quote_document(
        content, filename=filename
    )
    fields = analyzed.get("fields") or {}
    customer_name = (fields.get("customer_name") or {}).get("value")
    tool_number = (
        (fields.get("customer_project_number") or {}).get("value")
        or (fields.get("tool_number") or {}).get("value")
    )
    quote_number = (
        (fields.get("external_quote_number") or {}).get("value")
        or (fields.get("quote_number") or {}).get("value")
    )

    customer_matches = suggest_customer_matches(db, customer_name)
    top_customer_id: UUID | None = None
    if customer_matches:
        try:
            top_customer_id = UUID(str(customer_matches[0]["customer_id"]))
        except (ValueError, TypeError, KeyError):
            customer_matches = []

    project_matches = suggest_project_matches(db, tool_number=tool_number, customer_id=None)
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
                    m for m in customer_matches if m["customer_id"] != str(project_customer.id)
                ]
        except (ValueError, TypeError):
            pass
    elif top_customer_id is not None:
        project_matches = (
            suggest_project_matches(db, tool_number=tool_number, customer_id=top_customer_id)
            or project_matches
        )

    duplicates = find_duplicate_quotes(
        db,
        external_quote_number=quote_number,
        tool_number=tool_number,
        customer_id=top_customer_id,
        content_sha256=sha,
    )
    warnings = list(analyzed.get("warnings") or [])
    if duplicates:
        warnings.append(
            "Possible duplicate quote detected — review existing record before importing."
        )
    if top_customer_id is None:
        warnings.append("Customer match confidence is low — confirm customer before import.")
    if tool_number and not project_matches:
        warnings.append(
            f"Project not found for Customer Project # {tool_number}. "
            "Select an existing project or enable Create project if missing."
        )

    _ = team_id
    return {
        "pipeline": analyzed.get("pipeline", "document_intelligence_v2"),
        "text_extractable": analyzed.get("text_extractable", True),
        "ocr_used": analyzed.get("ocr_used", False),
        "source_chars": analyzed.get("source_chars", 0),
        "content_sha256": sha,
        "filename": filename,
        "warnings": warnings,
        "document_type": analyzed.get("document_type", "quote"),
        "document_type_confidence": analyzed.get("document_type_confidence", 0),
        "text_extraction_method": analyzed.get("text_extraction_method"),
        "raw_text": analyzed.get("raw_text"),
        "normalized_text": analyzed.get("normalized_text"),
        "extraction_quality": analyzed.get("extraction_quality"),
        "fields": fields,
        "stage_hours": analyzed.get("stage_hours") or [],
        "line_items": analyzed.get("line_items") or [],
        "work_breakdown": analyzed.get("work_breakdown") or [],
        "structured_warnings": analyzed.get("structured_warnings") or [],
        "extraction_status": analyzed.get("extraction_status"),
        "quality_gate": analyzed.get("quality_gate"),
        "page_preview_data_url": analyzed.get("page_preview_data_url"),
        "page_count": analyzed.get("page_count"),
        "analysis": analyzed.get("analysis"),
        "customer_matches": customer_matches,
        "project_matches": project_matches,
        "duplicates": duplicates,
        "suggested_customer_id": (
            customer_matches[0]["customer_id"] if customer_matches else None
        ),
        "suggested_project_id": (
            project_matches[0]["project_id"] if project_matches else None
        ),
        "source": "document_intelligence",
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
