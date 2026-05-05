"""MBTI 인지 기능 기반 궁합 계산 서비스"""

from typing import List, Tuple


def _get_group(mbti: str) -> str:
    """MBTI 타입에서 인지 기능 그룹 추출 (NT, NF, ST, SF)"""
    if len(mbti) != 4:
        return "NT"
    second = mbti[1]  # S or N
    third = mbti[2]   # T or F
    return f"{second}{third}"


# (그룹1, 그룹2) → (점수, 설명)
# 순서 무관하게 조회 가능하도록 양방향 등록
COMPATIBILITY_MATRIX = {
    ("NT", "NT"): (4, "지적 교류가 활발한 관계"),
    ("NT", "NF"): (5, "논리와 감성의 완벽한 조화"),
    ("NT", "ST"): (3, "실용적이지만 감정 교류가 부족할 수 있음"),
    ("NT", "SF"): (2, "소통 방식이 다를 수 있음"),
    ("NF", "NF"): (4, "깊은 감정적 교감"),
    ("NF", "ST"): (2, "가치관 차이로 갈등 가능"),
    ("NF", "SF"): (4, "따뜻한 감정 교류"),
    ("ST", "ST"): (3, "안정적이지만 변화에 둔감"),
    ("ST", "SF"): (4, "실용적이고 따뜻한 관계"),
    ("SF", "SF"): (5, "조화롭고 헌신적인 관계"),
}

# 그룹별 강점/약점 데이터
_STRENGTHS = {
    ("NT", "NT"): ["깊은 지적 토론 가능", "서로의 아이디어를 발전시킴", "독립성을 존중"],
    ("NT", "NF"): ["논리와 감성의 균형", "서로의 부족한 면을 채워줌", "깊은 대화 가능"],
    ("NT", "ST"): ["목표 지향적 협력", "효율적인 문제 해결", "실용적 관점 공유"],
    ("NT", "SF"): ["다양한 관점 제공", "서로에게서 배울 점이 많음"],
    ("NF", "NF"): ["감정적 교감이 깊음", "서로의 이상을 이해", "따뜻한 소통"],
    ("NF", "ST"): ["서로 다른 시각 제공", "균형 잡힌 의사결정"],
    ("NF", "SF"): ["따뜻한 감정 교류", "서로를 배려하는 관계", "정서적 안정감"],
    ("ST", "ST"): ["안정적이고 신뢰할 수 있는 관계", "실용적 문제 해결", "규칙적인 생활 공유"],
    ("ST", "SF"): ["현실적이면서 따뜻한 관계", "서로를 든든하게 지지", "실질적 도움"],
    ("SF", "SF"): ["헌신적인 관계", "일상의 소소한 행복 공유", "서로를 세심하게 챙김"],
}

_CHALLENGES = {
    ("NT", "NT"): ["감정 표현이 서로 부족할 수 있음", "경쟁심이 생길 수 있음"],
    ("NT", "NF"): ["논리 vs 감정으로 갈등 가능", "의사결정 방식 차이"],
    ("NT", "ST"): ["추상적 vs 구체적 사고 차이", "감정적 소통 부족"],
    ("NT", "SF"): ["소통 방식이 크게 다름", "가치관 차이로 오해 가능", "서로의 세계를 이해하기 어려움"],
    ("NF", "NF"): ["현실적 문제 해결이 약할 수 있음", "감정에 치우칠 수 있음"],
    ("NF", "ST"): ["가치관 차이로 갈등 가능", "소통 방식이 매우 다름", "서로를 이해하기 힘들 수 있음"],
    ("NF", "SF"): ["이상 vs 현실 차이", "깊은 토론이 부족할 수 있음"],
    ("ST", "ST"): ["변화에 둔감할 수 있음", "감정 표현이 부족", "틀에 박힌 관계가 될 수 있음"],
    ("ST", "SF"): ["감정 표현의 깊이 차이", "새로운 경험 시도가 부족할 수 있음"],
    ("SF", "SF"): ["갈등 회피 경향", "새로운 도전이 부족할 수 있음"],
}


def _lookup(group1: str, group2: str) -> Tuple[int, str]:
    """순서 무관하게 궁합 매트릭스 조회"""
    if (group1, group2) in COMPATIBILITY_MATRIX:
        return COMPATIBILITY_MATRIX[(group1, group2)]
    if (group2, group1) in COMPATIBILITY_MATRIX:
        return COMPATIBILITY_MATRIX[(group2, group1)]
    return (3, "보통의 관계")


def _lookup_list(data: dict, group1: str, group2: str) -> List[str]:
    """순서 무관하게 리스트 데이터 조회"""
    if (group1, group2) in data:
        return data[(group1, group2)]
    if (group2, group1) in data:
        return data[(group2, group1)]
    return ["서로를 알아가는 과정이 필요"]


def calculate_compatibility(user_mbti: str, character_mbti: str) -> dict:
    """MBTI 궁합 계산 결과 반환"""
    g1 = _get_group(user_mbti.upper())
    g2 = _get_group(character_mbti.upper())

    score, description = _lookup(g1, g2)
    strengths = _lookup_list(_STRENGTHS, g1, g2)
    challenges = _lookup_list(_CHALLENGES, g1, g2)

    return {
        "score": score,
        "description": f"{user_mbti}와(과) {character_mbti}의 궁합: {description}",
        "strengths": strengths,
        "challenges": challenges,
    }
