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
