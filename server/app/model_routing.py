"""Model routing helpers for chat generation and streaming."""

from __future__ import annotations

import logging

from .config import LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE

logger = logging.getLogger(__name__)


def select_model_for_crisis(crisis_result: dict) -> str:
    """Select the configured OpenAI model for crisis-aware routing."""
    level = crisis_result.get("level", "none")
    if level in ("tier1", "tier2", 1, 2):
        return LLM_MODEL_COMPLEX
    return LLM_MODEL_SIMPLE


async def resolve_model_endpoint(base_model: str, ab_variant: str) -> tuple[str, str]:
    """Resolve an OpenAI-compatible model id and optional base URL.

    Returns (model_id, base_url). Empty base_url means the default OpenAI
    endpoint should be used.

    2026-08-11(소유자 결정, LoRA 사문 코드 제거): 이 함수는 원래 ab_variant를
    LoRA 모델 슬러그로 매핑해 Together AI/vLLM 엔드포인트로 라우팅했다. 그러나
    ChatRequest에 ab_variant 필드 자체가 없어(2026-08-03 회의 S3-c 확정) 그
    경로에는 어떤 요청도 도달할 수 없었다 — 실험 정의 16종, 매핑 7종이 전부
    죽은 코드였다. 함수 계약(호출부 시그니처)은 유지하되, 이제는 base_model을
    base_url 없이 그대로 반환한다. 복구는 git 이력으로 가능하다.
    """
    return base_model, ""
