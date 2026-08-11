import pytest

from app import model_routing


def test_select_model_for_crisis_uses_configured_models():
    assert model_routing.select_model_for_crisis({"level": "none"}) == model_routing.LLM_MODEL_SIMPLE
    assert model_routing.select_model_for_crisis({"level": "tier1"}) == model_routing.LLM_MODEL_COMPLEX
    assert model_routing.select_model_for_crisis({"level": "tier2"}) == model_routing.LLM_MODEL_COMPLEX


@pytest.mark.asyncio
async def test_resolve_model_endpoint_returns_base_model_unchanged():
    """LoRA 서빙 경로 제거(2026-08-11, 소유자 결정) 후 resolve_model_endpoint는
    ab_variant 값과 무관하게 항상 base_model을 base_url 없이 그대로 반환한다.

    이전에는 ab_variant가 LoRA 모델 슬러그로 매핑되면 Together AI/vLLM
    엔드포인트를 반환했지만, ChatRequest에 ab_variant 필드 자체가 없어
    그 경로에는 어떤 요청도 도달할 수 없었다(2026-08-03 회의 S3-c 확정).
    """
    model_id, base_url = await model_routing.resolve_model_endpoint("gpt-4.1-mini", "")

    assert model_id == "gpt-4.1-mini"
    assert base_url == ""


@pytest.mark.asyncio
async def test_resolve_model_endpoint_ignores_legacy_lora_variant_names():
    """예전 LoRA 실험 variant 이름을 넘겨도 더 이상 특별 취급하지 않는다."""
    model_id, base_url = await model_routing.resolve_model_endpoint("gpt-4.1-mini", "lora_intj")

    assert model_id == "gpt-4.1-mini"
    assert base_url == ""


@pytest.mark.asyncio
async def test_resolve_model_endpoint_ignores_always_complex_variant():
    """model_routing 실험의 실 variant("always_complex")도 base_model을 바꾸지 않는다
    — 모델 승격은 chat_service._route_model_with_complexity가 별도로 처리한다."""
    model_id, base_url = await model_routing.resolve_model_endpoint("gpt-4.1", "always_complex")

    assert model_id == "gpt-4.1"
    assert base_url == ""
