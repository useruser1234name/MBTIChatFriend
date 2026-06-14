"""generate_reply LLM 경로 회귀 테스트.

배경: chat_service.py에서 async인 _resolve_model을 await 없이 호출하면
coroutine 언패킹 TypeError가 발생하고, generate_reply의 외부 except가 이를
삼켜 모든 사용자가 고정 폴백("앗, 잠깐 멍해졌어요...")만 받게 된다.
이 경로를 타는 테스트가 없어 152 passed로도 가려져 있었다.

이 테스트는 OpenAI 클라이언트를 mock하여 generate_reply가 폴백이 아닌
정상 LLM 응답을 반환하는지 검증한다. await 누락이 재발하면 실패한다.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app import chat_service
from app.chat_service import generate_reply
from app.models import HistoryMessage

# generate_reply가 LLM 호출 실패 시 반환하는 고정 폴백 문구들
ERROR_FALLBACK = "앗, 잠깐 멍해졌어요"
FILTERED_FALLBACK = "음... 뭐라고 말해야 할지 모르겠어요"


def _make_openai_response(content: str):
    """OpenAI chat.completions.create 응답 객체 모킹."""
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 20
    resp.usage.prompt_tokens_details.cached_tokens = 0
    return resp


def _make_mock_client(content: str):
    """create가 항상 주어진 content를 반환하는 AsyncOpenAI mock."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(content)
    )
    return client


def test_generate_reply_returns_llm_response_not_fallback():
    """정상 mock 클라이언트 주입 시 폴백이 아닌 실제 응답을 반환해야 한다.

    _resolve_model await 누락(회귀) 시 이 테스트는 ERROR_FALLBACK을 받아 실패한다.
    """
    valid_reply = '[{"text": "안녕! 반가워", "emotion": "HAPPY"}]'
    mock_client = _make_mock_client(valid_reply)

    # 모듈 전역 client를 mock으로 교체 (character_name 비워 DB 의존 제거)
    with patch.object(chat_service, "client", mock_client):
        replies, _delta = asyncio.run(
            generate_reply(
                message="안녕!",
                mbti="ENFP",
                speech_style="반말",
                relationship="친구",
                nickname="민수",
                affinity_level=1,
                conversation_history=[],
                character_name="",   # DB 조회(build_memory_context) 건너뛰기
                character_id="",      # 복잡도 라우팅 경로
            )
        )

    assert replies, "replies가 비어 있으면 안 된다"
    joined = " ".join(r.text for r in replies)
    assert ERROR_FALLBACK not in joined, (
        f"LLM 에러 폴백이 반환됨 — _resolve_model await 누락 회귀 의심: {joined}"
    )
    assert FILTERED_FALLBACK not in joined, f"전체 필터 폴백 반환됨: {joined}"
    assert "안녕! 반가워" in joined, f"mock 응답 텍스트가 반영되지 않음: {joined}"


def test_generate_reply_10turn_memory_extraction_path():
    """10턴(history 길이 10) 경로에서 _background_memory_extraction이 실제로 스케줄된다.

    단순히 폴백이 아닌지(=NameError 미발생)만 보는 것을 넘어, 추출 함수가 정확한
    인자로 호출되었는지까지 검증한다. character_name+nickname+history>=10이 발동 조건.
    create_tracked_task(fire-and-forget)이라 호출 자체를 spy로 확인한다.
    """
    valid_reply = '[{"text": "오늘 얘기 재밌었어", "emotion": "HAPPY"}]'
    mock_client = _make_mock_client(valid_reply)
    history = [
        HistoryMessage(role=("user" if i % 2 == 0 else "assistant"), content=f"메시지{i}")
        for i in range(10)
    ]

    spy = AsyncMock()  # _background_memory_extraction 대체 — 호출 인자 캡처
    with patch.object(chat_service, "client", mock_client), \
         patch.object(chat_service, "_background_memory_extraction", spy):
        replies, _delta = asyncio.run(
            generate_reply(
                message="오늘 하루 어땠어?",
                mbti="ENFP",
                speech_style="반말",
                relationship="친구",
                nickname="민수",
                affinity_level=2,
                conversation_history=history,
                character_name="하늘",   # +nickname+history → 메모리 추출 경로 진입
                character_id="char_1",
                room_id="room_1",
            )
        )

    assert replies, "replies가 비어 있으면 안 된다"
    joined = " ".join(r.text for r in replies)
    assert ERROR_FALLBACK not in joined, (
        f"10턴 메모리 추출 경로에서 폴백 반환 — _background_memory_extraction 회귀 의심: {joined}"
    )
    # 10턴 발동 조건이 실제로 메모리 추출을 스케줄했는지 검증 (조건 회귀 방지)
    spy.assert_called_once()
    args = spy.call_args.args
    assert args[0] == "하늘", f"character_name 전달 오류: {args}"
    assert args[3] == "char_1", f"character_id 전달 오류: {args}"
    assert args[4] == "room_1", f"room_id 전달 오류: {args}"


def test_background_memory_extraction_invokes_all_three(monkeypatch):
    """_background_memory_extraction이 요약·팩트·에피소드 추출을 모두 await하는지 검증.

    본문이 no-op로 회귀하면(과거 mutation 2b: 함수는 정의됐지만 본문이 비어도
    통과하던 허점) 이 테스트가 잡는다. 시그니처 정합(keyword vs positional)도 확인.
    """
    summ, facts, episodes = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(chat_service, "summarize_conversation", summ)
    monkeypatch.setattr(chat_service, "extract_facts", facts)
    monkeypatch.setattr(chat_service, "extract_episodes", episodes)

    history = [HistoryMessage(role="user", content="안녕")]
    asyncio.run(
        chat_service._background_memory_extraction(
            "하늘", "민수", history, "char_1", "room_1"
        )
    )

    summ.assert_awaited_once()
    facts.assert_awaited_once()
    episodes.assert_awaited_once()
    # summarize/facts: room_id·character_id는 keyword-only
    assert summ.await_args.kwargs.get("room_id") == "room_1"
    assert summ.await_args.kwargs.get("character_id") == "char_1"
    assert facts.await_args.kwargs.get("room_id") == "room_1"
    # extract_episodes: character_id, room_id는 positional (인덱스 3,4)
    assert episodes.await_args.args[3] == "char_1"
    assert episodes.await_args.args[4] == "room_1"


def test_generate_reply_no_client_returns_mock():
    """client가 None(API 키 없음)이면 _mock_reply 분기를 타 목업 응답을 반환한다.

    NOTE: 이 테스트는 await 회귀가 아니라 'client 미설정 시 목업 폴백' 분기를 보장한다
    (client=None이면 _resolve_model 경로 이전에 반환됨). await 회귀는 위 두 테스트가 담당.
    """
    with patch.object(chat_service, "client", None):
        replies, _delta = asyncio.run(
            generate_reply(
                message="안녕!",
                mbti="INFP",
                speech_style="반말",
                relationship="친구",
                nickname="민수",
                affinity_level=1,
                conversation_history=[],
                character_name="",
                character_id="",
            )
        )
    assert replies, "목업 응답이 비어 있으면 안 된다"
    joined = " ".join(r.text for r in replies)
    assert ERROR_FALLBACK not in joined, f"목업 경로에서 에러 폴백이 나옴: {joined}"
    assert FILTERED_FALLBACK not in joined, f"목업 경로에서 필터 폴백이 나옴: {joined}"
    assert joined.strip(), "목업 응답 텍스트가 비어 있음"
    # 모든 ReplyPart가 유효한 emotion 코드를 갖는지(목업 구조 보장)
    assert all(r.emotion for r in replies), "목업 응답에 emotion 누락"
