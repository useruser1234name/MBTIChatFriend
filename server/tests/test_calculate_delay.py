"""`_calculate_delay` 유닛테스트 — R7: 딜레이 지터 + 감정 가중치.

계약 (docs/MEETING_2026-08-03_model_perf_chat_realism.md R7):
- base = 텍스트 길이 기반 (<=5자 800ms, <=20자 1200ms, 이후 length*60+500 max 3000ms)
- ±15% 랜덤 지터: base * uniform(0.85, 1.15)
- 감정 가중치: SURPRISED/ANGRY 0.85배, WORRIED/SAD 1.2배, 그 외 1.0배
- 첫 버블(is_first_bubble=True)은 +300~500ms 가산
- 최종 결과는 [300ms, 3500ms] 범위로 clamp
- 서버는 sleep 하지 않는다 (delay는 메타데이터로만 전송, 클라이언트가 적용)
"""

import random

import pytest

from app.chat_service import (
    _calculate_delay,
    _DELAY_MAX_MS,
    _DELAY_MIN_MS,
    _EMOTION_DELAY_MULTIPLIER,
    _parse_reply,
    IncrementalReplyParser,
)


LONG_TEXT = "가" * 30  # length=30 → base = min(30*60+500, 3000) = 2300


# ── 1. 지터 범위 (반복 실행 시 ±15% 안에 분포) ──────────────────────────


def test_jitter_stays_within_15_percent_of_base_for_short_text():
    """5자 이하 텍스트: base=800, jitter 범위 [680, 920]."""
    text = "응"
    samples = [_calculate_delay(text) for _ in range(500)]
    assert min(samples) >= 800 * 0.85 - 1  # 반올림 여유
    assert max(samples) <= 800 * 1.15 + 1
    # 실제로 여러 값이 나와야 함 (순수 상수가 아님을 증명)
    assert len(set(samples)) > 1


def test_jitter_stays_within_15_percent_of_base_for_long_text():
    """긴 텍스트: base=min(len*60+500, 3000)."""
    base = min(len(LONG_TEXT) * 60 + 500, 3000)
    samples = [_calculate_delay(LONG_TEXT) for _ in range(500)]
    assert min(samples) >= base * 0.85 - 1
    assert max(samples) <= base * 1.15 + 1
    assert len(set(samples)) > 1


def test_repeated_calls_on_identical_text_vary():
    """동일 문장을 5회 호출해도 지터로 인해 delay가 매번 달라질 수 있어야 한다."""
    text = "오늘 하루도 정말 즐거웠어 고마워"  # length > 20
    samples = [_calculate_delay(text) for _ in range(5)]
    assert len(set(samples)) > 1, f"5회 호출 결과가 전부 동일함(지터 미적용 의심): {samples}"


# ── 2. 감정 배수 적용 ───────────────────────────────────────────────────


@pytest.mark.parametrize("emotion", ["SURPRISED", "ANGRY"])
def test_immediate_reaction_emotions_bias_delay_shorter(emotion):
    """SURPRISED/ANGRY(즉각 반응) → 0.85배 가중, 평균적으로 NEUTRAL보다 짧아야 함."""
    text = "그게 무슨 소리야 진짜 놀랐잖아"  # length > 20, base 고정
    random.seed(42)
    weighted = [_calculate_delay(text, emotion) for _ in range(300)]
    random.seed(42)
    neutral = [_calculate_delay(text, "NEUTRAL") for _ in range(300)]
    avg_weighted = sum(weighted) / len(weighted)
    avg_neutral = sum(neutral) / len(neutral)
    assert avg_weighted < avg_neutral
    # 대략 0.85배 근처인지 (지터로 인한 오차 허용)
    assert 0.80 <= avg_weighted / avg_neutral <= 0.90


@pytest.mark.parametrize("emotion", ["WORRIED", "SAD"])
def test_hesitant_emotions_bias_delay_longer(emotion):
    """WORRIED/SAD(머뭇거림) → 1.2배 가중, 평균적으로 NEUTRAL보다 길어야 함."""
    text = "음... 그건 좀 걱정이 되긴 하는데 어떡하지"  # length > 20
    random.seed(7)
    weighted = [_calculate_delay(text, emotion) for _ in range(300)]
    random.seed(7)
    neutral = [_calculate_delay(text, "NEUTRAL") for _ in range(300)]
    avg_weighted = sum(weighted) / len(weighted)
    avg_neutral = sum(neutral) / len(neutral)
    assert avg_weighted > avg_neutral
    assert 1.10 <= avg_weighted / avg_neutral <= 1.30


def test_unknown_or_default_emotion_uses_multiplier_1x():
    assert _EMOTION_DELAY_MULTIPLIER.get("HAPPY", 1.0) == 1.0
    assert _EMOTION_DELAY_MULTIPLIER.get("", 1.0) == 1.0
    assert _EMOTION_DELAY_MULTIPLIER.get("LOVE", 1.0) == 1.0


# ── 3. 첫 버블 가산 ─────────────────────────────────────────────────────


def test_first_bubble_adds_300_to_500ms_exactly(monkeypatch):
    """random.uniform 을 고정해 지터를 제거하고 첫 버블 가산분만 정확히 측정.

    통계적 비교(seed 재사용 + 호출 순서 비교)는 first-bubble 경로가 추가로
    난수를 1회 더 소비해 이후 호출들의 난수 시퀀스가 어긋나므로 신뢰할 수
    없다 — 대신 random.uniform 자체를 스텁으로 대체해 정확한 값을 검증한다.
    """
    from app import chat_service as cs

    def fake_uniform(a, b):
        if (a, b) == (0.85, 1.15):
            return 1.0  # 지터 없음(배수 1.0)
        if (a, b) == (300, 500):
            return 400  # 첫 버블 가산 고정값
        raise AssertionError(f"unexpected uniform range: {(a, b)}")

    monkeypatch.setattr(cs.random, "uniform", fake_uniform)

    text = "응"  # base=800
    delay_first = _calculate_delay(text, "", is_first_bubble=True)
    delay_non_first = _calculate_delay(text, "", is_first_bubble=False)

    assert delay_non_first == 800
    assert delay_first == 1200
    assert delay_first - delay_non_first == 400


def test_first_bubble_flag_defaults_to_false():
    """기존 호출부(파라미터 미지정)는 첫 버블 가산이 적용되지 않아야 한다."""
    random.seed(99)
    without_flag = _calculate_delay("응")
    random.seed(99)
    explicit_false = _calculate_delay("응", "", False)
    assert without_flag == explicit_false


# ── 4. clamp 경계 (최소 300ms, 최대 3500ms) ──────────────────────────────


def test_clamp_lower_bound_never_below_300ms():
    samples = [_calculate_delay("응") for _ in range(1000)]
    assert min(samples) >= _DELAY_MIN_MS == 300


def test_clamp_upper_bound_never_above_3500ms_even_with_worried_first_bubble():
    """최악 케이스: 긴 텍스트 + WORRIED(1.2배) + 첫 버블(+500ms) + 지터(+15%)도 3500ms를 넘지 않아야."""
    text = "가" * 200  # base = min(200*60+500, 3000) = 3000
    samples = [
        _calculate_delay(text, "WORRIED", is_first_bubble=True) for _ in range(1000)
    ]
    assert max(samples) <= _DELAY_MAX_MS == 3500


def test_delay_is_always_int():
    assert isinstance(_calculate_delay("응"), int)
    assert isinstance(_calculate_delay("가" * 50, "SAD", True), int)


# ── 5. 서버는 sleep 하지 않는다 (delay는 메타데이터로만 사용) ───────────


def test_calculate_delay_does_not_sleep(monkeypatch):
    """_calculate_delay는 시간을 소비하는 sleep을 호출하지 않아야 한다(클라이언트가 delay를 적용)."""
    import asyncio
    import time as time_module

    def _fail_sleep(*args, **kwargs):
        raise AssertionError("_calculate_delay는 sleep을 호출해서는 안 된다")

    monkeypatch.setattr(time_module, "sleep", _fail_sleep)

    async def _assert_no_async_sleep():
        orig_sleep = asyncio.sleep

        async def _fail_async_sleep(*args, **kwargs):
            raise AssertionError("_calculate_delay는 asyncio.sleep을 호출해서는 안 된다")

        asyncio.sleep = _fail_async_sleep
        try:
            _calculate_delay("테스트 문장입니다 길이 체크용")
        finally:
            asyncio.sleep = orig_sleep

    asyncio.run(_assert_no_async_sleep())


# ── 6. 통합: _parse_reply / IncrementalReplyParser의 첫 버블 판정 ───────


def test_parse_reply_marks_only_first_item_as_first_bubble(monkeypatch):
    """멀티 버블 JSON 응답에서 첫 항목만 first-bubble 가산을 받는지 간접 확인.

    _calculate_delay 를 모니터링해 is_first_bubble 인자가 호출 순서대로
    [True, False, False] 인지 검증한다.
    """
    calls = []
    from app import chat_service as cs

    orig = cs._calculate_delay

    def _spy(text, emotion="", is_first_bubble=False):
        calls.append(is_first_bubble)
        return orig(text, emotion, is_first_bubble)

    monkeypatch.setattr(cs, "_calculate_delay", _spy)

    content = (
        '[{"text":"첫 문장","emotion":"NEUTRAL"},'
        '{"text":"두번째","emotion":"HAPPY"},'
        '{"text":"세번째","emotion":"SAD"}]'
    )
    parts = _parse_reply(content)
    assert len(parts) == 3
    assert calls == [True, False, False]


def test_incremental_parser_marks_only_first_emitted_bubble_as_first(monkeypatch):
    calls = []
    from app import chat_service as cs

    orig = cs._calculate_delay

    def _spy(text, emotion="", is_first_bubble=False):
        calls.append(is_first_bubble)
        return orig(text, emotion, is_first_bubble)

    monkeypatch.setattr(cs, "_calculate_delay", _spy)

    p = IncrementalReplyParser()
    content = '[{"text":"안녕","emotion":"HAPPY"},{"text":"반가워","emotion":"LOVE"}]'
    parts = []
    for ch in content:
        parts.extend(p.feed(ch))
    assert len(parts) == 2
    assert calls == [True, False]
