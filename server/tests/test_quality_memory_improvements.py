import json

from app.memory_service import merge_memory_facts
from app.quality_service import classify_quality_issues, quick_score


def _reply(parts):
    return json.dumps(parts, ensure_ascii=False)


def test_classify_quality_issues_detects_invalid_json():
    assert classify_quality_issues("안녕", "그냥 텍스트") == ["JSON_INVALID"]
    assert quick_score("안녕", "그냥 텍스트", "ENFP") == 0.1


def test_classify_quality_issues_detects_repetition_and_monotone_emotion():
    response = _reply([
        {"text": "좋아 좋아", "emotion": "HAPPY"},
        {"text": "좋아 좋아", "emotion": "HAPPY"},
    ])

    issues = classify_quality_issues("오늘 기분 좋아", response)

    assert "REPEATED_TEXT" in issues
    assert "MONOTONE_EMOTION" in issues
    assert quick_score("오늘 기분 좋아", response, "ENFP") < 1.0


def test_classify_quality_issues_detects_user_echo():
    response = _reply([{"text": "오늘 너무 힘들어", "emotion": "SAD"}])

    issues = classify_quality_issues("오늘 너무 힘들어", response)

    assert "ECHO_USER" in issues


def test_merge_memory_facts_replaces_stale_same_key_value():
    merged = merge_memory_facts(
        [{"key": "취미", "value": "독서"}],
        [{"key": "취미", "value": "클라이밍"}],
    )

    assert merged == [{"key": "취미", "value": "클라이밍"}]


def test_merge_memory_facts_skips_sensitive_values():
    merged = merge_memory_facts(
        [{"key": "취미", "value": "독서"}],
        [
            {"key": "전화번호", "value": "010-1234-5678"},
            {"key": "이메일", "value": "user@example.com"},
            {"key": "좋아하는 음식", "value": "김치찌개"},
        ],
    )

    assert {"key": "전화번호", "value": "010-1234-5678"} not in merged
    assert {"key": "이메일", "value": "user@example.com"} not in merged
    assert {"key": "좋아하는 음식", "value": "김치찌개"} in merged


def test_merge_memory_facts_keeps_core_and_caps_non_core():
    existing = [{"key": "이름", "value": "민지"}]
    new_facts = [{"key": f"주제{i}", "value": str(i)} for i in range(20)]

    merged = merge_memory_facts(existing, new_facts, max_total=5)

    assert {"key": "이름", "value": "민지"} in merged
    assert len(merged) == 5
    assert merged[-1] == {"key": "주제19", "value": "19"}
