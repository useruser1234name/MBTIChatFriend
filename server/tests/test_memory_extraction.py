"""기억 추출 트리거/함수 회귀 테스트.

배경: _background_memory_extraction 정의가 유실되어 10턴마다 NameError →
에러 폴백이 나고 요약/팩트/에피소드가 전혀 갱신되지 않던 버그. 또한 트리거가
트림된 히스토리 길이를 검사해 10턴 이후 매턴 발동하던 버그. 아래 테스트가 재발을 막는다.
"""

import pytest

from app import chat_service


def test_should_extract_memory_only_at_intervals():
    assert not chat_service._should_extract_memory(0)
    assert not chat_service._should_extract_memory(4)
    assert not chat_service._should_extract_memory(8)
    assert chat_service._should_extract_memory(10)
    # 트림 길이(항상 10)로 판정하면 매턴 True가 되던 버그 방지: 원본 11은 False
    assert not chat_service._should_extract_memory(11)
    assert not chat_service._should_extract_memory(15)
    assert chat_service._should_extract_memory(20)
    assert chat_service._should_extract_memory(30)


def test_background_memory_extraction_is_defined():
    # 유실 회귀 방지: 반드시 존재해야 함
    assert hasattr(chat_service, "_background_memory_extraction")


@pytest.mark.asyncio
async def test_background_memory_extraction_runs_all_stages(monkeypatch):
    calls = []

    async def fake_summary(*a, **k):
        calls.append("summary")

    async def fake_facts(*a, **k):
        calls.append("facts")

    async def fake_episodes(*a, **k):
        calls.append("episodes")

    monkeypatch.setattr(chat_service, "summarize_conversation", fake_summary)
    monkeypatch.setattr(chat_service, "extract_facts", fake_facts)
    monkeypatch.setattr(chat_service, "extract_episodes", fake_episodes)

    await chat_service._background_memory_extraction("캐릭터", "유저", [], "cid", "rid")

    assert calls == ["summary", "facts", "episodes"]


@pytest.mark.asyncio
async def test_background_memory_extraction_survives_stage_failure(monkeypatch):
    calls = []

    async def boom(*a, **k):
        raise RuntimeError("summary down")

    async def fake_facts(*a, **k):
        calls.append("facts")

    async def fake_episodes(*a, **k):
        calls.append("episodes")

    monkeypatch.setattr(chat_service, "summarize_conversation", boom)
    monkeypatch.setattr(chat_service, "extract_facts", fake_facts)
    monkeypatch.setattr(chat_service, "extract_episodes", fake_episodes)

    # 한 단계 실패해도 예외를 밖으로 던지지 않고 나머지 단계 진행
    await chat_service._background_memory_extraction("캐릭터", "유저", [], "cid", "rid")

    assert calls == ["facts", "episodes"]
