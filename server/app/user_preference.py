"""유저 발화 스타일 미러링 — 개인화 되먹임 루프 MVP.

conversation_history의 '유저 턴'만 규칙 기반으로 분석해 '약한 스타일 힌트'를
산출한다. LLM 호출 0 / DB 저장 0 / 매 요청 계산. 콜드스타트(유저 턴 2개 미만)는
생략(None). 캐릭터 성격·말투가 항상 우선이며, 이 힌트는 톤 미세조정에 불과하다.

주의: quality_service._normalize_text 는 비교용으로 ㅋㅋ/ㅎㅎ 자모와 공백을 모두
제거하므로 길이 측정·자모 신호 감지에 부적합하다 → 여기서는 재사용하지 않는다.
"""

import re

# 존댓말 종결(대략): 어미가 요/니다/세요 계열로 끝나면 정중체로 본다.
# 뒤따르는 구두점·물결·자모(ㅋㅎ)는 허용.
_FORMAL_RE = re.compile(
    r"(요|용|죠|니다|니까|세요|십시오|드려요|던가요|나요|가요|세용)[\s.!?~ㅋㅎ]*$"
)

# ㅋㅋ/ㅎㅎ/ㅠㅠ/ㅜㅜ 류 자모 표현
_JAMO_RE = re.compile(r"[ㅋㅎㅠㅜ]")

# 텍스트 이모티콘(^^, :), ;), :D, <3) 및 물결 강조(~)
_EMOTICON_RE = re.compile(r"(\^\^|\^_\^|:\)|:\(|;\)|:D|<3|ㅜ_ㅜ|~)")


def _extract(h, field: str) -> str:
    """HistoryMessage(pydantic) / dict 양쪽에서 필드 안전 추출."""
    if isinstance(h, dict):
        val = h.get(field, "")
    else:
        val = getattr(h, field, "")
    return val or ""


def _user_turns(conversation_history) -> list:
    """유저 역할의 비어있지 않은 발화만 추출."""
    turns = []
    for h in conversation_history or []:
        if _extract(h, "role") == "user":
            content = _extract(h, "content").strip()
            if content:
                turns.append(content)
    return turns


def derive_user_style(conversation_history: list):
    """유저 턴을 규칙 기반으로 분석해 스타일 dict 반환. 유저 턴<2 면 None.

    반환 dict:
      turns:        분석에 사용된 유저 턴 수
      avg_len:      유저 턴 평균 문자 길이
      len_pref:     "short"(<20) | "medium" | "long"(>60)
      formality:    "casual"(존댓말 비율<=0.25) | "formal"(>=0.5) | "mixed"
      uses_jamo:    ㅋㅋ/ㅎㅎ/ㅠㅠ 자모 사용 여부
      uses_emoticon:텍스트 이모티콘/물결 사용 여부
    """
    turns = _user_turns(conversation_history)
    if len(turns) < 2:
        return None

    total = len(turns)
    avg_len = sum(len(t) for t in turns) / total
    if avg_len < 20:
        len_pref = "short"
    elif avg_len > 60:
        len_pref = "long"
    else:
        len_pref = "medium"

    formal_count = sum(1 for t in turns if _FORMAL_RE.search(t))
    formal_ratio = formal_count / total
    if formal_ratio >= 0.5:
        formality = "formal"
    elif formal_ratio <= 0.25:
        formality = "casual"
    else:
        formality = "mixed"

    joined = " ".join(turns)
    uses_jamo = bool(_JAMO_RE.search(joined))
    uses_emoticon = bool(_EMOTICON_RE.search(joined))

    return {
        "turns": total,
        "avg_len": round(avg_len, 1),
        "len_pref": len_pref,
        "formality": formality,
        "uses_jamo": uses_jamo,
        "uses_emoticon": uses_emoticon,
    }


def render_preference_section(style) -> str:
    """스타일 dict를 '약한 힌트' 섹션 텍스트로 변환. style=None 이면 빈 문자열.

    ≤100토큰(한국어 대략 200자 이내) 목표. 필수: 캐릭터 성격·말투 우선 명시.
    """
    if not style:
        return ""

    lines = ["## 상대 말투 참고 (약한 힌트, 강제 아님)"]

    len_pref = style.get("len_pref")
    if len_pref == "short":
        lines.append("- 상대는 짧고 가벼운 메시지를 즐겨 써. 답장을 과하게 길게 늘어뜨리지 마.")
    elif len_pref == "long":
        lines.append("- 상대는 길고 정성스러운 메시지를 써. 성의 있게 충분히 답해줘.")
    else:
        lines.append("- 상대는 보통 길이로 편하게 대화해. 리듬을 맞춰줘.")

    formality = style.get("formality")
    light = style.get("uses_jamo") or style.get("uses_emoticon")
    if formality == "formal" and not light:
        lines.append("- 상대는 정중한 존댓말 톤이야. 너무 가볍게 툭툭 대하지 마.")
    else:
        tone_bits = []
        if formality == "casual":
            tone_bits.append("편한 반말")
        if light:
            tone_bits.append("ㅋㅋ/ㅎㅎ 같은 가벼운 표현")
        if tone_bits:
            lines.append(f"- 상대는 {', '.join(tone_bits)}을 즐겨. 너무 딱딱하게 굴지 마.")

    lines.append("단, 캐릭터 성격과 말투가 항상 우선이야. 이 힌트 때문에 캐릭터 정체성을 바꾸지 마.")
    return "\n".join(lines)
