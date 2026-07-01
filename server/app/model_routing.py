"""Model routing helpers for chat generation and streaming."""

from __future__ import annotations

import logging

import httpx

from .config import LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE, TOGETHER_API_KEY, VLLM_BASE_URL

logger = logging.getLogger(__name__)


TOGETHER_LORA_MODELS: dict[str, str] = {
    "lora-enfp-v2": "mbtichatfriend/enfp-lora-v2",
    "lora-infj-v1": "mbtichatfriend/infj-lora-v1",
    "lora-intj-v1": "mbtichatfriend/intj-lora-v1",
    "lora-isfj-v1": "mbtichatfriend/isfj-lora-v1",
    "lora-infp-v1": "mbtichatfriend/infp-lora-v1",
    "lora-entp-v1": "mbtichatfriend/entp-lora-v1",
    "lora_estj": "togetherai/mbtichat-estj-lora-v1",
    "lora_isfp": "togetherai/mbtichat-isfp-lora-v1",
    "lora_intp": "togetherai/mbtichat-intp-lora-v1",
}

AB_VARIANT_TO_LORA_KEY: dict[str, str] = {
    "lora_intj": "lora-intj-v1",
    "lora_isfj": "lora-isfj-v1",
    "lora_infp": "lora-infp-v1",
    "lora_entp": "lora-entp-v1",
    "lora_estj_v1": "lora_estj",
    "lora_isfp_v1": "lora_isfp",
    "lora_intp_v1": "lora_intp",
}


def select_model_for_crisis(crisis_result: dict) -> str:
    """Select the configured OpenAI model for crisis-aware routing."""
    level = crisis_result.get("level", "none")
    if level in ("tier1", "tier2", 1, 2):
        return LLM_MODEL_COMPLEX
    return LLM_MODEL_SIMPLE


async def check_vllm_health() -> bool:
    """Return whether the configured vLLM endpoint is ready."""
    if not VLLM_BASE_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{VLLM_BASE_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def resolve_model_endpoint(base_model: str, ab_variant: str) -> tuple[str, str]:
    """Resolve an OpenAI-compatible model id and optional base URL.

    Returns (model_id, base_url). Empty base_url means the default OpenAI
    endpoint should be used.
    """
    resolved_variant = AB_VARIANT_TO_LORA_KEY.get(ab_variant, ab_variant)
    if resolved_variant in TOGETHER_LORA_MODELS and TOGETHER_API_KEY:
        lora_model_id = TOGETHER_LORA_MODELS[resolved_variant]
        if VLLM_BASE_URL and await check_vllm_health():
            logger.info("[ModelRouting] vLLM health check passed: %s", VLLM_BASE_URL)
            return lora_model_id, VLLM_BASE_URL
        logger.info("[ModelRouting] vLLM unavailable; falling back to Together AI")
        return lora_model_id, "https://api.together.xyz/v1"
    return base_model, ""
