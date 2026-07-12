"""C4: 시간대 인지 프롬프트 테스트.

routers/chat.py의 build_time_context(hour→구간 매핑)와, 그 결과가
build_system_prompt의 동적 꼬리(정적 프리픽스 뒤)에만 삽입되는지 검증한다.
"""

import pytest

from app.prompts import build_system_prompt
from app.routers.chat import build_time_context


@pytest.mark.parametrize("hour,expected_label", [
    (5, "아침"), (8, "아침"), (10, "아침"),
    (11, "낮"), (14, "낮"), (16, "낮"),
    (17, "저녁"), (19, "저녁"), (21, "저녁"),
    (22, "밤"), (23, "밤"), (0, "밤"), (3, "밤"), (4, "밤"),
])
def test_build_time_context_hour_bucket_mapping(hour, expected_label):
    result = build_time_context(hour)
    assert f"{expected_label}이다" in result
    assert result.startswith("[현재 시간대:")


def test_build_time_context_none_hour_returns_empty_string():
    assert build_time_context(None) == ""


def test_time_context_included_when_hour_given_and_positioned_after_static_prefix():
    """3단언: hour=8 → "아침" 포함 / hour=None → 시간 블록 없음 / 시간 블록이
    정적 프리픽스(prefix caching 대상) 뒤 동적 꼬리에 위치."""
    base_kwargs = dict(
        mbti="ENFP",
        speech_style="CASUAL",
        relationship="FRIEND",
        nickname="유저",
    )

    # 1) hour=8(아침 구간) → 프롬프트 본문에 "아침"이 포함되어야 한다
    morning_prompt = build_system_prompt(**base_kwargs, time_context=build_time_context(8))
    assert "아침" in morning_prompt
    assert "[현재 시간대: 아침이다. 자연스럽게 반영하되 매번 언급하지는 마라.]" in morning_prompt

    # 2) hour=None → 시간 블록 자체가 삽입되지 않아야 한다(기존 동작과 동일)
    no_hour_prompt = build_system_prompt(**base_kwargs, time_context=build_time_context(None))
    assert "[현재 시간대" not in no_hour_prompt
    # "아침"은 prompts.py 정적 페르소나 텍스트 어디에도 등장하지 않으므로
    # (grep으로 확인) 여기 있다면 시간 블록이 새어 들어간 것 — 회귀 감지용.
    assert "아침" not in no_hour_prompt

    # 3) 시간 블록은 정적 프리픽스(캐싱 대상: 역할/출력형식/성격/말투/감정/습관/
    # 자기설명 금지/행동 처리) 뒤, 동적 꼬리(표현 규칙 헤더 직전)에 위치해야 한다.
    static_marker_idx = morning_prompt.index("# 행동 처리 (역할극)")
    time_idx = morning_prompt.index("[현재 시간대")
    expression_rule_idx = morning_prompt.index("# 표현 규칙")
    assert static_marker_idx < time_idx < expression_rule_idx


def test_time_context_does_not_change_static_prefix_when_absent():
    """time_context 유무와 무관하게 정적 프리픽스(역할~행동 처리)는 바이트 동일해야 한다."""
    base_kwargs = dict(
        mbti="INTJ",
        speech_style="CASUAL",
        relationship="FRIEND",
        nickname="유저",
    )
    with_time = build_system_prompt(**base_kwargs, time_context=build_time_context(14))
    without_time = build_system_prompt(**base_kwargs)

    static_prefix_end_marker = "# 행동 처리 (역할극)"
    # 두 결과 모두에서 정적 마커까지의 prefix를 잘라 비교
    prefix_with = with_time[:with_time.index(static_prefix_end_marker)]
    prefix_without = without_time[:without_time.index(static_prefix_end_marker)]
    assert prefix_with == prefix_without
