"""실시간 응답 품질 평가 서비스.

fire-and-forget 방식으로 응답 전송 후 백그라운드에서 품질 점수를 산출하고,
응답 다양성을 추적하며, 파인튜닝용 학습 데이터 필터링을 제공한다.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY
from .metrics_service import record_event
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
    """gpt-4o-mini 를 사용해 응답 품질 4가지 축을 0-10으로 평가.

    반환: {"mbti_consistency", "contextual_relevance",
           "emotional_naturalness", "engagement_quality",
           "quality_score"} 또는 실패 시 None
    """
    if not _client:
        return None

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
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
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


async def quick_score(user_msg: str, ai_response: str, mbti: str) -> float:
    """응답 전 빠른 품질 체크 (~100ms). 0.0~1.0 반환.

    JSON 형식 유효성 + MBTI 일관성만 빠르게 확인.
    """
    if not _client:
        return 1.0  # 클라이언트 없으면 통과

    # 1. 기본 형식 체크 (LLM 없이)
    format_score = 0.5
    try:
        # JSON 배열 파싱 가능한지 확인
        import re as _re
        clean = _re.sub(r'```json?\s*', '', ai_response)
        clean = _re.sub(r'```\s*', '', clean).strip()
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(clean[start:end])
            if isinstance(data, list) and len(data) > 0:
                has_text = all(isinstance(d, dict) and d.get("text") for d in data)
                format_score = 1.0 if has_text else 0.3
            else:
                format_score = 0.2
        else:
            format_score = 0.1
    except (json.JSONDecodeError, Exception):
        format_score = 0.1

    # 형식이 매우 나쁘면 바로 반환 (LLM 호출 절약)
    if format_score < 0.2:
        return format_score

    # 2. LLM으로 MBTI 일관성 빠르게 확인
    try:
        prompt = (
            f"{mbti} 캐릭터의 응답이 자연스러운지 0-10으로 평가.\n"
            f"사용자: \"{user_msg[:100]}\"\nAI: \"{ai_response[:200]}\"\n"
            'JSON만: {"score": 0}'
        )
        resp = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=30,
        )
        content = resp.choices[0].message.content or ""
        s = content.find("{")
        e = content.rfind("}") + 1
        if s >= 0 and e > s:
            data = json.loads(content[s:e])
            llm_score = _clamp(data.get("score", 5)) / 10.0
        else:
            llm_score = 0.5
    except Exception:
        llm_score = 0.5

    # 가중 평균: 형식 40% + MBTI 일관성 60%
    return round(format_score * 0.4 + llm_score * 0.6, 2)


# ── 응답 다양성 추적 ─────────────────────────────────────────────


def _bigrams(text: str) -> List[Tuple[str, str]]:
    tokens = text.split()
    return list(zip(tokens, tokens[1:])) if len(tokens) >= 2 else []


def check_diversity(
    character_id: str,
    new_response: str,
    n_recent: int = 20,
) -> float:
    """최근 n_recent 개 응답과 bigram 겹침 비율을 계산해 diversity_score 반환.

    1.0 = 완전히 새로움, 0.0 = 완전 중복.
    score < 0.3 이면 low_diversity_warning 이벤트를 기록한다.
    """
    if not postgres_enabled():
        return 1.0

    rows = fetchall(
        """
        SELECT payload->>'ai_response' AS resp
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND character_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (character_id, n_recent),
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
    min_score: float = 0.6,
) -> List[Dict[str, Any]]:
    """quality_score >= min_score AND thumbs_down 아닌 대화만 반환."""
    if not postgres_enabled():
        return []

    # 1) 저품질 room_id + message_id 수집 (quality_score < min_score)
    # 2) thumbs_down 받은 message_id 수집
    # 3) 나머지만 반환

    quality_rows = fetchall(
        """
        SELECT room_id,
               (payload->>'quality_score')::float AS qs
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND character_id = %s
        """,
        (character_id,),
    )

    low_quality_rooms = {
        r["room_id"] for r in quality_rows if (r.get("qs") or 0) < min_score
    }

    thumbs_down_rows = fetchall(
        """
        SELECT DISTINCT room_id
        FROM response_feedback
        WHERE character_id = %s AND feedback_type = 'thumbs_down'
        """,
        (character_id,),
    )
    thumbs_down_rooms = {r["room_id"] for r in thumbs_down_rows}

    excluded_rooms = low_quality_rooms | thumbs_down_rooms

    good_rows = fetchall(
        """
        SELECT room_id,
               (payload->>'quality_score')::float AS qs
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND character_id = %s
          AND (payload->>'quality_score')::float >= %s
        """,
        (character_id, min_score),
    )

    return [
        {"room_id": r["room_id"], "quality_score": r["qs"]}
        for r in good_rows
        if r["room_id"] not in excluded_rooms
    ]


# ── 품질 대시보드 집계 ───────────────────────────────────────────


def get_quality_dashboard(
    character_id: str,
    days: int = 30,
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
    agg = fetchone(
        """
        SELECT
            COALESCE(AVG((payload->>'quality_score')::float), 0) AS avg_qs,
            COALESCE(AVG((payload->>'mbti_consistency')::float), 0) AS avg_mc,
            COALESCE(AVG((payload->>'contextual_relevance')::float), 0) AS avg_cr,
            COALESCE(AVG((payload->>'emotional_naturalness')::float), 0) AS avg_en,
            COALESCE(AVG((payload->>'engagement_quality')::float), 0) AS avg_eq,
            COUNT(*) AS total
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND character_id = %s
          AND created_at >= NOW() - INTERVAL '%s days'
        """,
        (character_id, days),
    )

    # 다양성 점수 평균
    div_agg = fetchone(
        """
        SELECT COALESCE(AVG((payload->>'diversity_score')::float), 0) AS avg_div
        FROM metric_events
        WHERE event_type = 'low_diversity_warning'
          AND character_id = %s
          AND created_at >= NOW() - INTERVAL '%s days'
        """,
        (character_id, days),
    )

    # 피드백 카운트
    fb = fetchone(
        """
        SELECT
            COALESCE(SUM(CASE WHEN feedback_type = 'thumbs_up' THEN 1 ELSE 0 END), 0) AS up,
            COALESCE(SUM(CASE WHEN feedback_type = 'thumbs_down' THEN 1 ELSE 0 END), 0) AS down
        FROM response_feedback
        WHERE character_id = %s
          AND created_at >= NOW() - INTERVAL '%s days'
        """,
        (character_id, days),
    )

    # 일별 추이
    trend_rows = fetchall(
        """
        SELECT
            DATE(created_at) AS d,
            AVG((payload->>'quality_score')::float) AS avg_score
        FROM metric_events
        WHERE event_type = 'quality_score'
          AND character_id = %s
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY d
        """,
        (character_id, days),
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


def get_diversity_report(character_id: str) -> Dict[str, Any]:
    """최근 다양성 경고 이벤트 기반 리포트."""
    if not postgres_enabled():
        return {"warnings": [], "avg_diversity": 1.0}

    rows = fetchall(
        """
        SELECT payload, created_at
        FROM metric_events
        WHERE event_type = 'low_diversity_warning'
          AND character_id = %s
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (character_id,),
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
