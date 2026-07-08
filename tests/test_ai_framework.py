"""Tests for the AI & Analytics framework."""

from app.services.ai.base import confidence_from_sample_size
from app.services.ai.engine import ai_engine
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


def test_dashboard_insights_api(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/ai/insights", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
