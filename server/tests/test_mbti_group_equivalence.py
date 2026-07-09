"""chat_service._get_mbti_group 와 prompts._get_mbti_group 동치성 테스트.

두 모듈은 각자 독립적으로 MBTI → 4개 기능 그룹(NT/NF/ST/SF) 분류 함수를
갖고 있다(chat_service.py 약 119-130줄, prompts.py 약 804-808줄). 로직이
문자 그대로 동일하지 않으므로(chat_service는 세부 분기, prompts는 단순
슬라이싱) 리팩토링 시 하나로 통합하기 전에 16종 전체에서 실제로 같은
결과를 내는지 특성화해 고정한다.
"""

from app import chat_service
from app import prompts

ALL_MBTI = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]


def test_mbti_group_classification_equivalent_across_modules():
    mismatches = [
        (m, chat_service._get_mbti_group(m), prompts._get_mbti_group(m))
        for m in ALL_MBTI
        if chat_service._get_mbti_group(m) != prompts._get_mbti_group(m)
    ]
    assert not mismatches, f"그룹 분류 불일치: {mismatches}"

    for m in ALL_MBTI:
        assert chat_service._get_mbti_group(m) == prompts._get_mbti_group(m)
