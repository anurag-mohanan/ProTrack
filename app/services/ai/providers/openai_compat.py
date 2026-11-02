"""OpenAI-compatible chat completions client with soft failure."""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class LlmProviderError(Exception):
    """Provider call failed. ``kind`` is safe to show; the message never contains the key."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind  # timeout | auth | rate_limited | unavailable | bad_response


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
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            logger.info("LLM enrichment skipped: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — never break heuristic path
            logger.info("LLM enrichment unexpected failure: %s", exc)
            return None

    def chat_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """One chat-completions call with function tools. Returns content, tool_calls, usage, model."""
        if not self.is_available():
            raise LlmProviderError("unavailable", "The AI provider is not configured.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, default=str).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise LlmProviderError("auth", "The AI provider rejected the credentials.") from None
            if exc.code == 429:
                raise LlmProviderError("rate_limited", "The AI provider is rate limiting requests.") from None
            raise LlmProviderError("unavailable", f"The AI provider returned HTTP {exc.code}.") from None
        except (TimeoutError, OSError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise LlmProviderError("timeout", "The AI provider did not respond in time.") from None
            raise LlmProviderError("unavailable", "The AI provider could not be reached.") from None
        except (json.JSONDecodeError, ValueError):
            raise LlmProviderError("bad_response", "The AI provider returned an unreadable response.") from None
        choices = body.get("choices") if isinstance(body, dict) else None
        if not choices:
            raise LlmProviderError("bad_response", "The AI provider returned no answer.")
        message = choices[0].get("message") or {}
        calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            calls.append({"id": call.get("id") or "", "name": function.get("name") or "", "arguments": function.get("arguments") or "{}"})
        usage = body.get("usage") or {}
        return {
            "content": message.get("content") if isinstance(message.get("content"), str) else None,
            "tool_calls": calls,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            },
            "model": body.get("model") or self.model,
        }

    def analyze_document_json(
        self,
        *,
        system: str,
        kind: str,
        native_text: str,
        page_images_png: list[bytes],
        filename: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        """Multimodal structured extraction. Soft-fail → None."""
        if not self.is_available():
            return None
        schema_hint = (
            "Return JSON with keys: document_type (QUOTE|INVOICE|UNKNOWN), document, project, "
            "customer, purchase, commercial, work_breakdown, terms, warnings. "
            "document has invoice_number/quote_number, dates, currency, sales_person. "
            "project has customer_project_number. customer has name, attention/billing_attention, address. "
            "purchase has po_number. commercial has line_items, subtotal, tax, total, balance_due. "
            "work_breakdown is [{stage, hours}]. terms has payment_terms, notes."
        )
        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"Document kind hint: {kind}\nFilename: {filename or ''}\n"
                    f"{schema_hint}\n\nNative PDF text:\n{native_text[:6000]}"
                ),
            }
        ]
        for png in page_images_png[:2]:
            b64 = base64.b64encode(png).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0,
            "max_tokens": 2500,
            "response_format": {"type": "json_object"},
        }
        timeout = (
            timeout_seconds if timeout_seconds is not None else max(self.timeout_seconds, 45.0)
        )
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices") or []
            if not choices:
                return None
            content = (choices[0].get("message") or {}).get("content")
            if not isinstance(content, str):
                return None
            text = content.strip()
            fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if fence:
                text = fence.group(1).strip()
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.info("Document vision JSON analysis skipped: %s", exc)
            return None
