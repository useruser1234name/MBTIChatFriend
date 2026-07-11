"""LLM 응답에서 JSON 블록을 슬라이싱으로 추출하는 공용 헬퍼.

여러 곳(chat_service.py, quality_service.py, memory_service.py)에서
`content.find("{") / content.rfind("}") + 1` (및 `[`/`]` 변형) 패턴이
반복되어 단일 지점으로 통합했다. 슬라이싱 부분만 대체하며, 호출부의
json.loads try/except·폴백 동작은 그대로 유지한다.
"""

from __future__ import annotations

from typing import Optional


def extract_json_object(content: str) -> Optional[str]:
    """content에서 첫 `{`부터 마지막 `}`까지의 부분 문자열을 반환.

    유효한 범위가 없으면(중괄호가 없거나 순서가 뒤바뀐 경우) None을 반환한다.
    """
    start = content.find("{")
    end = content.rfind("}") + 1
    return content[start:end] if start >= 0 and end > start else None


def extract_json_array(content: str) -> Optional[str]:
    """content에서 첫 `[`부터 마지막 `]`까지의 부분 문자열을 반환.

    유효한 범위가 없으면(대괄호가 없거나 순서가 뒤바뀐 경우) None을 반환한다.
    """
    start = content.find("[")
    end = content.rfind("]") + 1
    return content[start:end] if start >= 0 and end > start else None
