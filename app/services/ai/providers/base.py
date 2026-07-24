"""LLM provider protocol for optional narrative enrichment (R5)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LlmProvider(Protocol):
    """Optional LLM enrichment. Soft-fail: return None on any error / offline."""

    name: str

    def enrich(self, prompt: str, *, context: dict[str, Any] | None = None) -> str | None:
        """Return a short enrichment string, or None to keep heuristic-only output."""

    def is_available(self) -> bool:
        """True when this provider can realistically call an LLM."""
