"""IncrementalReplyParser 유닛테스트 — 말풍선 점진 스트리밍 파서.

핵심 계약:
- {"text","emotion"} 객체가 완결되는 순간 즉시 방출 (전체 완료 전)
- 토큰이 임의 경계로 쪼개져도 정확히 복원
- 형식 오류/유효하지 않은 감정 → 안전 폴백
"""

from app.chat_service import IncrementalReplyParser
from app.models import ReplyPart


def _feed_all(parser: IncrementalReplyParser, chunks):
    parts = []
    for c in chunks:
        parts.extend(parser.feed(c))
    return parts


def test_emits_each_bubble_as_it_completes():
    p = IncrementalReplyParser()
    # 첫 객체가 닫히기 전엔 아무 것도 방출하지 않음
    assert p.feed('[{"text":"안녕",') == []
    assert p.feed('"emotion":"HAPPY"}') != []  # 여기서 첫 말풍선 완결
    assert p.emitted_count == 1
    # 두 번째 객체
    out2 = p.feed(',{"text":"반가워","emotion":"LOVE"}]')
    assert len(out2) == 1
    assert p.emitted_count == 2


def test_full_result_matches_expected_parts():
    p = IncrementalReplyParser()
    content = '[{"text":"오늘 뭐했어?","emotion":"PLAYFUL"},{"text":"보고싶었어","emotion":"LOVE"}]'
    parts = _feed_all(p, list(content))  # 문자 단위로 극단 분할
    assert [x.text for x in parts] == ["오늘 뭐했어?", "보고싶었어"]
    assert [x.emotion for x in parts] == ["PLAYFUL", "LOVE"]
    assert all(isinstance(x, ReplyPart) for x in parts)
    assert all(x.delay > 0 for x in parts)


def test_handles_code_fence_wrapping():
    p = IncrementalReplyParser()
    chunks = ['```json\n[', '{"text":"응","emotion":"NEUTRAL"}', ']\n```']
    parts = _feed_all(p, chunks)
    assert len(parts) == 1
    assert parts[0].text == "응"


def test_escaped_quotes_and_braces_in_text():
    p = IncrementalReplyParser()
    content = r'[{"text":"그가 \"안녕\" 이라 했어 {웃음}","emotion":"HAPPY"}]'
    parts = _feed_all(p, [content])
    assert len(parts) == 1
    assert parts[0].text == '그가 "안녕" 이라 했어 {웃음}'
    assert parts[0].emotion == "HAPPY"


def test_invalid_emotion_falls_back_to_neutral():
    p = IncrementalReplyParser()
    parts = _feed_all(p, ['[{"text":"음","emotion":"BOGUS"}]'])
    assert len(parts) == 1
    assert parts[0].emotion == "NEUTRAL"


def test_empty_text_object_skipped():
    p = IncrementalReplyParser()
    parts = _feed_all(p, ['[{"text":"","emotion":"SAD"},{"text":"진짜","emotion":"SAD"}]'])
    assert [x.text for x in parts] == ["진짜"]
    assert p.emitted_count == 1


def test_broken_format_emits_nothing_and_preserves_raw():
    p = IncrementalReplyParser()
    raw = "이건 그냥 평범한 텍스트야 JSON 아님"
    parts = _feed_all(p, [raw])
    assert parts == []
    assert p.emitted_count == 0
    assert p.raw == raw  # 호출측 폴백(_parse_reply)이 쓸 원문 보존


def test_partial_object_not_emitted_until_closed():
    p = IncrementalReplyParser()
    assert p.feed('[{"text":"기다려","emotion":"WORR') == []  # 미완결
    assert p.emitted_count == 0
    out = p.feed('IED"}]')
    assert len(out) == 1
    assert out[0].emotion == "WORRIED"
