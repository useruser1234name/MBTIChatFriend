"""콘텐츠 필터링 모듈 - 유해 콘텐츠 감지 및 차단"""

import re
from typing import Tuple

# 금칙어 패턴 (기본)
BLOCKED_PATTERNS = [
    # 성적 표현 패턴
    r"(?i)(sex|porn|nude|naked|야동|야사|섹스|성관계|강간)",
    # 폭력적 표현
    r"(?i)(죽여|죽일|살인|자살|테러)",
    # 혐오 표현
    r"(?i)(시발|씨발|병신|장애인|느금마)",
]

COMPILED_PATTERNS = [re.compile(p) for p in BLOCKED_PATTERNS]


def check_content(text: str) -> Tuple[bool, str]:
    """
    콘텐츠 필터링 체크
    Returns: (is_safe, reason)

    TODO: 테스트 모드 - 필터 비활성화. 프로덕션 배포 시 원래 로직 복원 필요.
    """
    # for pattern in COMPILED_PATTERNS:
    #     if pattern.search(text):
    #         return False, "부적절한 표현이 감지되었습니다."

    return True, ""


def get_safety_system_prompt() -> str:
    """AI 응답 안전 가이드라인 시스템 프롬프트

    TODO: 테스트 모드 - safety prompt 비활성화. 프로덕션 배포 시 원래 프롬프트 복원 필요.
    """
    return ""
