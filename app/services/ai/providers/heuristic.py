"""Default offline LLM provider — never calls an external model."""

from __future__ import annotations

from typing import Any


class HeuristicLlmProvider:
    name = "heuristic"

    def enrich(self, prompt: str, *, context: dict[str, Any] | None = None) -> str | None:
        return None

    def is_available(self) -> bool:
        return False
