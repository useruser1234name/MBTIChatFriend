"""콘텐츠 필터링 모듈 - 유해 콘텐츠 감지 및 차단"""

import hashlib
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ── 금칙어 패턴 ──────────────────────────────────────────────

BLOCKED_PATTERNS = [
    # 성적 표현 패턴
    r"(?i)(sex|porn|nude|naked|야동|야사|섹스|성관계|강간|자위|오르가즘|포르노|음란)",
    # 폭력적 표현 (자살/자해는 위기 감지로 분리)
    r"(?i)(죽여|죽일|살인|테러|칼빵|폭행|폭파)",
    # 혐오 표현
    r"(?i)(시발|씨발|병신|느금마|니거|한남충|한녀충|틀딱|급식충)",
]

COMPILED_PATTERNS = [re.compile(p) for p in BLOCKED_PATTERNS]

# ── 위기 키워드 (차단 대신 개입 응답) ─────────────────────────

CRISIS_KEYWORDS_TIER1 = [
    r"자살", r"죽고\s*싶", r"죽을래", r"자해", r"목숨",
    r"목매", r"손목", r"약\s*먹고", r"뛰어내", r"유서",
]

CRISIS_KEYWORDS_TIER2 = [
    r"살기\s*싫", r"의미\s*없", r"포기하고\s*싶",
    r"아무도\s*없", r"끝내고\s*싶", r"힘들어\s*못\s*참",
]

COMPILED_CRISIS_T1 = [re.compile(p) for p in CRISIS_KEYWORDS_TIER1]
COMPILED_CRISIS_T2 = [re.compile(p) for p in CRISIS_KEYWORDS_TIER2]

# ── 허용 목록 (오탐 방지) ────────────────────────────────────

ALLOWLIST_PATTERNS = [
    r"죽여주[는다]?\s*(맛|연기|노래|음식)",  # "죽여주는 맛"
    r"(소설|영화|드라마|게임|뉴스)에서",      # 미디어 맥락
    r"살인\s*사건\s*(뉴스|기사|드라마)",       # 뉴스/미디어 맥락
]

COMPILED_ALLOWLIST = [re.compile(p) for p in ALLOWLIST_PATTERNS]

# ── 위기 키워드 허용 목록 (오탐 방지) ─────────────────────────
CRISIS_ALLOWLIST_PATTERNS = [
    r"약\s*먹고\s*(자|잘|잠)",       # "약 먹고 자고 싶어" (수면 맥락)
    r"손목\s*시계",                   # "손목시계"
    r"목매\s*(는|인)\s*(드라마|영화|소설)",  # 미디어 맥락
]

COMPILED_CRISIS_ALLOWLIST = [re.compile(p) for p in CRISIS_ALLOWLIST_PATTERNS]

# ── 위기 개입 메시지 ─────────────────────────────────────────

CRISIS_RESPONSE_TIER1 = (
    "정말 힘든 시간을 보내고 계시는군요. 혼자 감당하지 않아도 돼요.\n\n"
    "📞 자살예방상담전화 1393 (24시간)\n"
    "📞 정신건강위기상담전화 1577-0199\n"
    "💬 카카오톡 '마음이음' (24시간 채팅상담)\n\n"
    "전문 상담사가 도움을 줄 수 있어요."
)

CRISIS_RESPONSE_TIER2 = (
    "많이 힘든 것 같아서 걱정돼요. 괜찮으세요?\n"
    "혹시 도움이 필요하시면, 전문 상담도 받을 수 있어요.\n\n"
    "📞 정신건강위기상담전화 1577-0199\n"
    "💬 카카오톡 '마음이음' (24시간 채팅상담)"
)


def _is_allowlisted(text: str) -> bool:
    """허용 목록에 해당하는지 확인 (오탐 방지)"""
    for pattern in COMPILED_ALLOWLIST:
        if pattern.search(text):
            return True
    return False


def _is_crisis_allowlisted(text: str) -> bool:
    """위기 키워드 오탐 허용 목록 확인"""
    for pattern in COMPILED_CRISIS_ALLOWLIST:
        if pattern.search(text):
            return True
    return False


def check_crisis(text: str) -> Tuple[bool, int, str]:
    """
    위기 키워드 감지.
    Returns: (is_crisis, tier, intervention_message)
      - tier 1: 즉시 위기상담 안내
      - tier 2: 부드러운 확인 + 상담 안내
    """
    if _is_crisis_allowlisted(text):
        return False, 0, ""

    msg_hash = hashlib.sha256(text.encode()).hexdigest()[:12]

    for pattern in COMPILED_CRISIS_T1:
        if pattern.search(text):
            logger.warning(f"Crisis keyword detected (tier1) msg_hash={msg_hash} len={len(text)}")
            return True, 1, CRISIS_RESPONSE_TIER1

    for pattern in COMPILED_CRISIS_T2:
        if pattern.search(text):
            logger.info(f"Crisis keyword detected (tier2) msg_hash={msg_hash} len={len(text)}")
            return True, 2, CRISIS_RESPONSE_TIER2

    return False, 0, ""


def check_content(text: str) -> Tuple[bool, str]:
    """
    콘텐츠 필터링 체크.
    Returns: (is_safe, reason)
    """
    if _is_allowlisted(text):
        return True, ""

    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            logger.info(f"Content blocked by filter")
            return False, "부적절한 표현이 감지되었습니다."

    return True, ""


def get_safety_system_prompt() -> str:
    """AI 응답 안전 가이드라인 시스템 프롬프트.

    NOTE: AI 정체성 관련 지시는 prompts.py의 '역할 설정' 블록에서 통합 관리.
    여기서는 안전 관련 규칙만 포함.
    """
    return (
        "\n[안전 가이드라인]\n"
        "- 폭력, 자해, 자살을 조장하거나 구체적 방법을 알려주지 않는다.\n"
        "- 성적으로 노골적인 콘텐츠를 생성하지 않는다.\n"
        "- 혐오 발언이나 차별적 표현을 사용하지 않는다.\n"
        "- 사용자가 위기 상황(자해/자살 암시)을 보이면, "
        "공감하면서 전문 상담 리소스(1393, 1577-0199)를 안내한다.\n"
    )
