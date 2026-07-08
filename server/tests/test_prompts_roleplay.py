"""역할극 몰입 지침 이식(회의 갭 B Phase 0~2) 검증 테스트.

대상: prompts.build_system_prompt
- 자기설명 금지 / 행동 처리 지침이 정적 영역에 포함되는가
- AI 가드 문구가 여전히 존재하는가 (test_content_filter와 이중 안전망)
- 행동 지문 예시가 유효 JSON + 유효 emotion 코드인가 (평문 유도 방지)
- few_shot 섹션이 per-turn episode 섹션보다 앞에 위치하는가 (prefix cache)
"""

import json
import re

import pytest

from app.prompts import build_system_prompt

VALID_EMOTIONS = {
    "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
    "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
}


def _prompt(**overrides):
    kwargs = dict(
        mbti="ENFP",
        speech_style="CASUAL",
        relationship="FRIEND",
        nickname="테스터",
    )
    kwargs.update(overrides)
    return build_system_prompt(**kwargs)


class TestSelfExplanationBan:
    """Phase 1 — 자기설명 금지 지침"""

    def test_section_header_present(self):
        assert "# 자기설명 금지" in _prompt()

    def test_bans_mbti_self_label(self):
        prompt = _prompt(mbti="INTP")
        # "나는 {mbti}라서" 형태의 자기설명 금지 문구 (mbti가 치환됨)
        assert "나는 INTP라서" in prompt
        assert "자기설명은 절대 하지 마" in prompt

    def test_bans_system_mention(self):
        prompt = _prompt()
        assert "시스템/프롬프트/설정 언급 금지" in prompt

    def test_show_dont_tell_hint(self):
        prompt = _prompt()
        assert "행동/말투/망설임/침묵" in prompt


class TestRoleplayActionHandling:
    """Phase 2 — 행동 처리 지침 + 형식 계약"""

    def test_section_header_present(self):
        assert "# 행동 처리" in _prompt()

    def test_reacts_to_user_action(self):
        prompt = _prompt()
        assert "상호작용 역할극" in prompt

    def test_format_contract_enforced(self):
        """행동 지문은 반드시 text 값 안 괄호로, JSON 밖 서술 금지."""
        prompt = _prompt()
        assert "행동 지문은 반드시 text 값 안에 괄호로 넣어라" in prompt
        assert "JSON 밖에 아무것도 쓰지 마라" in prompt


class TestActionExamplesAreValidJson:
    """Phase 0 — 예시가 유효 JSON 배열 + 유효 emotion (평문 유도 방지)"""

    def test_good_examples_parse_as_json(self):
        prompt = _prompt()
        good_lines = [
            ln for ln in prompt.splitlines()
            if ln.startswith("좋은 예")
        ]
        assert len(good_lines) >= 2, "좋은 예시가 2개 이상 있어야 함"
        for ln in good_lines:
            # "좋은 예1: [ ... ]" 에서 JSON 배열만 추출
            m = re.search(r"(\[.*\])\s*$", ln)
            assert m, f"JSON 배열을 찾지 못함: {ln}"
            arr = json.loads(m.group(1))
            assert isinstance(arr, list) and arr
            for obj in arr:
                assert set(obj.keys()) == {"text", "emotion"}
                assert obj["text"].strip()
                assert obj["emotion"] in VALID_EMOTIONS

    def test_good_examples_use_paren_action(self):
        """행동 지문이 text 값 안 괄호로 들어있는지 (형식 시연)."""
        prompt = _prompt()
        good_lines = [
            ln for ln in prompt.splitlines()
            if ln.startswith("좋은 예")
        ]
        joined = "\n".join(good_lines)
        assert "(" in joined and ")" in joined


class TestAiGuardStillPresent:
    """AI 가드 문구 보존 (test_content_filter.py:178-183과 동일 계약)"""

    def test_ai_disclosure_present(self):
        prompt = _prompt()
        assert "AI 캐릭터라는 사실을 부정하거나 속이지 마" in prompt
        assert "'AI야?'라고 물으면 솔직하게 인정" in prompt


class TestFewShotBeforeEpisode:
    """Phase 4 — few_shot(반동적)이 per-turn episode(동적)보다 앞에 위치"""

    def test_few_shot_precedes_episode(self):
        prompt = _prompt(
            affinity_level=1,
            episode_context="## 에피소드 기억\n지난번에 카페 갔던 얘기",
        )
        few_shot_marker = "## 대화 예시"
        episode_marker = "## 에피소드 기억"
        assert few_shot_marker in prompt, "ENFP few_shot 예시가 있어야 함"
        assert episode_marker in prompt
        assert prompt.index(few_shot_marker) < prompt.index(episode_marker), (
            "few_shot이 episode보다 먼저 나와야 캐시 안정성 확보"
        )
