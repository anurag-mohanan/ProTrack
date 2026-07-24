"""Tests for the AI & Analytics framework + R5 LLM provider foundation."""

from app.services.ai.base import confidence_from_sample_size
from app.services.ai.engine import ai_engine
from app.services.ai.providers import (
    build_llm_provider,
    provider_status,
    reset_llm_provider_cache,
)
from app.services.ai.providers.heuristic import HeuristicLlmProvider
from app.services.ai.providers.openai_compat import OpenAiCompatLlmProvider
from tests.conftest import login


def test_confidence_from_sample_size():
    assert confidence_from_sample_size(0) == 55.0
    assert confidence_from_sample_size(3) == 79.0
    assert confidence_from_sample_size(10) == 95.0


def test_ai_engine_registers_modules():
    assert "dashboard_insights" in ai_engine._modules
    assert "morning_brief" in ai_engine._modules
    assert "quoting_assistant" in ai_engine._modules
    assert "chat_assistant" in ai_engine._modules
    assert "report_insights" in ai_engine._modules


def test_dashboard_insights_api(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/ai/insights", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_llm_provider_defaults_to_heuristic():
    reset_llm_provider_cache()
    provider = build_llm_provider(provider_name="heuristic", api_key="")
    assert isinstance(provider, HeuristicLlmProvider)
    assert provider.enrich("hello") is None
    assert provider.is_available() is False


def test_openai_without_key_falls_back_to_heuristic():
    reset_llm_provider_cache()
    provider = build_llm_provider(provider_name="openai", api_key="")
    assert isinstance(provider, HeuristicLlmProvider)


def test_openai_with_key_selects_compat_provider():
    reset_llm_provider_cache()
    provider = build_llm_provider(
        provider_name="openai",
        api_key="sk-test",
        model="gpt-test",
    )
    assert isinstance(provider, OpenAiCompatLlmProvider)
    assert provider.is_available() is True


def test_provider_status_api_offline(client):
    reset_llm_provider_cache()
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/ai/provider", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "offline"
    assert body["llm_available"] is False
    assert body["provider"] == "heuristic"


def test_provider_status_helper_openai_without_key(monkeypatch):
    reset_llm_provider_cache()
    monkeypatch.setattr("app.core.config.AI_PROVIDER", "openai")
    monkeypatch.setattr("app.core.config.AI_API_KEY", "")
    reset_llm_provider_cache()
    status = provider_status()
    assert status["mode"] == "offline"
    assert status["llm_available"] is False
    assert status["configured_provider"] == "openai"
