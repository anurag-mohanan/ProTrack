"""OpenAI-compatible chat completions client with soft failure."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class OpenAiCompatLlmProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 12.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = (model or "gpt-4o-mini").strip()
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, prompt: str, *, context: dict[str, Any] | None = None) -> str | None:
        if not self.is_available():
            return None
        try:
            system = (
                "You are a concise operations assistant for an engineering services firm. "
                "Reply with one short sentence only. No markdown, no bullets."
            )
            if context:
                system += f" Context keys: {', '.join(sorted(context.keys())[:12])}."
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt[:4000]},
                ],
                "temperature": 0.2,
                "max_tokens": 120,
            }
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices") or []
            if not choices:
                return None
            content = (choices[0].get("message") or {}).get("content")
            if not isinstance(content, str):
                return None
            text = content.strip()
            return text[:500] if text else None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
            logger.info("LLM enrichment skipped: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — never break heuristic path
            logger.info("LLM enrichment unexpected failure: %s", exc)
            return None
