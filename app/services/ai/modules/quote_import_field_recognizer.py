"""AI module wrapper for awarded-quote field recognition."""

from __future__ import annotations

from typing import Any

from app.services.ai.base import AiContext, AiModule
from app.services.finance.quote_field_recognizer import enrich_import_row


class QuoteImportFieldRecognizerModule(AiModule):
    name = "quote_import_field_recognizer"

    def run(self, ctx: AiContext, **kwargs: Any) -> dict[str, object]:  # noqa: ARG002
        row = kwargs.get("row") or {}
        if not isinstance(row, dict):
            raise ValueError("row must be a dict")
        filename = kwargs.get("filename")
        return enrich_import_row(
            row,
            filename=filename if isinstance(filename, str) else None,
        )
