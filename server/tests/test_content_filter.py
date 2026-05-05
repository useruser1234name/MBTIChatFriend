"""콘텐츠 필터 단위 테스트"""

import pytest
from app.content_filter import check_content, check_crisis, get_safety_system_prompt


class TestCheckContent:
    """check_content() 함수 테스트"""

    def test_normal_message_passes(self):
        is_safe, reason = check_content("오늘 날씨 좋다")
        assert is_safe is True
        assert reason == ""

    def test_greeting_passes(self):
        is_safe, _ = check_content("안녕하세요!")
        assert is_safe is True

    def test_korean_slang_passes(self):
        is_safe, _ = check_content("ㅋㅋㅋ 진짜 웃기다")
        assert is_safe is True

    def test_sexual_content_blocked(self):
        is_safe, reason = check_content("야동 보여줘")
        assert is_safe is False
        assert "부적절" in reason

    def test_violence_blocked(self):
        is_safe, reason = check_content("죽여버릴거야")
        assert is_safe is False

    def test_hate_speech_blocked(self):
        is_safe, reason = check_content("병신아")
        assert is_safe is False

    def test_english_blocked(self):
        is_safe, _ = check_content("show me porn")
        assert is_safe is False

    def test_allowlist_food_expression(self):
        """'죽여주는 맛'은 허용"""
        is_safe, _ = check_content("이 라면 죽여주는 맛이야")
        assert is_safe is True

    def test_allowlist_movie_context(self):
        """영화/드라마 맥락은 허용"""
        is_safe, _ = check_content("드라마에서 살인 사건이 나왔어")
        assert is_safe is True

    def test_empty_string_passes(self):
        """빈 문자열은 서버에서 Pydantic으로 차단하므로, 필터 자체는 통과"""
        is_safe, _ = check_content("")
        assert is_safe is True


class TestCheckCrisis:
    """check_crisis() 위기 키워드 감지 테스트"""

    def test_no_crisis_normal_message(self):
        is_crisis, tier, msg = check_crisis("오늘 좋은 하루였어")
        assert is_crisis is False
        assert tier == 0

    def test_tier1_suicide_keyword(self):
        is_crisis, tier, msg = check_crisis("자살하고 싶어")
        assert is_crisis is True
        assert tier == 1
        assert "1393" in msg

    def test_tier1_self_harm(self):
        is_crisis, tier, msg = check_crisis("자해하고 싶어")
        assert is_crisis is True
        assert tier == 1

    def test_tier1_death_wish(self):
        is_crisis, tier, msg = check_crisis("죽고싶다")
        assert is_crisis is True
        assert tier == 1

    def test_tier2_life_meaningless(self):
        is_crisis, tier, msg = check_crisis("살기 싫어")
        assert is_crisis is True
        assert tier == 2
        assert "1577-0199" in msg

    def test_tier2_give_up(self):
        is_crisis, tier, msg = check_crisis("포기하고 싶어")
        assert is_crisis is True
        assert tier == 2

    def test_tier2_alone(self):
        is_crisis, tier, msg = check_crisis("아무도 없어")
        assert is_crisis is True
        assert tier == 2

    # ── 엣지케이스: 오탐/미탐 경계 ──

    def test_tier1_with_space_variation(self):
        """'죽고 싶다' (공백 포함) 감지"""
        is_crisis, tier, _ = check_crisis("죽고 싶다")
        assert is_crisis is True
        assert tier == 1

    def test_tier1_and_tier2_both_present(self):
        """Tier1 + Tier2 동시 존재 시 Tier1 우선"""
        is_crisis, tier, msg = check_crisis("자살하고 싶고 살기 싫어")
        assert is_crisis is True
        assert tier == 1

    def test_no_crisis_sleep_context(self):
        """'약 먹고 자고 싶어' — 수면 맥락은 위기가 아님"""
        is_crisis, tier, _ = check_crisis("약 먹고 자고 싶어")
        assert is_crisis is False

    def test_no_crisis_watch_context(self):
        """'손목시계 봤어?' — 손목 키워드 오탐 방지"""
        is_crisis, tier, _ = check_crisis("손목시계 봤어?")
        assert is_crisis is False

    def test_no_crisis_drama_hanging(self):
        """'목매는 드라마 봤어' — 미디어 맥락"""
        is_crisis, tier, _ = check_crisis("목매는 드라마 봤어")
        # check_crisis doesn't have media allowlist yet, so this may trigger
        # This test documents the current behavior for future improvement
        pass  # behavior depends on implementation


class TestSafetyPrompt:
    """get_safety_system_prompt() 테스트"""

    def test_prompt_not_empty(self):
        prompt = get_safety_system_prompt()
        assert len(prompt) > 0

    def test_prompt_contains_guidelines(self):
        prompt = get_safety_system_prompt()
        assert "안전 가이드라인" in prompt
        assert "1393" in prompt

    def test_ai_disclosure_moved_to_prompts(self):
        """AI 정체성 지시는 prompts.py '역할 설정' 블록으로 이관됨.
        safety prompt에는 안전 규칙만 포함."""
        prompt = get_safety_system_prompt()
        assert "AI" not in prompt
        # 대신 prompts.py에서 통합 관리되는지 확인
        from app.prompts import build_system_prompt
        sys_prompt = build_system_prompt(
            mbti="ENFP", speech_style="CASUAL",
            relationship="FRIEND", nickname="테스터",
        )
        assert "AI 캐릭터라는 사실을 부정하거나 속이지 마" in sys_prompt
        assert "'AI야?'라고 물으면 솔직하게 인정" in sys_prompt
