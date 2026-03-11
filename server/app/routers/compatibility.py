import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/compatibility", tags=["compatibility"])

_DATA_PATH = Path(__file__).parent.parent / "data" / "compatibility_data.json"
_VALENTINE_PATH = Path(__file__).parent.parent / "data" / "valentine_messages.json"
_GRATITUDE_PATH = Path(__file__).parent.parent / "data" / "gratitude_messages.json"

# 기본 궁합 규칙 (동적 생성용)
_COMPATIBILITY_RULES = {
    # (같은 유형끼리 겹치는 차원)
    ("I", "I"): ("공명형", "내향인의 깊은 이해"),
    ("E", "E"): ("공명형", "에너지 넘치는 만남"),
    ("I", "E"): ("보완형", "고요함과 활기의 균형"),
    ("N", "N"): ("공명형", "직관이 통하는 사이"),
    ("S", "S"): ("안정형", "현실에서 함께 성장"),
    ("N", "S"): ("자극형", "추상과 구체의 만남"),
    ("T", "T"): ("자극형", "논리로 단단해지는 관계"),
    ("F", "F"): ("공명형", "감정이 깊이 공명하는 사이"),
    ("T", "F"): ("보완형", "논리와 감성의 조화"),
    ("J", "J"): ("안정형", "계획 속에서 안심되는 관계"),
    ("P", "P"): ("자극형", "자유로운 탐색의 여정"),
    ("J", "P"): ("보완형", "구조와 유연성의 균형"),
}

_TYPE_DESCRIPTIONS = {
    "보완형": "서로 다른 강점이 맞물려 함께 더 나아지는 조합입니다.",
    "공명형": "비슷한 감수성과 가치관으로 깊이 공명하는 조합입니다.",
    "자극형": "서로를 지적으로 도전하며 성장시키는 조합입니다.",
    "안정형": "서로에게 안전함과 신뢰를 주는 편안한 조합입니다.",
}

_DEFAULT_TIPS = {
    "보완형": ["차이를 단점이 아닌 보완으로 바라봐", "서로의 강점을 적극 활용해", "다름이 이 관계의 힘이야"],
    "공명형": ["너무 비슷해서 서로 의존하지 않도록 주의", "각자의 개성도 소중히 여겨", "깊은 공감이 이 관계의 특별함"],
    "자극형": ["논쟁은 성장을 위한 것, 이기려 하지 않기", "상대의 다른 시각을 존중해", "지적 긴장감을 즐겨봐"],
    "안정형": ["편안함 속에서도 새로운 시도를 해봐", "서로의 필요를 솔직하게 표현해", "안정감이 이 관계의 가장 큰 선물"],
}


def _get_compat_type(mbti_a: str, mbti_b: str) -> tuple[str, str]:
    """MBTI 4글자를 비교해 가장 영향력 있는 차원으로 궁합 유형 결정"""
    pairs = [
        (mbti_a[0], mbti_b[0]),  # I/E
        (mbti_a[1], mbti_b[1]),  # N/S
        (mbti_a[2], mbti_b[2]),  # T/F
        (mbti_a[3], mbti_b[3]),  # J/P
    ]
    # T/F 차원이 감정적 궁합에 가장 큰 영향
    tf_pair = tuple(sorted([mbti_a[2], mbti_b[2]]))
    return _COMPATIBILITY_RULES.get(tf_pair, ("보완형", "서로에게 배우는 관계"))


with open(_DATA_PATH, encoding="utf-8") as f:
    _CURATED_DATA: dict = json.load(f)

with open(_VALENTINE_PATH, encoding="utf-8") as f:
    VALENTINE_MESSAGES: dict = json.load(f)

with open(_GRATITUDE_PATH, encoding="utf-8") as f:
    GRATITUDE_MESSAGES: dict = json.load(f)


@router.get("/valentine/{mbti}")
async def get_valentine_message(mbti: str):
    """인증 불필요 — 발렌타인 MBTI 메시지"""
    msg = VALENTINE_MESSAGES.get(mbti.upper())
    if not msg:
        raise HTTPException(404)
    return {"mbti": mbti.upper(), "message": msg}


@router.get("/gratitude/{mbti}")
async def get_gratitude_message(mbti: str):
    """가정의 달 MBTI별 감사 메시지 (인증 불필요)"""
    msg = GRATITUDE_MESSAGES.get(mbti.upper())
    if not msg:
        raise HTTPException(404)
    return {"mbti": mbti.upper(), "message": msg}


@router.get("/all-complete/{mbti}")
async def get_all_complete_message(mbti: str):
    """16종 완성 기념 카드 메시지 (37차 스프린트)"""
    return {
        "mbti": mbti.upper(),
        "message": f"이제 {mbti.upper()} 친구를 포함해 16가지 MBTI 친구가 모두 생겼어요!",
        "all_mbti": ["ENFP", "INFJ", "INTJ", "ISFJ", "INFP", "ENTP", "ESTJ", "ISFP",
                     "INTP", "ESFP", "ENTJ", "ISTJ", "ESTP", "ENFJ", "ESFJ", "ISTP"],
    }


@router.get("/summer/{mbti}")
async def get_summer_message(mbti: str):
    """여름 시즌 MBTI별 메시지 (34차 스프린트)"""
    messages = {
        "ENFP": "이 여름, 네 에너지가 제일 빛나는 계절이야!",
        "INFJ": "조용한 여름 밤, 깊은 생각들이 꽃피는 계절이야.",
        "INTJ": "혼자만의 여름 계획, 완벽하게 실행해봐.",
        "ISFJ": "이 여름, 소중한 사람들과의 기억을 하나씩 쌓아봐.",
        "INFP": "여름의 감성 속에서 진짜 나를 찾아봐.",
        "ENTP": "이 여름, 새로운 아이디어와 모험이 기다리고 있어!",
        "ESTJ": "계획적인 여름 목표, 하나씩 달성해나가자!",
        "ISFP": "이 여름, 순간순간의 아름다움을 느껴봐.",
        "INTP": "여름의 긴 낮 동안 깊이 탐구할 주제를 찾아봐.",
        "ESFP": "이 여름, 매 순간을 즐겁게 살아봐!",
        "ENTJ": "이 여름, 큰 목표를 향해 전력질주해봐!",
        "ISTJ": "착실한 여름 루틴으로 알차게 보내봐.",
        "ESTP": "이 여름, 짜릿한 도전이 기다리고 있어!",
        "ENFJ": "이 여름, 소중한 사람들에게 따뜻함을 전해봐.",
        "ESFJ": "이 여름, 모두가 행복한 시간을 만들어봐!",
        "ISTP": "이 여름, 혼자만의 조용한 모험을 즐겨봐.",
    }
    return {
        "summer_message": messages.get(mbti.upper(), "이 여름을 특별하게 만들어봐!"),
        "mbti": mbti.upper(),
    }


@router.get("/{mbti_a}/{mbti_b}")
async def get_compatibility(mbti_a: str, mbti_b: str):
    a = mbti_a.upper()
    b = mbti_b.upper()
    if len(a) != 4 or len(b) != 4:
        raise HTTPException(400, "Invalid MBTI format")

    key = f"{a}_{b}"
    reverse_key = f"{b}_{a}"

    # 큐레이션 데이터 우선
    data = _CURATED_DATA.get(key) or _CURATED_DATA.get(reverse_key)
    if data:
        return {"mbti_a": a, "mbti_b": b, **data}

    # 동적 생성
    compat_type, title = _get_compat_type(a, b)
    description = _TYPE_DESCRIPTIONS.get(compat_type, "서로에게 배우는 특별한 관계입니다.")
    tips = _DEFAULT_TIPS.get(compat_type, ["서로를 이해하는 시간을 가져봐", "차이를 존중해", "함께 성장해나가자"])

    return {
        "mbti_a": a,
        "mbti_b": b,
        "type": compat_type,
        "title": title,
        "description": description,
        "tips": tips,
    }
