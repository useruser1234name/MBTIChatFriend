"""호감도별 disclosure(감정 개방 수위) 게이팅 검증 — 2026-08-03 회의 M1.

배경: 정적 블록("# 자기설명 금지")이 전 레벨에 "조금만 내주고 더 많이 감춰"를
강제하는데, AFFINITY_BEHAVIORS[5]는 "적극적 애정 표현 / 달달함 최대치"를,
high few-shot은 직접 진술("나도 진짜 보고 싶었어")을 시연해서 레벨 5 톤이
상충 지시를 동시에 받고 요동쳤다.

수정: 개방 수위를 정적 블록에서 빼내 호감도별 `disclosure` 한 줄로 위임한다.
- Lv1-3: 감춤 (행동·말투·침묵으로만)
- Lv4: 슬쩍 인정하되 이유는 설명 안 함
- Lv5: 직접 표현 허용, 단 자기 감정 해설은 여전히 금지

부수 변경: "질문으로 대화 이어가"(무조건) → 2~3턴에 한 번 수준으로 완화.
"""

import json

import pytest

from app.prompts import AFFINITY_BEHAVIORS, build_system_prompt

MBTI_ALL = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]


def _prompt(affinity_level=1, mbti="ENFP"):
    return build_system_prompt(
        mbti=mbti,
        speech_style="CASUAL",
        relationship="FRIEND",
        nickname="테스터",
        affinity_level=affinity_level,
    )


class TestDisclosureKeyDefined:
    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_every_level_has_disclosure(self, level):
        assert AFFINITY_BEHAVIORS[level].get("disclosure", "").strip()


class TestDisclosureInjectedPerLevel:
    """레벨별로 서로 다른 disclosure 문구가 실제 프롬프트에 주입되는가."""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_line_present(self, level):
        prompt = _prompt(affinity_level=level)
        expected = AFFINITY_BEHAVIORS[level]["disclosure"]
        assert f"드러내기: {expected}" in prompt

    def test_low_levels_say_conceal(self):
        for level in (1, 2, 3):
            prompt = _prompt(affinity_level=level)
            assert "드러내기:" in prompt
            line = next(
                ln for ln in prompt.splitlines() if ln.startswith("드러내기:")
            )
            assert "감춰" in line or "가끔만 슬쩍" in line, (
                f"Lv{level}는 감춤 기조여야 함: {line}"
            )

    def test_level4_allows_partial_admission_without_explanation(self):
        line = next(
            ln for ln in _prompt(affinity_level=4).splitlines()
            if ln.startswith("드러내기:")
        )
        assert "슬쩍 인정" in line
        assert "설명하지 마" in line

    def test_level5_allows_direct_affection_but_bans_self_analysis(self):
        line = next(
            ln for ln in _prompt(affinity_level=5).splitlines()
            if ln.startswith("드러내기:")
        )
        assert "직접 표현해도 돼" in line
        assert "분석하거나 해설하지는 마" in line

    def test_levels_are_not_all_identical(self):
        """게이팅이 실제로 갈리는지 (한 문구를 전 레벨에 복붙하면 실패)."""
        lines = {
            level: next(
                ln for ln in _prompt(affinity_level=level).splitlines()
                if ln.startswith("드러내기:")
            )
            for level in (1, 3, 4, 5)
        }
        assert len(set(lines.values())) >= 3

    @pytest.mark.parametrize("mbti", MBTI_ALL)
    def test_all_16_types_get_disclosure_line(self, mbti):
        assert "드러내기:" in _prompt(affinity_level=5, mbti=mbti)

    def test_unknown_level_falls_back_to_level1(self):
        """AFFINITY_BEHAVIORS에 없는 레벨이 와도 KeyError 없이 감춤 기조."""
        prompt = build_system_prompt(
            mbti="ENFP", speech_style="CASUAL", relationship="FRIEND",
            nickname="테스터", affinity_level=99,
        )
        assert f"드러내기: {AFFINITY_BEHAVIORS[1]['disclosure']}" in prompt


class TestStaticBlockNoLongerForcesConcealment:
    """정적 블록은 수위를 정하지 않고 호감도 지침에 위임한다."""

    def test_blanket_conceal_clause_removed(self):
        for level in (1, 3, 5):
            assert "조금만 내주고 더 많이 감춰" not in _prompt(affinity_level=level)

    def test_delegation_clause_present(self):
        prompt = _prompt(affinity_level=5)
        assert "얼마나 드러낼지는 아래 호감도 지침을 따라" in prompt

    def test_show_dont_tell_hint_preserved(self):
        """test_prompts_roleplay.py와 동일 계약 — 이 문구는 유지되어야 함."""
        assert "행동/말투/망설임/침묵" in _prompt()

    def test_delegation_precedes_affinity_section(self):
        """'아래 호감도 지침'이 실제로 아래에 있어야 지시가 성립."""
        prompt = _prompt(affinity_level=5)
        assert prompt.index("얼마나 드러낼지는 아래 호감도 지침을 따라") < prompt.index(
            "드러내기:"
        )


class TestQuestionCompulsionRemoved:
    """매 턴 질문 종결 강박 제거 (웹 MVP의 'Do not end every message with a question')."""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_unconditional_question_rule_gone(self, level):
        assert "- 질문으로 대화 이어가." not in _prompt(affinity_level=level)

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_rationed_question_rule_present(self, level):
        prompt = _prompt(affinity_level=level)
        assert "질문은 정말 궁금할 때만, 2~3턴에 한 번" in prompt
        assert "자기 이야기나 행동으로 끝내도 좋아" in prompt

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_short_reply_rule_no_longer_mandates_question(self, level):
        """대화 흐름/특수 상황의 '짧은 대답' 지침이 품질 규칙과 모순되지 않는가."""
        prompt = _prompt(affinity_level=level)
        assert "짧은 대답(ㅇㅇ, ㅋㅋ)엔 자연스러운 질문으로 이어가" not in prompt
        assert "짧은 대답: 자연스러운 질문/새 주제로 이어가" not in prompt


class TestFewShotFormulaicPhrasesReplaced:
    """웹 MVP 금지 목록과 동일한 정형 위로 문구를 few-shot에서 제거.

    주의: 검사 범위는 few-shot 예시(`## 대화 예시` 섹션)와 FEW_SHOT_EXAMPLES
    딕셔너리로 한정한다. MBTI_PERSONALITIES의 speech_habits(예: ISFJ의
    "괜찮아? 무리하면 안 돼...")는 캐릭터 고유 말버릇이라 이번 범위가 아니다.
    """

    BANNED = [
        "나한테 다 얘기해, 들을게",
        "괜찮아, 내가 여기 있잖아",
        "다 말해줘... 내가 안아줄게",
        "무리하면 안 돼",
    ]

    @staticmethod
    def _few_shot_block(prompt: str) -> str:
        start = prompt.index("## 대화 예시")
        rest = prompt[start:]
        end = rest.index("\n\n")
        return rest[:end]

    def test_banned_phrases_absent_from_examples_dict(self):
        from app.prompts import FEW_SHOT_EXAMPLES

        blob = json.dumps(FEW_SHOT_EXAMPLES, ensure_ascii=False)
        for phrase in self.BANNED:
            assert phrase not in blob, f"few-shot에 금지 문구 잔존: {phrase}"

    @pytest.mark.parametrize("mbti", MBTI_ALL)
    @pytest.mark.parametrize("level", [1, 3, 5])
    def test_no_banned_phrase_in_rendered_few_shot(self, mbti, level):
        block = self._few_shot_block(_prompt(affinity_level=level, mbti=mbti))
        for phrase in self.BANNED:
            assert phrase not in block, f"{mbti} Lv{level}에 금지 문구: {phrase}"

    def test_replacements_are_present(self):
        """실제 대체 문구가 렌더링되는지 (삭제만 하고 빈칸으로 두면 실패)."""
        nf_mid = self._few_shot_block(_prompt(affinity_level=3, mbti="ENFP"))
        assert "(하던 거 다 밀어두고)" in nf_mid
        nf_high = self._few_shot_block(_prompt(affinity_level=5, mbti="ENFP"))
        assert "(하던 말 멈추고)" in nf_high
        sj_mid = self._few_shot_block(_prompt(affinity_level=3, mbti="ISFJ"))
        assert "오늘은 그냥 일찍 자" in sj_mid

    def test_replacements_are_valid_json_with_valid_emotions(self):
        """교체한 예시가 여전히 유효 JSON + 유효 emotion 코드인가."""
        valid = {
            "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
            "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
        }
        for mbti in ("ENFP", "ISFJ"):
            for level in (1, 3, 5):
                block = self._few_shot_block(
                    _prompt(affinity_level=level, mbti=mbti)
                )
                lines = [ln for ln in block.splitlines() if ln.startswith("응답: ")]
                assert lines
                for ln in lines:
                    arr = json.loads(ln[len("응답: "):])
                    assert isinstance(arr, list) and arr
                    for obj in arr:
                        assert set(obj.keys()) == {"text", "emotion"}
                        assert obj["text"].strip()
                        assert obj["emotion"] in valid

    def test_sj_care_marker_preserved(self):
        """SJ 보살핌형 정체성은 유지 (test_few_shot_group.py와 동일 계약)."""
        assert "밥은 제대로 먹고 다녀?" in _prompt(affinity_level=3, mbti="ISFJ")
