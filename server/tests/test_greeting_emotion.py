"""C2: 첫인사 감정 부여 테스트.

get_greeting_emotion(app/mbti.py)의 순수 매핑 로직과, /chat/greeting
엔드포인트(routers/chat.py:send_greeting) 응답에 emotion 필드가 additive로
포함되는지 검증한다.
"""

import pytest

from app.mbti import GREETING_EMOTION_MAP, get_greeting_emotion
from app.models import VALID_EMOTIONS


def test_greeting_emotion_map_covers_all_16_mbti_types():
    mbti_16 = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    ]
    assert set(GREETING_EMOTION_MAP.keys()) == set(mbti_16)
    # 매핑값은 반드시 서버가 인식하는 유효 감정 코드여야 한다.
    assert set(GREETING_EMOTION_MAP.values()) <= VALID_EMOTIONS


@pytest.mark.parametrize("mbti,expected", [
    ("ENFP", "PLAYFUL"), ("ESFP", "PLAYFUL"), ("ESTP", "PLAYFUL"), ("ENTP", "PLAYFUL"),
    ("ENFJ", "HAPPY"), ("ESFJ", "HAPPY"), ("ENTJ", "HAPPY"), ("ESTJ", "HAPPY"),
    ("INFP", "SHY"), ("ISFP", "SHY"), ("INFJ", "SHY"), ("ISFJ", "SHY"),
    ("INTJ", "NEUTRAL"), ("INTP", "NEUTRAL"), ("ISTJ", "NEUTRAL"), ("ISTP", "NEUTRAL"),
])
def test_get_greeting_emotion_fixed_mapping(mbti, expected):
    assert get_greeting_emotion(mbti) == expected


def test_get_greeting_emotion_case_insensitive():
    assert get_greeting_emotion("enfp") == "PLAYFUL"
    assert get_greeting_emotion("IntJ") == "NEUTRAL"


def test_get_greeting_emotion_falls_back_to_neutral_for_invalid_input():
    assert get_greeting_emotion("") == "NEUTRAL"
    assert get_greeting_emotion("XXXX") == "NEUTRAL"
    assert get_greeting_emotion(None) == "NEUTRAL"


@pytest.mark.asyncio
async def test_send_greeting_response_includes_emotion_no_api_key(monkeypatch):
    """API 키 없음(mock 인사) 분기에서도 emotion 필드가 채워져야 한다."""
    from app.routers import chat as chat_router

    # slowapi @limiter.limit 데코레이터를 무력화 — 비활성화 시 request를
    # 전혀 검사하지 않으므로 직접 호출 테스트에서 실제 Request 없이 안전하다.
    monkeypatch.setattr(chat_router.limiter, "enabled", False)
    monkeypatch.setattr(chat_router, "OPENAI_API_KEY", "")

    resp = await chat_router.send_greeting(
        request=None, character_mbti="enfp", user={"uid": "test-uid"}
    )

    assert resp["character_mbti"] == "ENFP"
    assert resp["emotion"] == "PLAYFUL"
    assert "greeting" in resp and resp["greeting"]
    # additive 확인: 기존 필드가 그대로 남아있어야 한다
    assert set(resp.keys()) >= {"greeting", "character_mbti", "emotion"}


@pytest.mark.asyncio
async def test_send_greeting_response_emotion_neutral_group_no_api_key(monkeypatch):
    from app.routers import chat as chat_router

    monkeypatch.setattr(chat_router.limiter, "enabled", False)
    monkeypatch.setattr(chat_router, "OPENAI_API_KEY", "")

    resp = await chat_router.send_greeting(
        request=None, character_mbti="INTJ", user=None
    )

    assert resp["character_mbti"] == "INTJ"
    assert resp["emotion"] == "NEUTRAL"


@pytest.mark.asyncio
async def test_send_greeting_response_includes_emotion_with_llm_success(monkeypatch):
    """LLM 호출 성공 분기(응답 텍스트 커스텀)에서도 emotion 필드가 채워져야 한다."""
    import types

    from app.routers import chat as chat_router

    monkeypatch.setattr(chat_router.limiter, "enabled", False)
    monkeypatch.setattr(chat_router, "OPENAI_API_KEY", "fake-key-for-test")

    class _FakeMessage:
        content = "안녕하세요! 반가워요~"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        async def create(self, **kwargs):
            return _FakeResponse()

    class _FakeAsyncOpenAI:
        def __init__(self, *a, **k):
            self.chat = types.SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(chat_router.openai, "AsyncOpenAI", _FakeAsyncOpenAI)

    resp = await chat_router.send_greeting(
        request=None, character_mbti="ENFJ", user={"uid": "test-uid"}
    )

    assert resp["character_mbti"] == "ENFJ"
    assert resp["emotion"] == "HAPPY"
    assert resp["greeting"] == "안녕하세요! 반가워요~"


def test_send_greeting_http_contract_accepts_android_body(monkeypatch):
    """2026-08-13 QA 회귀 방지: 안드로이드가 보내는 실제 바디 형태
    {"character_mbti": ..., "character_name": ...}가 HTTP 레벨에서 422 없이
    수용되는지 검증한다. (기존 테스트는 send_greeting을 직접 호출해 FastAPI
    바디 파싱을 우회했고, embed 누락으로 라이브에서 항상 422였다.)
    """
    from fastapi.testclient import TestClient

    from app import chat_service
    from app.main import app

    monkeypatch.setattr(chat_service, "OPENAI_API_KEY", "", raising=False)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat/greeting",
        json={"character_mbti": "INFP", "character_name": "미루"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["greeting"]
    assert data["character_mbti"] == "INFP"
