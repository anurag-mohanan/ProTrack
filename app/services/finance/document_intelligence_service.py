"""DocumentIntelligenceService — visual + native text finance PDF understanding.

Primary path: layout-aware visual analysis (word coordinates + page render).
Optional enhancement: existing OpenAI-compatible vision model when configured.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from app.services.finance.document_import_extract import (
    build_line_item,
    extract_raw_document_text,
    extraction_quality_dict,
    hours_mismatch_warning,
)
from app.services.finance.prosohm_layout_analyzer import LayoutAnalysis, analyze_prosohm_layout

logger = logging.getLogger(__name__)

FINANCE_DOC_ANALYSIS_SYSTEM = """You are analyzing a financial quote or invoice document for Prosohm.

Read the ENTIRE document visually and from the supplied text.
Do not stop after finding the document number.
Identify every relevant field visible in the document.
Understand relationships between labels and values from visual layout.
Read tables, customer blocks, project information, commercial values, work descriptions, totals and terms.
Return structured JSON only matching the requested schema.
Do not invent values. If a value is not visible, return null.
If the document contains inconsistencies, report them in warnings — do not silently resolve them.
"""


def render_pdf_page_images(content: bytes, *, max_pages: int = 3, dpi: int = 150) -> list[bytes]:
    """Render PDF pages to PNG bytes. Prefer pdfplumber; fall back to pdf2image."""
    images: list[bytes] = []
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:max_pages]:
                page_image = page.to_image(resolution=dpi)
                buf = io.BytesIO()
                page_image.original.save(buf, format="PNG")
                images.append(buf.getvalue())
        if images:
            return images
    except Exception as exc:  # noqa: BLE001
        logger.info("pdfplumber render failed: %s", exc)

    try:
        from pdf2image import convert_from_bytes

        pil_pages = convert_from_bytes(content, dpi=dpi, first_page=1, last_page=max_pages)
        for page in pil_pages:
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            images.append(buf.getvalue())
    except Exception as exc:  # noqa: BLE001
        logger.info("pdf2image render failed: %s", exc)
    return images


def _field_to_candidate(hit) -> dict:
    if hit is None:
        return {"value": None, "confidence": 0, "source": None, "needs_review": True, "evidence": None}
    empty = hit.value is None or str(hit.value).strip() == ""
    return {
        "value": None if empty else str(hit.value),
        "confidence": float(hit.confidence or 0) * (100 if hit.confidence <= 1 else 1),
        "source": hit.source,
        "needs_review": empty or (hit.confidence or 0) < 0.6,
        "evidence": hit.evidence,
    }


def _layout_to_review_fields(layout: LayoutAnalysis, *, kind: str) -> dict[str, dict]:
    f = layout.fields
    out: dict[str, dict] = {}

    def put(key: str, hit_key: str) -> None:
        if hit_key in f:
            out[key] = _field_to_candidate(f[hit_key])

    if kind == "invoice":
        put("invoice_number", "invoice_number")
        put("invoice_date", "invoice_date")
        put("due_date", "due_date")
        put("payment_terms", "payment_terms")
        put("sales_person", "sales_person")
        put("po_number", "po_number")
        put("customer_project_number", "customer_project_number")
        put("project_ref", "customer_project_number")
        put("customer_name", "customer_name")
        put("billing_attention", "billing_attention")
        put("currency_code", "currency")
        put("quantity", "quantity")
        put("raw_table_quantity", "quantity")
        put("rate", "rate")
        put("subtotal", "subtotal")
        put("tax_amount", "tax")
        put("amount", "total")
        put("balance_due", "balance_due")
        put("line_description", "line_description")
        put("stage_hours_sum", "stage_hours_sum")
        put("raw_description_total_hours", "stated_total_hours")
        if "line_amount" in f and "amount" not in out:
            out["amount"] = _field_to_candidate(f["line_amount"])
    else:
        put("external_quote_number", "quote_number")
        put("quote_number", "quote_number")
        put("quoted_date", "quote_date")
        put("sales_person", "sales_person")
        put("customer_project_number", "customer_project_number")
        put("tool_number", "customer_project_number")
        put("customer_name", "customer_name")
        put("customer_contact", "customer_contact")
        put("currency_code", "currency")
        put("quoted_hours", "quantity")
        put("raw_table_quantity", "quantity")
        put("rate", "rate")
        put("subtotal", "subtotal")
        put("quoted_revenue", "total")
        put("line_description", "line_description")
        put("payment_terms", "payment_terms")
        put("stage_hours_sum", "stage_hours_sum")
        put("raw_description_total_hours", "stated_total_hours")
        if "line_amount" in f and "quoted_revenue" not in out:
            out["quoted_revenue"] = _field_to_candidate(f["line_amount"])
        if "total" not in f and "line_amount" in f:
            out["quoted_revenue"] = _field_to_candidate(f["line_amount"])
    return out


def _quality_gate(fields: dict[str, dict], *, kind: str) -> dict[str, Any]:
    if kind == "invoice":
        required = [
            "invoice_number",
            "invoice_date",
            "customer_project_number",
            "customer_name",
            "currency_code",
            "amount",
        ]
    else:
        required = [
            "external_quote_number",
            "quoted_date",
            "customer_project_number",
            "customer_name",
            "currency_code",
            "quoted_revenue",
        ]
    present = [k for k in required if fields.get(k, {}).get("value")]
    missing = [k for k in required if k not in present]
    ready = len(missing) == 0
    return {
        "status": "READY_FOR_REVIEW" if ready else "INCOMPLETE",
        "required_fields": required,
        "present_fields": present,
        "missing_fields": missing,
        "completeness": round(len(present) / max(len(required), 1), 2),
    }


def _call_vision_llm(
    *,
    page_images: list[bytes],
    native_text: str,
    kind: str,
    filename: str | None,
    timeout_seconds: float = 12.0,
) -> dict[str, Any] | None:
    """Optional multimodal JSON extraction via configured OpenAI-compatible provider.

    Keep timeout short so IIS/ARR reverse proxies (often ~30s) are not tripped.
    """
    from app.core import config
    from app.services.ai.providers.registry import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_available() or config.AI_PROVIDER.strip().lower() != "openai":
        return None
    if not hasattr(provider, "analyze_document_json"):
        return None
    try:
        return provider.analyze_document_json(  # type: ignore[attr-defined]
            system=FINANCE_DOC_ANALYSIS_SYSTEM,
            kind=kind,
            native_text=native_text[:8000],
            page_images_png=page_images[:2],
            filename=filename,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Vision LLM analysis skipped: %s", exc)
        return None


class DocumentIntelligenceService:
    """Central finance document understanding.

    Order: native text → deterministic field extractors → layout/visual → optional LLM.
    """

    def analyze_document(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        expected_kind: str | None = None,
    ) -> dict[str, Any]:
        from app.services.finance.deterministic_prosohm_extractor import (
            deterministic_to_review_fields,
            extract_deterministic_document,
        )

        raw = extract_raw_document_text(
            content,
            document_kind=(expected_kind or "invoice"),
            filename=filename,
        )
        page_images = render_pdf_page_images(content)
        layout = analyze_prosohm_layout(content, filename=filename)
        deterministic = extract_deterministic_document(
            raw.raw_text,
            filename=filename,
            expected_kind=expected_kind,
        )

        # Prefer deterministic classification when strong; never leave UNKNOWN for Prosohm docs
        doc_type = deterministic.document_type
        doc_conf = deterministic.document_type_confidence
        if doc_type == "UNKNOWN" and layout.document_type != "UNKNOWN":
            doc_type = layout.document_type
            doc_conf = layout.document_type_confidence
        if doc_type == "UNKNOWN" and expected_kind:
            doc_type = expected_kind.upper()
            doc_conf = max(doc_conf, 0.85)

        kind = doc_type.lower() if doc_type in {"INVOICE", "QUOTE"} else (
            (expected_kind or "invoice").lower()
        )

        det_fields = deterministic_to_review_fields(deterministic)
        layout_fields = _layout_to_review_fields(
            layout, kind=kind if kind in {"quote", "invoice"} else "invoice"
        )
        fields = _fuse_fields(det_fields, layout_fields)
        gate = _quality_gate(fields, kind="invoice" if kind == "invoice" else "quote")

        # Only call vision when deterministic+layout is incomplete. Avoids IIS/ARR
        # proxy timeouts when OpenAI is configured but fields are already complete.
        vision_json = None
        if gate["status"] == "INCOMPLETE":
            vision_json = _call_vision_llm(
                page_images=page_images,
                native_text=raw.raw_text,
                kind=kind,
                filename=filename,
                timeout_seconds=12.0,
            )
            if vision_json:
                layout = _merge_vision_into_layout(layout, vision_json)
                layout_fields = _layout_to_review_fields(
                    layout, kind=kind if kind in {"quote", "invoice"} else "invoice"
                )
                fields = _fuse_fields(det_fields, layout_fields)
                gate = _quality_gate(fields, kind="invoice" if kind == "invoice" else "quote")

        # Alias fill for review UI (quantity / quote_date)
        if not (fields.get("quantity") or {}).get("value") and (fields.get("raw_table_quantity") or {}).get("value"):
            fields["quantity"] = dict(fields["raw_table_quantity"])
        if kind == "quote":
            if not (fields.get("quote_date") or {}).get("value") and (fields.get("quoted_date") or {}).get("value"):
                fields["quote_date"] = dict(fields["quoted_date"])
            if not (fields.get("quoted_date") or {}).get("value") and (fields.get("quote_date") or {}).get("value"):
                fields["quoted_date"] = dict(fields["quote_date"])

        stages = [
            {
                "label": s.get("stage") or s.get("label"),
                "hours": s.get("hours"),
                "source_line": s.get("evidence"),
            }
            for s in (deterministic.work_breakdown or layout.work_breakdown)
        ]
        line_items = deterministic.line_items or layout.line_items or []
        if not line_items and fields.get("line_description", {}).get("value"):
            line_items = [
                build_line_item(
                    description=fields["line_description"]["value"],
                    quantity=_float_or_none(fields.get("quantity") or fields.get("raw_table_quantity")),
                    rate=_float_or_none(fields.get("rate")),
                    amount=_float_or_none(fields.get("amount") or fields.get("quoted_revenue")),
                    stage_hours=stages,
                    stated_total_hours=_float_or_none(fields.get("raw_description_total_hours")),
                )
            ]

        mismatch = hours_mismatch_warning(
            table_quantity=_float_or_none(fields.get("raw_table_quantity") or fields.get("quantity")),
            stage_breakdown_total=_float_or_none(fields.get("stage_hours_sum")),
            stated_total=_float_or_none(fields.get("raw_description_total_hours")),
        )
        warnings = list(raw.warnings) + list(deterministic.warnings) + list(layout.warnings)
        if mismatch:
            warnings.append(mismatch["message"])

        if gate["status"] == "INCOMPLETE":
            warnings.append(
                "Extraction Status: INCOMPLETE — missing "
                + ", ".join(gate["missing_fields"])
            )
        else:
            warnings.append("Extraction Status: READY FOR REVIEW")

        preview_data_url = None
        if page_images:
            b64 = base64.b64encode(page_images[0]).decode("ascii")
            preview_data_url = f"data:image/png;base64,{b64}"

        return {
            "pipeline": "document_intelligence_v2",
            "text_extractable": bool(raw.raw_text.strip()) or layout.word_count > 0,
            "ocr_used": raw.ocr_used,
            "source_chars": raw.character_count or len(raw.raw_text),
            "filename": filename,
            "warnings": warnings,
            "document_type": kind,
            "document_type_confidence": round(max(doc_conf, 0.01) * 100, 1),
            "text_extraction_method": "deterministic+visual_layout+native_pdf"
            + ("+llm_vision" if vision_json else ""),
            "raw_text": raw.raw_text,
            "normalized_text": deterministic.normalized_text,
            "extraction_quality": {
                **extraction_quality_dict(raw),
                "word_count": layout.word_count,
                "pages": layout.page_count,
                "analysis_method": "deterministic+layout",
                "llm_vision_used": bool(vision_json),
                "deterministic_field_count": len(det_fields),
                "layout_field_count": len(layout_fields),
            },
            "fields": fields,
            "stage_hours": stages,
            "line_items": line_items,
            "work_breakdown": deterministic.work_breakdown or layout.work_breakdown,
            "structured_warnings": [mismatch] if mismatch else [],
            "extraction_status": gate["status"],
            "quality_gate": gate,
            "page_preview_data_url": preview_data_url,
            "page_count": layout.page_count,
            "analysis": {
                "deterministic": {
                    "document_type": deterministic.document_type,
                    "confidence": deterministic.document_type_confidence,
                    "field_count": len(deterministic.fields),
                },
                "layout": {
                    "document_type": layout.document_type,
                    "confidence": layout.document_type_confidence,
                    "field_count": len(layout.fields),
                    "method": layout.method,
                },
                "vision_llm": bool(vision_json),
            },
            "source": "document_intelligence",
        }

    def analyze_quote_document(self, content: bytes, *, filename: str | None = None) -> dict[str, Any]:
        return self.analyze_document(content, filename=filename, expected_kind="quote")

    def analyze_invoice_document(self, content: bytes, *, filename: str | None = None) -> dict[str, Any]:
        return self.analyze_document(content, filename=filename, expected_kind="invoice")

    def analyze_debug(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        expected_kind: str | None = None,
    ) -> dict[str, Any]:
        """Full diagnostic payload — no Finance persistence."""
        from app.services.workorder_pdf_extract import extract_pdf_text
        from app.services.finance.deterministic_prosohm_extractor import (
            extract_deterministic_document,
            normalize_pdf_text,
        )

        native_ok = True
        native_text = ""
        native_error = None
        try:
            native_text = extract_pdf_text(content) or ""
        except Exception as exc:  # noqa: BLE001
            native_ok = False
            native_error = str(exc)

        images = render_pdf_page_images(content)
        dims = None
        if images:
            try:
                from PIL import Image

                im = Image.open(io.BytesIO(images[0]))
                dims = f"{im.width}x{im.height}"
            except Exception:
                dims = f"bytes={len(images[0])}"

        structured = self.analyze_document(
            content, filename=filename, expected_kind=expected_kind
        )
        det = extract_deterministic_document(
            native_text, filename=filename, expected_kind=expected_kind
        )

        # Compact structured summary for logs
        field_summary = {
            k: (v.get("value") if isinstance(v, dict) else v)
            for k, v in (structured.get("fields") or {}).items()
            if isinstance(v, dict) and v.get("value")
        }

        return {
            "filename": filename,
            "page_count": structured.get("page_count"),
            "pipeline": "document_intelligence_v2",
            "native_text": {
                "success": native_ok and bool(native_text.strip()),
                "length": len(native_text),
                "error": native_error,
                "text": native_text,
                "normalized_length": len(normalize_pdf_text(native_text)),
                "contains_invoice_number": "INV-2026-27-051" in native_text,
                "contains_quote_number": "QT-2026-27-036" in native_text,
            },
            "render": {
                "success": bool(images),
                "page_count": len(images),
                "image_dimensions": dims,
            },
            "document_classification": {
                "type": structured.get("document_type"),
                "confidence": structured.get("document_type_confidence"),
                "deterministic_type": det.document_type,
            },
            "structured_extraction": field_summary,
            "full_result": structured,
            "validation": structured.get("quality_gate"),
            "stage_hours": structured.get("stage_hours"),
        }


def _fuse_fields(primary: dict[str, dict], secondary: dict[str, dict]) -> dict[str, dict]:
    """Prefer primary non-empty values; fill gaps from secondary; keep higher confidence."""
    out = dict(secondary)
    for key, cand in primary.items():
        if not cand or not cand.get("value"):
            continue
        existing = out.get(key)
        if not existing or not existing.get("value"):
            out[key] = cand
            continue
        if float(cand.get("confidence") or 0) >= float(existing.get("confidence") or 0):
            out[key] = cand
    return out


def _float_or_none(field: dict | None) -> float | None:
    if not field or field.get("value") in (None, ""):
        return None
    try:
        return float(Decimal(str(field["value"]).replace(",", "")))
    except Exception:
        return None


def _merge_vision_into_layout(layout: LayoutAnalysis, vision: dict[str, Any]) -> LayoutAnalysis:
    """Fill null layout fields from LLM vision JSON; never invent when layout already has value."""
    from app.services.finance.prosohm_layout_analyzer import FieldHit

    mapping = {
        "invoice_number": ("document", "invoice_number"),
        "invoice_date": ("document", "invoice_date"),
        "due_date": ("document", "due_date"),
        "quote_number": ("document", "quote_number"),
        "quote_date": ("document", "quote_date"),
        "currency": ("document", "currency"),
        "sales_person": ("document", "sales_person"),
        "customer_project_number": ("project", "customer_project_number"),
        "customer_name": ("customer", "name"),
        "billing_attention": ("customer", "billing_attention"),
        "customer_contact": ("customer", "attention"),
        "po_number": ("purchase", "po_number"),
        "subtotal": ("commercial", "subtotal"),
        "tax": ("commercial", "tax"),
        "total": ("commercial", "total"),
        "balance_due": ("commercial", "balance_due"),
        "payment_terms": ("terms", "payment_terms"),
    }
    for field_key, path in mapping.items():
        if field_key in layout.fields and layout.fields[field_key].value:
            continue
        node: Any = vision
        for part in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if node in (None, ""):
            continue
        layout.fields[field_key] = FieldHit(
            value=str(node),
            confidence=0.88,
            source="document_visual_llm",
            evidence="llm_vision",
        )
    if vision.get("document_type") in {"QUOTE", "INVOICE"}:
        layout.document_type = vision["document_type"]
        layout.document_type_confidence = max(layout.document_type_confidence, 0.95)
    wb = vision.get("work_breakdown")
    if isinstance(wb, list) and wb and not layout.work_breakdown:
        layout.work_breakdown = wb
    return layout


# Singleton-style accessor
_document_intelligence_service: DocumentIntelligenceService | None = None


def get_document_intelligence_service() -> DocumentIntelligenceService:
    global _document_intelligence_service
    if _document_intelligence_service is None:
        _document_intelligence_service = DocumentIntelligenceService()
    return _document_intelligence_service


__all__ = [
    "DocumentIntelligenceService",
    "get_document_intelligence_service",
    "render_pdf_page_images",
]
