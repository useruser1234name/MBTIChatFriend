"""app.mbti.get_mbti_group 정본 및 chat_service/prompts 참조 동등성 테스트.

과거 chat_service.py와 prompts.py는 각자 독립적으로 MBTI → 4개 기능
그룹(NT/NF/ST/SF) 분류 함수를 갖고 있었다(로직이 문자 그대로 동일하지
않았음 — chat_service는 세부 분기, prompts는 단순 슬라이싱). S10 리팩토링으로
두 모듈 모두 `app.mbti.get_mbti_group`(chat_service의 엄격한 버전)을 정본으로
참조하도록 통합했다. 이 테스트는 (1) 두 모듈의 `_get_mbti_group`이 정본과
동일한 객체(진짜 통합, 재구현 아님)인지, (2) 16종 전체에서 정본이 기존
기대값 테이블과 정확히 일치하는지를 검증한다.
"""

from app import chat_service
from app import prompts
from app.mbti import get_mbti_group

EXPECTED_GROUPS = {
    "INTJ": "NT", "INTP": "NT", "ENTJ": "NT", "ENTP": "NT",
    "INFJ": "NF", "INFP": "NF", "ENFJ": "NF", "ENFP": "NF",
    "ISTJ": "ST", "ISTP": "ST", "ESTJ": "ST", "ESTP": "ST",
    "ISFJ": "SF", "ISFP": "SF", "ESFJ": "SF", "ESFP": "SF",
}

ALL_MBTI = list(EXPECTED_GROUPS.keys())


def test_mbti_group_classification_equivalent_across_modules():
    """(1) chat_service/prompts의 _get_mbti_group가 재구현이 아니라
    app.mbti.get_mbti_group를 그대로 참조하는지(동일 객체, 진짜 통합)와
    (2) 16종 전체에서 정본 결과가 기존 기대값 테이블과 정확히 일치하는지를
    함께 검증한다."""
    assert chat_service._get_mbti_group is get_mbti_group
    assert prompts._get_mbti_group is get_mbti_group

    mismatches = [
        (m, get_mbti_group(m), expected)
        for m, expected in EXPECTED_GROUPS.items()
        if get_mbti_group(m) != expected
    ]
    assert not mismatches, f"그룹 분류 불일치: {mismatches}"

    for m in ALL_MBTI:
        assert get_mbti_group(m) == EXPECTED_GROUPS[m]
        # 통합 후에도 chat_service/prompts 참조가 정본과 완전히 같은 결과를 낸다.
        assert chat_service._get_mbti_group(m) == get_mbti_group(m)
        assert prompts._get_mbti_group(m) == get_mbti_group(m)
