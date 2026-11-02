"""Provider selection for the assistant. Returns None when no provider is configured.

Configuration is read from the environment (``AI_PROVIDER``, ``AI_API_KEY``, ``AI_BASE_URL``,
``AI_MODEL`` and the ``AI_*`` limits in ``app.core.config``). The status payload names the
provider and model only: never the key, and never the endpoint URL.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.services.ai.providers.openai_compat import LlmProviderError, OpenAiCompatLlmProvider

__all__ = ["ChatProvider", "LlmProviderError", "get_chat_provider", "provider_status", "set_provider_override"]


class ChatProvider(Protocol):
    name: str
    model: str

    def chat_with_tools(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: float,
        max_tokens: int, timeout_seconds: float,
    ) -> dict[str, Any]: ...


_override: ChatProvider | None = None


def set_provider_override(provider: ChatProvider | None) -> None:
    """Tests install a scripted provider here; production never calls this."""
    global _override
    _override = provider


def get_chat_provider() -> ChatProvider | None:
    from app.core import config

    if not config.AI_ASSISTANT_ENABLED:
        return None
    if _override is not None:
        return _override
    if config.AI_PROVIDER == "openai" and config.AI_API_KEY:
        return OpenAiCompatLlmProvider(api_key=config.AI_API_KEY, base_url=config.AI_BASE_URL, model=config.AI_MODEL,
                                       timeout_seconds=float(config.AI_TIMEOUT_SECONDS))
    return None


def provider_status() -> dict[str, Any]:
    from app.core import config

    if not config.AI_ASSISTANT_ENABLED:
        return {"enabled": False, "configured": False, "mode": "disabled", "provider": None, "model": None,
                "message": "The assistant has been switched off by an administrator (AI_ASSISTANT_ENABLED=false)."}
    provider = get_chat_provider()
    if provider is None:
        return {
            "enabled": True, "configured": False, "mode": "offline", "provider": None, "model": None,
            "message": (
                "No AI provider is configured, so the assistant cannot answer free-text questions. Suggested questions "
                "still show ProTrack data directly. An administrator can enable answers by setting AI_PROVIDER=openai, "
                "AI_API_KEY and optionally AI_BASE_URL and AI_MODEL in the server environment."
            ),
        }
    return {"enabled": True, "configured": True, "mode": "llm", "provider": provider.name, "model": provider.model,
            "message": None}


def generation_settings() -> dict[str, Any]:
    from app.core import config

    return {"temperature": config.AI_TEMPERATURE, "max_tokens": config.AI_MAX_TOKENS,
            "timeout_seconds": float(config.AI_TIMEOUT_SECONDS), "max_tool_rounds": config.AI_MAX_TOOL_ROUNDS}
