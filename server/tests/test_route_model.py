"""_route_model 라우팅 회귀 테스트 (2026-08-03 회의 P0-S2).

수정 전 결함: character_id가 있으면(라우터에서 사실상 항상 채워짐) A/B variant
문자열을 그대로 모델 ID로 즉시 반환해 _classify_message_complexity가 아예
실행되지 않았다 — 캐릭터별 sha256 해시로 모델이 영구 고정되어 심층 상담도
mini로 갔고, "ㅇㅇ" 한 마디에도 상위 모델을 썼다.

수정 후 계약:
- 복잡도 분류는 character_id 유무와 무관하게 **항상** 실행되어 base 모델을 정한다
- A/B variant는 정책 오버레이 — always_complex면 상위 모델로 승격, 대조군은 그대로
- variant 배정이 실패하면 복잡도 라우팅 결과를 그대로 사용(안전 폴백)
"""

import pytest

from app import ab_test, chat_service
from app.ab_test import MODEL_ROUTING_ALWAYS_COMPLEX, MODEL_ROUTING_COMPLEXITY
from app.config import LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE

CHARACTER_ID = "char-routing-test"

# 복잡도 분류기가 complex/simple로 확실히 가르는 입력
COMPLEX_MESSAGE = "요즘 진짜 고민이 많아서 너무 힘들어... 어떻게 해야 할지 모르겠어"
SIMPLE_MESSAGE = "ㅇㅇ"


@pytest.fixture(autouse=True)
def _no_finetuned_model(monkeypatch):
    """파인튜닝 모델 우선 분기를 비활성화해 라우팅 경로만 검증한다."""
    monkeypatch.setattr(
        chat_service, "get_model_for_character", lambda character_id, *a, **kw: LLM_MODEL_COMPLEX
    )


def _force_variant(monkeypatch, variant):
    """assign_variant가 항상 지정 variant를 반환하도록 고정."""

    class _FakeManager:
        def assign_variant(self, user_id, experiment_id, character_id=""):
            assert experiment_id == ab_test.MODEL_ROUTING_EXPERIMENT_ID
            return variant

    monkeypatch.setattr(ab_test, "get_ab_manager", lambda: _FakeManager())


# ── 복잡도 분류가 실제로 반영되는가 (핵심 회귀) ──────────────────────────────

def test_complex_message_with_character_id_routes_to_complex_model(monkeypatch):
    _force_variant(monkeypatch, MODEL_ROUTING_COMPLEXITY)

    model_id, ab_variant = chat_service._route_model(CHARACTER_ID, COMPLEX_MESSAGE, 3)

    assert model_id == LLM_MODEL_COMPLEX
    assert ab_variant == MODEL_ROUTING_COMPLEXITY


def test_simple_message_with_character_id_routes_to_simple_model(monkeypatch):
    _force_variant(monkeypatch, MODEL_ROUTING_COMPLEXITY)

    model_id, ab_variant = chat_service._route_model(CHARACTER_ID, SIMPLE_MESSAGE, 0)

    assert model_id == LLM_MODEL_SIMPLE
    assert ab_variant == MODEL_ROUTING_COMPLEXITY


def test_variant_is_not_used_as_model_id(monkeypatch):
    """variant 문자열이 모델 ID로 새어나가지 않아야 한다(구 결함의 직접 원인)."""
    _force_variant(monkeypatch, MODEL_ROUTING_COMPLEXITY)

    for message in (COMPLEX_MESSAGE, SIMPLE_MESSAGE):
        model_id, _ = chat_service._route_model(CHARACTER_ID, message, 0)
        assert model_id in (LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE)
        assert model_id != MODEL_ROUTING_COMPLEXITY


# ── A/B 정책 오버레이 ────────────────────────────────────────────────────────

def test_always_complex_overlay_promotes_simple_message(monkeypatch):
    _force_variant(monkeypatch, MODEL_ROUTING_ALWAYS_COMPLEX)

    model_id, ab_variant, complexity = chat_service._route_model_with_complexity(
        CHARACTER_ID, SIMPLE_MESSAGE, 0
    )

    assert complexity == "simple"           # 분류기 판정 자체는 그대로 보존
    assert model_id == LLM_MODEL_COMPLEX    # 정책이 상위 모델로 승격
    assert ab_variant == MODEL_ROUTING_ALWAYS_COMPLEX


def test_always_complex_overlay_keeps_complex_message_on_complex_model(monkeypatch):
    _force_variant(monkeypatch, MODEL_ROUTING_ALWAYS_COMPLEX)

    model_id, _, complexity = chat_service._route_model_with_complexity(
        CHARACTER_ID, COMPLEX_MESSAGE, 3
    )

    assert complexity == "complex"
    assert model_id == LLM_MODEL_COMPLEX


def test_real_manager_control_assignment_still_routes_by_complexity():
    """실제 ABTestManager로도(모킹 없이) 대조군 캐릭터는 복잡도로 갈린다."""
    manager = ab_test.get_ab_manager()
    control_char = next(
        (
            f"char-{i}"
            for i in range(200)
            if manager.assign_variant(
                user_id=f"char-{i}", experiment_id=ab_test.MODEL_ROUTING_EXPERIMENT_ID
            )
            == MODEL_ROUTING_COMPLEXITY
        ),
        None,
    )
    assert control_char is not None, "대조군에 배정되는 character_id를 찾지 못함"

    assert chat_service._route_model(control_char, SIMPLE_MESSAGE, 0)[0] == LLM_MODEL_SIMPLE
    assert chat_service._route_model(control_char, COMPLEX_MESSAGE, 3)[0] == LLM_MODEL_COMPLEX


# ── 계측용 complexity 반환 ───────────────────────────────────────────────────

def test_complexity_returned_without_character_id():
    model_id, ab_variant, complexity = chat_service._route_model_with_complexity(
        "", COMPLEX_MESSAGE, 3
    )

    assert complexity == "complex"
    assert model_id == LLM_MODEL_COMPLEX
    assert ab_variant is None  # character_id 없으면 A/B 배정 없음


# ── 예외 폴백 ────────────────────────────────────────────────────────────────

def test_ab_failure_falls_back_to_complexity_routing(monkeypatch):
    def _boom():
        raise RuntimeError("ab manager down")

    monkeypatch.setattr(ab_test, "get_ab_manager", _boom)

    complex_model, complex_variant = chat_service._route_model(CHARACTER_ID, COMPLEX_MESSAGE, 3)
    simple_model, simple_variant = chat_service._route_model(CHARACTER_ID, SIMPLE_MESSAGE, 0)

    assert complex_model == LLM_MODEL_COMPLEX
    assert simple_model == LLM_MODEL_SIMPLE
    assert complex_variant is None and simple_variant is None


def test_finetuned_model_still_takes_priority(monkeypatch):
    monkeypatch.setattr(
        chat_service, "get_model_for_character", lambda character_id, *a, **kw: "ft:custom-model"
    )
    _force_variant(monkeypatch, MODEL_ROUTING_ALWAYS_COMPLEX)

    model_id, ab_variant, complexity = chat_service._route_model_with_complexity(
        CHARACTER_ID, SIMPLE_MESSAGE, 0
    )

    assert model_id == "ft:custom-model"
    assert ab_variant is None
    assert complexity == "simple"  # 계측용 분류는 파인튜닝 경로에서도 남는다
