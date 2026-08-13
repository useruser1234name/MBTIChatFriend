"""파인튜닝 모델의 (owner_uid, character_id) 복합 키 스코프 회귀 테스트.

발견 결함(페르소나 배선 조사, 2026-08-13):
- Android의 character_id는 Room의 로컬 autoIncrement Long을 문자열화한
  값이라(`FinetuneRepository.kt`: `characterId = character.id.toString()`)
  전역 유니크가 아니다 — 서로 다른 사용자의 첫 캐릭터가 둘 다 "1"일 수 있다.
- finetune_service.get_model_for_character/activate_model은 이미
  (owner_uid, character_id) 복합 키로 설계돼 있었지만, 호출부(chat_service의
  모델 라우팅 체인, routers/finetune.py)가 owner_uid를 전달하지 않아
  - 등록된 파인튜닝 모델이 실제 채팅 경로에서 영원히 조회되지 않았고
    (get_model_for_character(character_id)만 호출 → scoped_key가 항상 "").
  - routers/finetune.py의 activate_model/prepare_and_start_finetune/
    check_finetune_status 호출은 필수 owner_uid 인자를 아예 넘기지 않아
    호출 시 TypeError로 즉시 500이 나는, 완전히 죽어있는 경로였다.

이 파일은 두 가지를 함께 확인한다:
1. finetune_service 자체의 복합 키가 서로 다른 owner를 올바르게 격리하는지.
2. routers/finetune.py가 이제 owner_uid를 인증 토큰에서 뽑아 올바르게 배선하는지.
"""

import pytest

from app import finetune_service
from app.config import LLM_MODEL_BASE
from app.models import FinetuneActivateRequest
from app.routers import finetune as finetune_router


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """실제 finetune_models.json을 건드리지 않도록 임시 파일/캐시로 격리."""
    monkeypatch.setattr(finetune_service, "_MODELS_FILE", str(tmp_path / "finetune_models.json"))
    monkeypatch.setattr(finetune_service, "_models_cache", None)
    monkeypatch.setattr(finetune_service, "_models_cache_mtime", 0.0)
    yield


# ── finetune_service: 복합 키 격리 ──────────────────────────────────────────

def test_same_character_id_different_owner_isolated():
    """character_id가 전역 유니크하지 않아도(두 사용자 모두 "1") 서로의
    파인튜닝 모델을 보면 안 된다."""
    finetune_service.activate_model("1", "ft:owner-a-model", "owner-a")
    finetune_service.activate_model("1", "ft:owner-b-model", "owner-b")

    assert finetune_service.get_model_for_character("1", "owner-a") == "ft:owner-a-model"
    assert finetune_service.get_model_for_character("1", "owner-b") == "ft:owner-b-model"


def test_missing_owner_uid_falls_back_to_base_model():
    """owner_uid를 넘기지 않으면(구 결함 상태와 동일) 등록된 모델이 있어도
    base로 안전하게 폴백한다 — 교차 사용자 오매칭이 아니라 기능 미적용이었음의
    회귀 확인."""
    finetune_service.activate_model("1", "ft:owner-a-model", "owner-a")

    assert finetune_service.get_model_for_character("1") == LLM_MODEL_BASE
    assert finetune_service.get_model_for_character("1", "") == LLM_MODEL_BASE


def test_activate_model_requires_owner_uid_positional():
    """activate_model은 owner_uid가 필수 인자다 — 호출부가 빠뜨리면 즉시
    TypeError가 나야 한다(routers/finetune.py가 이를 지키는지의 회귀 가드)."""
    with pytest.raises(TypeError):
        finetune_service.activate_model("1", "ft:x")  # type: ignore[call-arg]


# ── routers/finetune.py: owner_uid 배선 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_finetune_endpoint_wires_owner_uid_from_token():
    """/finetune/activate 호출이 더 이상 TypeError로 죽지 않고, 인증 토큰의
    uid로 스코프된다."""
    req = FinetuneActivateRequest(character_id="1", model_id="ft:custom-model")

    result = await finetune_router.activate_finetune(req, user={"uid": "user-a"})

    assert result["status"] == "ok"
    assert finetune_service.get_model_for_character("1", "user-a") == "ft:custom-model"
    # 다른 사용자에게는 새지 않는다
    assert finetune_service.get_model_for_character("1", "user-b") == LLM_MODEL_BASE


@pytest.mark.asyncio
async def test_activate_finetune_endpoint_no_token_does_not_crash():
    """REQUIRE_AUTH=false 개발 우회 경로(user=None)에서도 TypeError 없이
    동작해야 한다. 빈 owner_uid는 조회 시에도 항상 미스하도록 설계돼 있어
    (get_model_for_character의 `if owner_uid` 가드) 활성화는 성공하지만
    조회는 base 모델로 안전 폴백된다 — 크래시하지 않는 것 자체가 회귀 대상."""
    req = FinetuneActivateRequest(character_id="2", model_id="ft:dev-model")

    result = await finetune_router.activate_finetune(req, user=None)

    assert result["status"] == "ok"
    assert finetune_service.get_model_for_character("2", "") == LLM_MODEL_BASE
