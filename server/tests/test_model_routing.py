import inspect

import pytest

from app import model_routing


def test_select_model_for_crisis_uses_configured_models():
    assert model_routing.select_model_for_crisis({"level": "none"}) == model_routing.LLM_MODEL_SIMPLE
    assert model_routing.select_model_for_crisis({"level": "tier1"}) == model_routing.LLM_MODEL_COMPLEX
    assert model_routing.select_model_for_crisis({"level": "tier2"}) == model_routing.LLM_MODEL_COMPLEX


@pytest.mark.asyncio
async def test_resolve_model_endpoint_returns_base_model_for_non_lora(monkeypatch):
    monkeypatch.setattr(model_routing, "TOGETHER_API_KEY", "test-key")

    model_id, base_url = await model_routing.resolve_model_endpoint("gpt-4.1-mini", "")

    assert model_id == "gpt-4.1-mini"
    assert base_url == ""


@pytest.mark.asyncio
async def test_resolve_model_endpoint_maps_lora_variant_to_together(monkeypatch):
    async def fake_health():
        return False

    monkeypatch.setattr(model_routing, "TOGETHER_API_KEY", "test-key")
    monkeypatch.setattr(model_routing, "VLLM_BASE_URL", "")
    monkeypatch.setattr(model_routing, "check_vllm_health", fake_health)

    result = model_routing.resolve_model_endpoint("gpt-4.1-mini", "lora_intj")

    assert inspect.isawaitable(result)
    model_id, base_url = await result
    assert model_id == "mbtichatfriend/intj-lora-v1"
    assert base_url == "https://api.together.xyz/v1"


@pytest.mark.asyncio
async def test_resolve_model_endpoint_prefers_healthy_vllm(monkeypatch):
    async def fake_health():
        return True

    monkeypatch.setattr(model_routing, "TOGETHER_API_KEY", "test-key")
    monkeypatch.setattr(model_routing, "VLLM_BASE_URL", "http://vllm.local")
    monkeypatch.setattr(model_routing, "check_vllm_health", fake_health)

    model_id, base_url = await model_routing.resolve_model_endpoint("gpt-4.1-mini", "lora_intp_v1")

    assert model_id == "togetherai/mbtichat-intp-lora-v1"
    assert base_url == "http://vllm.local"
