"""Resolve the configured LLM provider (R5)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.ai.providers.base import LlmProvider
from app.services.ai.providers.heuristic import HeuristicLlmProvider
from app.services.ai.providers.openai_compat import OpenAiCompatLlmProvider


def build_llm_provider(
    *,
    provider_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> LlmProvider:
    from app.core import config

    name = (provider_name if provider_name is not None else config.AI_PROVIDER).strip().lower()
    key = api_key if api_key is not None else config.AI_API_KEY
    url = base_url if base_url is not None else config.AI_BASE_URL
    mdl = model if model is not None else config.AI_MODEL

    if name == "openai":
        provider = OpenAiCompatLlmProvider(api_key=key, base_url=url, model=mdl)
        if provider.is_available():
            return provider
        # Missing key → stay offline rather than pretending LLM mode works.
        return HeuristicLlmProvider()

    return HeuristicLlmProvider()


@lru_cache(maxsize=1)
def get_llm_provider() -> LlmProvider:
    return build_llm_provider()


def reset_llm_provider_cache() -> None:
    get_llm_provider.cache_clear()


def provider_status() -> dict[str, Any]:
    from app.core import config

    provider = get_llm_provider()
    configured = config.AI_PROVIDER.strip().lower()
    llm_available = provider.is_available() and configured == "openai"
    return {
        "provider": provider.name if llm_available else "heuristic",
        "configured_provider": configured,
        "model": config.AI_MODEL if llm_available else None,
        "llm_available": llm_available,
        "mode": "llm" if llm_available else "offline",
    }
