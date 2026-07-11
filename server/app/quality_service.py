"""실시간 응답 품질 평가 서비스.

fire-and-forget 방식으로 응답 전송 후 백그라운드에서 품질 점수를 산출하고,
응답 다양성을 추적하며, 파인튜닝용 학습 데이터 필터링을 제공한다.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, LLM_MODEL_SIMPLE, MAX_MESSAGE_LENGTH
from .metrics_service import record_event
from .models import VALID_EMOTIONS
from .postgres import fetchall, fetchone, postgres_enabled

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ── 실시간 비동기 품질 평가 ──────────────────────────────────────


async def score_response_async(
    user_msg: str,
    ai_response: str,
    mbti: str,
    affinity_level: int,
    room_id: str = "",
    character_id: str = "",
) -> Optional[Dict[str, Any]]:
    """gpt-4.1-mini 를 사용해 응답 품질 4가지 축을 0-10으로 평가.

    반환: {"mbti_consistency", "contextual_relevance",
           "emotional_naturalness", "engagement_quality",
           "quality_score"} 또는 실패 시 None
    """
    if not _client:
        return None

    quality_issues = classify_quality_issues(user_msg, ai_response)

    prompt = (
        f"아래 대화에서 AI 캐릭터({mbti}, 호감도 {affinity_level}/5)의 응답 품질을 평가해.\n"
        f"사용자: \"{user_msg}\"\n"
        f"AI: \"{ai_response}\"\n\n"
        "4가지 항목을 각각 0-10 정수로 평가하고 JSON만 출력:\n"
        '{"mbti_consistency":0,"contextual_relevance":0,'
        '"emotional_naturalness":0,"engagement_quality":0}'
    )

    try:
        resp = await _client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
            timeout=20,
        )
        content = resp.choices[0].message.content or ""
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            return None

        data = json.loads(content[start:end])
        mc = _clamp(data.get("mbti_consistency", 5))
        cr = _clamp(data.get("contextual_relevance", 5))
        en = _clamp(data.get("emotional_naturalness", 5))
        eq = _clamp(data.get("engagement_quality", 5))
        quality_score = round(0.3 * mc + 0.3 * cr + 0.2 * en + 0.2 * eq, 2)

        result = {
            "mbti_consistency": mc,
            "contextual_relevance": cr,
            "emotional_naturalness": en,
            "engagement_quality": eq,
            "quality_score": quality_score,
            "quality_issues": quality_issues,
            "ai_response": ai_response,
        }

        # metric_events 에 저장
        record_event(
            event_type="quality_score",
            room_id=room_id,
            character_id=character_id,
            payload=result,
        )
        return result

    except Exception as e:
        logger.warning(f"품질 평가 실패: {e}")
        return None


# ── 빠른 품질 체크 (응답 전 게이트) ──────────────────────────────


_VALID_EMOTIONS = VALID_EMOTIONS


def classify_quality_issues(user_msg: str, ai_response: str) -> List[str]:
    """Classify low-cost response quality issues without calling an LLM."""
    issues: List[str] = []
    try:
        clean = re.sub(r'```json?\s*', '', ai_response)
        clean = re.sub(r'```\s*', '', clean).strip()
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start < 0 or end <= start:
            return ["JSON_INVALID"]

        data = json.loads(clean[start:end])
        if not isinstance(data, list) or len(data) == 0:
            return ["EMPTY_REPLY"]

        if not all(isinstance(d, dict) and d.get("text") for d in data):
            issues.append("MISSING_TEXT")

        emotions = [d.get("emotion") for d in data if isinstance(d, dict)]
        if not emotions or any(e not in _VALID_EMOTIONS for e in emotions):
            issues.append("EMOTION_INVALID")

        texts = [d.get("text", "") for d in data if isinstance(d, dict)]
        nonblank = [t for t in texts if t and t.strip()]
        if len(nonblank) < len(texts):
            issues.append("EMPTY_TEXT")

        total_len = sum(len(t) for t in texts)
        if total_len < 2:
            issues.append("TOO_SHORT")
        if total_len > MAX_MESSAGE_LENGTH:
            issues.append("TOO_LONG")

        normalized = [n for n in (_normalize_text(t) for t in texts) if n]
        if len(normalized) >= 2 and len(set(normalized)) < len(normalized):
            issues.append("REPEATED_TEXT")

        if len(emotions) >= 2 and len(set(emotions)) == 1:
            issues.append("MONOTONE_EMOTION")

        user_norm = _normalize_text(user_msg or "")
        if user_norm and len(user_norm) >= 3:
            for n in normalized:
                if n == user_norm or (user_norm in n and len(user_norm) >= 0.7 * len(n)):
                    issues.append("ECHO_USER")
                    break

        return issues
    except (json.JSONDecodeError, Exception):
        return ["JSON_INVALID"]


def _normalize_text(s: str) -> str:
    """비교용 정규화: 소문자, 공백/구두점/이모지 제거."""
    s = s.lower()
    # 한글/영문/숫자만 남기고 나머지(공백, 구두점, 이모지, ㅋㅋ 류 자모) 제거
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def quick_score(user_msg: str, ai_response: str, mbti: str) -> float:
    """응답 전 빠른 품질 체크 (LLM 호출 없이 ~1ms). 0.0~1.0 반환.

    1) JSON 배열 형식/emotion 코드/길이 유효성 (기존 동작 유지)
    2) 저비용 휴리스틱 감점 (LLM 미호출):
       - 동일/거의 동일 문장 반복
       - 모든 emotion 단조로움 (전부 동일)
       - 사용자 메시지 그대로 에코
       - 빈/공백만 있는 reply
    MBTI 일관성은 _post_response_quality_check에서 비동기 처리.
    """
    issues = classify_quality_issues(user_msg, ai_response)
    if "JSON_INVALID" in issues:
        return 0.1
    if "EMPTY_REPLY" in issues:
        return 0.2
    if "MISSING_TEXT" in issues:
        return 0.3

    # ── 1) JSON 배열 형식 검증 (LLM 불필요) ──
    try:
        clean = re.sub(r'```json?\s*', '', ai_response)
        clean = re.sub(r'```\s*', '', clean).strip()
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start < 0 or end <= start:
            return 0.1

        data = json.loads(clean[start:end])
        if not isinstance(data, list) or len(data) == 0:
            return 0.2

        # emotion 필드 유효성 체크
        has_valid_emotion = "EMOTION_INVALID" not in issues

        # 텍스트 길이 합리성 (너무 짧거나 너무 긴 응답 감점)
        texts = [d.get("text", "") for d in data if isinstance(d, dict)]
        total_len = sum(len(t) for t in texts)
        length_ok = 2 <= total_len <= MAX_MESSAGE_LENGTH

        # ── 형식 기반 base score (기존 0.5~1.0 스케일 유지) ──
        if has_valid_emotion and length_ok:
            base = 1.0
        elif has_valid_emotion:
            base = 0.8
        elif length_ok:
            base = 0.7
        else:
            base = 0.5

        # ── 2) 저비용 휴리스틱 감점 ──
        penalty = 0.0

        # (a) 빈/공백만 있는 reply 감점
        if "EMPTY_TEXT" in issues:
            penalty += 0.3

        normalized = [n for n in (_normalize_text(t) for t in texts) if n]

        # (b) 동일/거의 동일 문장 반복 감지
        if "REPEATED_TEXT" in issues and normalized:
            unique = set(normalized)
            dup_ratio = 1.0 - (len(unique) / len(normalized))
            penalty += min(0.3, 0.3 * dup_ratio + 0.1)

        # (c) 모든 emotion 단조로움 (2개 이상인데 전부 동일) — 소폭 감점
        if "MONOTONE_EMOTION" in issues:
            penalty += 0.05

        # (d) 사용자 메시지 그대로 에코 감점
        if "ECHO_USER" in issues:
            penalty += 0.3

        score = base - penalty
        # 0.0~1.0 클램프, JSON 형식은 통과했으므로 최저 0.1 보장(파싱불가와 구분)
        return round(max(0.1, min(1.0, score)), 3)

    except (json.JSONDecodeError, Exception):
        return 0.1


# ── 응답 다양성 추적 ─────────────────────────────────────────────


def _bigrams(text: str) -> List[Tuple[str, str]]:
    tokens = text.split()
    return list(zip(tokens, tokens[1:])) if len(tokens) >= 2 else []


def _scope_filter(room_id: str, character_id: str) -> Tuple[str, Tuple[Any, ...]]:
    scoped_room_id = (room_id or "").strip()
    if scoped_room_id:
        return "room_id = %s", (scoped_room_id,)
    return "character_id = %s", (character_id,)


def check_diversity(
    character_id: str,
    new_response: str,
    room_id: str = "",
    n_recent: int = 20,
) -> float:
    """최근 n_recent 개 응답과 bigram 겹침 비율을 계산해 diversity_score 반환.

    1.0 = 완전히 새로움, 0.0 = 완전 중복.
    score < 0.3 이면 low_diversity_warning 이벤트를 기록한다.
    """
    if not postgres_enabled():
        return 1.0

    scope_sql, scope_params = _scope_filter(room_id, character_id)
    rows = fetchall(
        f"""
        SELECT payload->>'ai_response' AS resp
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND {scope_sql}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        scope_params + (n_recent,),
    )

    if not rows:
        return 1.0

    past_texts = [r["resp"] for r in rows if r.get("resp")]
    if not past_texts:
        return 1.0

    new_bg = set(_bigrams(new_response))
    if not new_bg:
        return 1.0

    overlap_ratios: List[float] = []
    for past in past_texts:
        past_bg = set(_bigrams(past))
        if not past_bg:
            continue
        overlap = len(new_bg & past_bg)
        ratio = overlap / len(new_bg)
        overlap_ratios.append(ratio)

    if not overlap_ratios:
        return 1.0

    avg_overlap = sum(overlap_ratios) / len(overlap_ratios)
    diversity_score = round(1.0 - avg_overlap, 3)

    if diversity_score < 0.3:
        record_event(
            event_type="low_diversity_warning",
            room_id=room_id,
            character_id=character_id,
            payload={
                "diversity_score": diversity_score,
                "recent_count": len(past_texts),
            },
        )

    return diversity_score


# ── 품질 기반 학습 데이터 필터링 ──────────────────────────────────


def get_quality_filtered_conversations(
    character_id: str,
    room_id: str = "",
    min_score: float = 0.6,
) -> List[Dict[str, Any]]:
    """quality_score >= min_score AND thumbs_down 아닌 대화만 반환."""
    if not postgres_enabled():
        return []

    # 1) 저품질 room_id + message_id 수집 (quality_score < min_score)
    # 2) thumbs_down 받은 message_id 수집
    # 3) 나머지만 반환

    # 3개 쿼리를 1개 통합 쿼리로: thumbs_down 받지 않고 quality_score >= min_score인 room_id만 반환
    scope_sql, scope_params = _scope_filter(room_id, character_id)
    rows = fetchall(
        f"""
        SELECT me.room_id,
               (me.payload->>'quality_score')::float AS qs
        FROM metric_events me
        WHERE me.event_type = 'quality_score'
          AND me.{scope_sql}
          AND (me.payload->>'quality_score')::float >= %s
          AND me.room_id NOT IN (
              SELECT DISTINCT room_id
              FROM response_feedback
              WHERE {scope_sql}
                AND feedback_type = 'thumbs_down'
          )
        """,
        scope_params + (min_score,) + scope_params,
    )

    return [
        {"room_id": r["room_id"], "quality_score": r["qs"]}
        for r in rows
    ]


# ── 품질 대시보드 집계 ───────────────────────────────────────────


def get_quality_dashboard(
    character_id: str,
    days: int = 30,
    room_id: str = "",
) -> Dict[str, Any]:
    """character_id 에 대한 품질 대시보드 데이터를 집계."""
    empty = {
        "avg_quality_score": 0.0,
        "avg_mbti_consistency": 0.0,
        "avg_contextual_relevance": 0.0,
        "avg_emotional_naturalness": 0.0,
        "avg_engagement_quality": 0.0,
        "avg_diversity_score": 0.0,
        "total_turns": 0,
        "thumbs_up_count": 0,
        "thumbs_down_count": 0,
        "thumbs_up_rate": 0.0,
        "quality_trend": [],
    }

    if not postgres_enabled():
        return empty

    # 품질 점수 집계
    scope_sql, scope_params = _scope_filter(room_id, character_id)

    agg = fetchone(
        f"""
        SELECT
            COALESCE(AVG((payload->>'quality_score')::float), 0) AS avg_qs,
            COALESCE(AVG((payload->>'mbti_consistency')::float), 0) AS avg_mc,
            COALESCE(AVG((payload->>'contextual_relevance')::float), 0) AS avg_cr,
            COALESCE(AVG((payload->>'emotional_naturalness')::float), 0) AS avg_en,
            COALESCE(AVG((payload->>'engagement_quality')::float), 0) AS avg_eq,
            COUNT(*) AS total
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND {scope_sql}
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        """,
        scope_params + (days,),
    )

    # 다양성 점수 평균
    div_agg = fetchone(
        f"""
        SELECT COALESCE(AVG((payload->>'diversity_score')::float), 0) AS avg_div
        FROM metric_events
        WHERE event_type = 'low_diversity_warning'
          AND {scope_sql}
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        """,
        scope_params + (days,),
    )

    # 피드백 카운트
    fb = fetchone(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN feedback_type = 'thumbs_up' THEN 1 ELSE 0 END), 0) AS up,
            COALESCE(SUM(CASE WHEN feedback_type = 'thumbs_down' THEN 1 ELSE 0 END), 0) AS down
        FROM response_feedback
        WHERE {scope_sql}
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        """,
        scope_params + (days,),
    )

    # 일별 추이
    trend_rows = fetchall(
        f"""
        SELECT
            DATE(created_at) AS d,
            AVG((payload->>'quality_score')::float) AS avg_score
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND {scope_sql}
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        GROUP BY DATE(created_at)
        ORDER BY d
        """,
        scope_params + (days,),
    )

    total_turns = (agg or {}).get("total", 0)
    up_count = (fb or {}).get("up", 0)
    down_count = (fb or {}).get("down", 0)
    total_fb = up_count + down_count

    return {
        "avg_quality_score": round((agg or {}).get("avg_qs", 0), 2),
        "avg_mbti_consistency": round((agg or {}).get("avg_mc", 0), 2),
        "avg_contextual_relevance": round((agg or {}).get("avg_cr", 0), 2),
        "avg_emotional_naturalness": round((agg or {}).get("avg_en", 0), 2),
        "avg_engagement_quality": round((agg or {}).get("avg_eq", 0), 2),
        "avg_diversity_score": round((div_agg or {}).get("avg_div", 0), 2),
        "total_turns": total_turns,
        "thumbs_up_count": up_count,
        "thumbs_down_count": down_count,
        "thumbs_up_rate": round(up_count / total_fb, 3) if total_fb > 0 else 0.0,
        "quality_trend": [
            {"date": str(r["d"]), "avg_score": round(r["avg_score"], 2)}
            for r in trend_rows
        ],
    }


# ── 다양성 리포트 ────────────────────────────────────────────────


def get_diversity_report(character_id: str, room_id: str = "") -> Dict[str, Any]:
    """최근 다양성 경고 이벤트 기반 리포트."""
    if not postgres_enabled():
        return {"warnings": [], "avg_diversity": 1.0}

    scope_sql, scope_params = _scope_filter(room_id, character_id)
    rows = fetchall(
        f"""
        SELECT payload, created_at
        FROM metric_events
        WHERE event_type = 'low_diversity_warning'
          AND {scope_sql}
        ORDER BY created_at DESC
        LIMIT 20
        """,
        scope_params,
    )

    if not rows:
        return {"warnings": [], "avg_diversity": 1.0}

    scores = [r["payload"].get("diversity_score", 1.0) for r in rows]
    return {
        "warnings": [
            {
                "diversity_score": r["payload"].get("diversity_score"),
                "recent_count": r["payload"].get("recent_count"),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "avg_diversity": round(sum(scores) / len(scores), 3),
    }


# ── helpers ──────────────────────────────────────────────────────


def _clamp(v: Any, lo: int = 0, hi: int = 10) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 5
