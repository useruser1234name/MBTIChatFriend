"""MBTI 4개 기능 그룹(NT/NF/ST/SF) 분류 정본.

과거 `chat_service.py`, `prompts.py`(모듈 레벨 + `get_compatibility_description`
내부 중첩 함수)에 각기 다른 구현이 3중으로 존재했다. 유효한 16개 MBTI
유형에서는 모두 동치이나(tests/test_mbti_group_equivalence.py가 증명)
비정상 입력 처리 방식이 서로 달랐다. 여기서는 그중 가장 엄격한
chat_service 버전을 정본으로 삼는다.

이 모듈은 다른 app 모듈을 임포트하지 않는 중립 모듈이므로
chat_service.py / prompts.py 양쪽에서 순환 임포트 없이 가져다 쓸 수 있다.
"""

from __future__ import annotations


def get_mbti_group(mbti: str) -> str:
    """MBTI를 4개 기능 그룹으로 분류 (NT/NF/ST/SF)."""
    if len(mbti) != 4:
        return "NF"
    if mbti[1] == "N" and mbti[2] == "T":
        return "NT"
    elif mbti[1] == "N" and mbti[2] == "F":
        return "NF"
    elif mbti[1] == "S" and mbti[2:4] in ("TJ", "TP"):
        return "ST"
    else:
        return "SF"


# ── 첫인사 감정 매핑 (C2) ────────────────────────────────────────────────
# get_mbti_group의 NT/NF/ST/SF 4그룹과는 다른 축(E/I × J/P 또는 F/T)의
# 별도 분류다 — 재사용 목적(C6에서도 쓸 예정)으로 이 중립 모듈에 둔다.
# 값은 반드시 models.VALID_EMOTIONS의 코드와 일치해야 한다.
GREETING_EMOTION_MAP: dict[str, str] = {
    # 외향 인식형(E**P) → PLAYFUL
    "ENFP": "PLAYFUL", "ESFP": "PLAYFUL", "ESTP": "PLAYFUL", "ENTP": "PLAYFUL",
    # 외향 판단형(E**J) → HAPPY
    "ENFJ": "HAPPY", "ESFJ": "HAPPY", "ENTJ": "HAPPY", "ESTJ": "HAPPY",
    # 내향 감정형(I**F) → SHY
    "INFP": "SHY", "ISFP": "SHY", "INFJ": "SHY", "ISFJ": "SHY",
    # 내향 사고형(I**T) → NEUTRAL
    "INTJ": "NEUTRAL", "INTP": "NEUTRAL", "ISTJ": "NEUTRAL", "ISTP": "NEUTRAL",
}

_DEFAULT_GREETING_EMOTION = "NEUTRAL"


def get_greeting_emotion(mbti: str) -> str:
    """MBTI 유형별 첫인사 감정 코드 반환 (C2, C6 재사용 예정).

    16종 유효 MBTI는 GREETING_EMOTION_MAP에 고정 매핑되어 있다(대소문자
    무관, 내부에서 upper() 정규화). 유효하지 않거나 알 수 없는 입력은
    기본값 NEUTRAL로 안전하게 폴백한다. 반환값은 models.VALID_EMOTIONS의
    코드와 항상 일치한다(NEUTRAL/HAPPY/SHY/PLAYFUL 중 하나).
    """
    return GREETING_EMOTION_MAP.get((mbti or "").strip().upper(), _DEFAULT_GREETING_EMOTION)
