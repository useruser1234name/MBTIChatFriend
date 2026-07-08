"""유저 발화 스타일 미러링(개인화 되먹임 MVP) 검증.

대상:
- user_preference.derive_user_style / render_preference_section
- prompts.build_system_prompt 의 preference_context 배선 + 위치 + 바이트 등가

mutation 방어: 스타일 산출/렌더/삽입위치/등가를 각각 독립 assert.
"""

from app.models import HistoryMessage
from app.prompts import build_system_prompt
from app.user_preference import derive_user_style, render_preference_section


def _hist(*pairs):
    """(role, content) 튜플들을 HistoryMessage 리스트로."""
    return [HistoryMessage(role=r, content=c) for r, c in pairs]


# ── (a) 반말 + 짧은 문장 + ㅋㅋ → casual/short/jamo ──────────────────
class TestCasualShortStyle:
    def test_derive_casual_short_jamo(self):
        hist = _hist(
            ("user", "뭐해 ㅋㅋ"),
            ("assistant", "책 읽어"),
            ("user", "헐 대박 ㅋㅋ"),
            ("assistant", "왜"),
            ("user", "심심해 ㅠㅠ"),
        )
        style = derive_user_style(hist)
        assert style is not None
        assert style["len_pref"] == "short"
        assert style["formality"] == "casual"
        assert style["uses_jamo"] is True

    def test_render_casual_hints(self):
        style = {
            "len_pref": "short",
            "formality": "casual",
            "uses_jamo": True,
            "uses_emoticon": False,
        }
        out = render_preference_section(style)
        assert "과하게 길게" in out  # 짧게 유도
        assert "딱딱하게 굴지 마" in out  # 가벼운 톤 유도


# ── (b) 존댓말 + 긴 문장 → formal/long (반대 산출) ───────────────────
class TestFormalLongStyle:
    def test_derive_formal_long(self):
        long_a = (
            "오늘 회사에서 정말 많은 일이 있었는데요, 프로젝트 마감이 겹쳐서 "
            "하루 종일 정신없이 바쁘게 보냈던 것 같아요 정말 힘든 하루였습니다"
        )
        long_b = (
            "그래도 동료분들이 많이 도와주셔서 무사히 잘 마무리할 수 있었어요 "
            "이런 날에는 따뜻한 저녁이 생각나네요 오늘 하루도 수고 많으셨어요"
        )
        hist = _hist(
            ("user", long_a),
            ("assistant", "고생 많았어"),
            ("user", long_b),
        )
        style = derive_user_style(hist)
        assert style is not None
        assert style["len_pref"] == "long"
        assert style["formality"] == "formal"

    def test_render_formal_opposite_of_casual(self):
        style = {
            "len_pref": "long",
            "formality": "formal",
            "uses_jamo": False,
            "uses_emoticon": False,
        }
        out = render_preference_section(style)
        assert "충분히 답해줘" in out  # 길게 유도
        assert "존댓말 톤" in out
        assert "가볍게 툭툭" in out
        # casual 전용 문구가 새어들어오면 안 됨 (mutation 방어)
        assert "과하게 길게" not in out


# ── (c) 히스토리 부족 → None / 빈 문자열 ────────────────────────────
class TestColdStart:
    def test_single_user_turn_returns_none(self):
        hist = _hist(("user", "안녕 ㅋㅋ"), ("assistant", "안녕"))
        assert derive_user_style(hist) is None

    def test_empty_history_returns_none(self):
        assert derive_user_style([]) is None
        assert derive_user_style(None) is None

    def test_render_none_is_empty(self):
        assert render_preference_section(None) == ""
        assert render_preference_section({}) == ""


# ── (d) preference_section 위치: compat 뒤 · few_shot 앞 ──────────────
class TestSectionPlacement:
    def test_between_compat_and_fewshot(self):
        pref = (
            "## 상대 말투 참고 (약한 힌트, 강제 아님)\n"
            "- 상대는 짧고 가벼운 메시지를 즐겨 써. 답장을 과하게 길게 늘어뜨리지 마.\n"
            "단, 캐릭터 성격과 말투가 항상 우선이야."
        )
        prompt = build_system_prompt(
            mbti="ENFP",
            speech_style="CASUAL",
            relationship="FRIEND",
            nickname="테스터",
            affinity_level=1,       # few_shot 예시 유발
            user_mbti="INTJ",       # compat 섹션 유발
            preference_context=pref,
        )
        compat_marker = "## MBTI 궁합"
        pref_marker = "## 상대 말투 참고"
        fewshot_marker = "## 대화 예시"
        assert compat_marker in prompt
        assert pref_marker in prompt
        assert fewshot_marker in prompt
        assert (
            prompt.index(compat_marker)
            < prompt.index(pref_marker)
            < prompt.index(fewshot_marker)
        )


# ── (e) 렌더 결과에 "캐릭터 성격 우선" 문구 포함 ────────────────────
class TestCharacterPriorityAlwaysPresent:
    def test_priority_clause_in_every_render(self):
        for style in (
            {"len_pref": "short", "formality": "casual", "uses_jamo": True, "uses_emoticon": False},
            {"len_pref": "long", "formality": "formal", "uses_jamo": False, "uses_emoticon": False},
            {"len_pref": "medium", "formality": "mixed", "uses_jamo": False, "uses_emoticon": False},
        ):
            out = render_preference_section(style)
            assert "캐릭터 성격" in out
            assert "우선" in out

    def test_render_within_token_budget(self):
        """≤100토큰(한국어 대략 200자 이내) 목표."""
        style = {"len_pref": "long", "formality": "formal", "uses_jamo": True, "uses_emoticon": True}
        out = render_preference_section(style)
        assert len(out) <= 200


# ── (f) preference_context 빈 값 → build_system_prompt 바이트 등가 ────
class TestByteEquivalenceWhenEmpty:
    _BASE = dict(
        mbti="INTJ",
        speech_style="CASUAL",
        relationship="FRIEND",
        nickname="테스터",
        affinity_level=3,
        user_mbti="ENFP",
    )

    def test_default_equals_explicit_empty(self):
        without = build_system_prompt(**self._BASE)
        explicit_empty = build_system_prompt(**self._BASE, preference_context="")
        assert without == explicit_empty

    def test_nonempty_changes_output(self):
        without = build_system_prompt(**self._BASE)
        withctx = build_system_prompt(
            **self._BASE,
            preference_context="## 상대 말투 참고\n- 힌트\n단, 캐릭터 성격과 말투가 항상 우선이야.",
        )
        assert withctx != without
        assert "## 상대 말투 참고" in withctx
        assert "## 상대 말투 참고" not in without
