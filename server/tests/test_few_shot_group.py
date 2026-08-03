"""_few_shot_group 분류 검증 (2026-08-03 회의 S1).

배경: FEW_SHOT_EXAMPLES의 "ST"/"SF" 키는 본문이 SJ(보살핌형)/SP(활발형)
기준으로 작성돼 있었는데, 예시 선택 시 get_mbti_group(NT/NF/ST/SF, S 유형을
T/F로 분류)을 그대로 재사용해서 ISTP·ESTP·ISTJ·ESTJ가 "ST" 키로, ISFJ·ESFJ·
ISFP·ESFP가 "SF" 키로 묶이는 바람에 ISTP/ESTP(SP 기질)가 SJ 예시를, ISFJ/ESFJ
(SJ 기질)가 SP 예시를 받는 오배정이 있었다.

수정: few-shot 전용 `_few_shot_group`을 신설해 S 유형을 J/P로 재분류하고
(SJ/SP), FEW_SHOT_EXAMPLES 키도 "ST"→"SJ", "SF"→"SP"로 개명했다.
get_mbti_group 자체(궁합/호감도 가중치용 정본)는 변경하지 않았다.
"""

import pytest

from app.prompts import FEW_SHOT_EXAMPLES, _few_shot_group, build_system_prompt

EXPECTED_GROUPS = {
    "INTJ": "NT", "INTP": "NT", "ENTJ": "NT", "ENTP": "NT",
    "INFJ": "NF", "INFP": "NF", "ENFJ": "NF", "ENFP": "NF",
    "ISTJ": "SJ", "ISFJ": "SJ", "ESTJ": "SJ", "ESFJ": "SJ",
    "ISTP": "SP", "ISFP": "SP", "ESTP": "SP", "ESFP": "SP",
}


class TestFewShotGroup:
    @pytest.mark.parametrize("mbti,expected", list(EXPECTED_GROUPS.items()))
    def test_16_types_map_to_expected_group(self, mbti, expected):
        assert _few_shot_group(mbti) == expected

    def test_groups_are_keys_of_few_shot_examples(self):
        """분류 결과가 실제 FEW_SHOT_EXAMPLES 딕셔너리 키와 어긋나지 않는지."""
        assert set(EXPECTED_GROUPS.values()) == set(FEW_SHOT_EXAMPLES.keys())

    def test_istp_no_longer_gets_sj_examples(self):
        """회귀 방지: ISTP(SP 기질)가 예전처럼 SJ(보살핌형) 예시를 받지 않는다."""
        prompt = build_system_prompt(
            mbti="ISTP", speech_style="CASUAL", relationship="FRIEND",
            nickname="유저", affinity_level=3,
        )
        # SP mid 예시 고유 문구
        assert "오 뭔데뭔데?!" in prompt
        # SJ mid 예시 고유 문구는 없어야 함
        assert "밥은 제대로 먹고 다녀?" not in prompt

    def test_isfj_no_longer_gets_sp_examples(self):
        """회귀 방지: ISFJ(SJ 기질)가 예전처럼 SP(활발형) 예시를 받지 않는다."""
        prompt = build_system_prompt(
            mbti="ISFJ", speech_style="CASUAL", relationship="FRIEND",
            nickname="유저", affinity_level=3,
        )
        # SJ mid 예시 고유 문구
        assert "밥은 제대로 먹고 다녀?" in prompt
        # SP mid 예시 고유 문구는 없어야 함
        assert "오 뭔데뭔데?!" not in prompt
