"""A/B 테스트 프레임워크 — DATA-B 신예린 설계 (3차 회의 합의)."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ABTestConfig:
    """A/B 실험 설정."""

    experiment_id: str
    variant_a: str          # 대조군 (예: "gpt-4.1-mini")
    variant_b: str          # 실험군 (예: "gpt-4.1")
    traffic_split: float    # 0~1 사이 float; variant_b에 배정되는 비율
    active: bool = True
    character_filter: str = ""  # 특정 캐릭터 MBTI에만 적용 (빈 문자열이면 전체 적용)


# ── model_routing 정책 키 ───────────────────────────────────────────────────
# 2026-08-03 회의 P0-S2: model_routing 실험은 더 이상 "어떤 모델 ID를 쓸지"를
# 배정하지 않는다. 이전 정의(variant_a="gpt-4.1-mini", variant_b="gpt-4.1")는
# chat_service._route_model이 variant 문자열을 그대로 모델 ID로 반환하는 구조와
# 맞물려, 캐릭터별 sha256 해시로 모델을 영구 고정시켰다(복잡도 분류기가 아예
# 실행되지 않음 → 심층 상담도 mini, "ㅇㅇ" 한 마디에도 4.1).
#
# 이제 variant는 복잡도 라우팅 위에 얹는 **정책 오버레이**를 뜻한다:
#   MODEL_ROUTING_COMPLEXITY      대조군 — _classify_message_complexity 결과 그대로
#   MODEL_ROUTING_ALWAYS_COMPLEX  실험군 — 복잡도와 무관하게 상위(complex) 모델 강제
MODEL_ROUTING_EXPERIMENT_ID = "model_routing"
MODEL_ROUTING_COMPLEXITY = "complexity_routing"
MODEL_ROUTING_ALWAYS_COMPLEX = "always_complex"


# ── 전역 실험 정의 ──────────────────────────────────────────────────────────

EXPERIMENTS: Dict[str, ABTestConfig] = {
    MODEL_ROUTING_EXPERIMENT_ID: ABTestConfig(
        experiment_id=MODEL_ROUTING_EXPERIMENT_ID,
        variant_a=MODEL_ROUTING_COMPLEXITY,      # 대조군: 복잡도 라우팅 유지
        variant_b=MODEL_ROUTING_ALWAYS_COMPLEX,  # 실험군: 상위 모델 강제
        traffic_split=0.3,                        # 30%에게 상위 모델 강제 정책
        active=True,
    )
}

EXPERIMENTS["cta_level3_v1"] = ABTestConfig(
    experiment_id="cta_level3_v1",
    variant_a="feature_gate",       # 현재: "레벨 4는 프리미엄에서만 경험할 수 있어요"
    variant_b="relationship_growth", # 신규: "우리 관계가 깊어지고 있어요. 더 많은 감정을 표현할 수 있게 해줄게요"
    traffic_split=0.5,
    active=True,
)

EXPERIMENTS["referral_cta_v1"] = ABTestConfig(
    experiment_id="referral_cta_v1",
    variant_a="control",
    variant_b="referral_cta",
    traffic_split=1.0,  # B 문구 전체 적용
    active=True,
)


class ABTestManager:
    """A/B 실험 배정·기록·집계 매니저."""

    # 인메모리 이벤트 버퍼 (PostgreSQL 미연결 환경 대비)
    _buffer: List[dict] = []

    # ── variant 배정 ────────────────────────────────────────────────────────

    def assign_variant(
        self,
        user_id: str,
        experiment_id: str,
        character_id: str = "",
    ) -> str:
        """
        variant 배정. character_id가 있으면 character_id 기준으로 분할.

        동일한 (split_key, experiment_id) 조합은 항상 동일 variant를 반환한다.
        실험이 비활성화 상태이거나 존재하지 않으면 variant_a(대조군)를 반환한다.

        Returns:
            배정된 variant 문자열 — 실험마다 의미가 다르다(예: model_routing은
            "complexity_routing"/"always_complex" 정책 오버레이 이름 등).
            2026-08-03 P0-S2 이전에는 model_routing 실험 자체가 모델 ID 문자열
            ("gpt-4.1-mini"/"gpt-4.1")을 그대로 배정했지만, 지금은 그 실험도
            복잡도 라우팅 위의 정책 오버레이일 뿐이라 모델 ID를 직접
            반환하지 않는다. 2026-08-11(소유자 결정): LoRA 실험 16종은 도달
            불가한 사문 코드였기에 EXPERIMENTS에서 전부 제거됐다(복구는 git
            이력으로 가능).
        """
        config = EXPERIMENTS.get(experiment_id)
        if config is None or not config.active:
            # 실험 없음 또는 비활성 → 대조군
            if config:
                return config.variant_a
            # Low-3(2026-08-04 점검): 등록되지 않은 experiment_id에 대한 기본
            # fallback. 이전에는 구식 모델 ID 문자열("gpt-4.1-mini")을 그대로
            # 반환했다 — model_routing 실험이 P0-S2로 "모델 ID 배정"에서
            # "복잡도 라우팅 위의 정책 오버레이"로 의미가 바뀐 뒤에는 이 값이
            # variant_a/variant_b 어느 쪽과도 일치하지 않아, record_result가
            # 집계에서 알아볼 수 없는 유령 variant 버킷을 만들었다. 실질적으로
            # 이 분기는 "정책 개입 없음 = 복잡도 라우팅 그대로"와 동치이므로
            # 그 정책 상수를 반환한다.
            return MODEL_ROUTING_COMPLEXITY  # 기본 fallback

        # 분할 기준: character_id 우선, 없으면 user_id
        split_key = character_id if character_id else user_id
        hash_input = f"{split_key}:{experiment_id}".encode()
        hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
        normalized = (hash_value % 10000) / 10000.0

        return config.variant_b if normalized < config.traffic_split else config.variant_a

    # ── 결과 기록 ────────────────────────────────────────────────────────────

    def record_result(
        self,
        experiment_id: str,
        variant: str,
        metric_name: str,
        value: float,
        user_id: str = "",
        character_id: str = "",
    ) -> None:
        """A/B 테스트 메트릭을 PostgreSQL ab_test_results 테이블에 기록.

        DB 미연결 시 인메모리 버퍼에 저장 후 로깅으로 대체한다.
        """
        record = {
            "experiment_id": experiment_id,
            "variant": variant,
            "user_id": user_id,
            "character_id": character_id,
            "metric_name": metric_name,
            "metric_value": float(value),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        # DB 기록 시도
        try:
            from .postgres import execute as pg_execute, postgres_enabled
            if postgres_enabled():
                pg_execute(
                    """
                    INSERT INTO ab_test_results
                        (experiment_id, variant, user_id, character_id,
                         metric_name, metric_value)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        experiment_id,
                        variant,
                        user_id,
                        character_id,
                        metric_name,
                        float(value),
                    ),
                )
                logger.debug(
                    "[AB] recorded experiment=%s variant=%s metric=%s value=%s",
                    experiment_id, variant, metric_name, value,
                )
                return
        except Exception as exc:
            logger.warning("[AB] DB 기록 실패, 인메모리 버퍼에 저장: %s", exc)

        # DB 미연결 fallback: 인메모리 버퍼
        self._buffer.append(record)
        logger.info(
            "[AB] buffered experiment=%s variant=%s metric=%s value=%s",
            experiment_id, variant, metric_name, value,
        )

    # ── 결과 집계 ────────────────────────────────────────────────────────────

    def get_experiment_summary(
        self,
        experiment_id: str,
        days: int = 7,
    ) -> dict:
        """실험 결과 집계.

        PostgreSQL 연결 시 DB 데이터를 집계하고,
        미연결 시 인메모리 버퍼에서 집계한다.

        Returns:
            {
                "experiment_id": str,
                "period_days": int,
                "config": {...},
                "variants": {
                    "<variant>": {
                        "sample_count": int,
                        "metrics": {
                            "<metric_name>": {
                                "count": int,
                                "mean": float,
                                "min": float,
                                "max": float,
                            }
                        }
                    }
                }
            }
        """
        config = EXPERIMENTS.get(experiment_id)
        config_info = {}
        if config:
            config_info = {
                "variant_a": config.variant_a,
                "variant_b": config.variant_b,
                "traffic_split": config.traffic_split,
                "active": config.active,
            }

        # DB 집계 시도
        try:
            from .postgres import fetchall, postgres_enabled
            if postgres_enabled():
                rows = fetchall(
                    """
                    SELECT
                        variant,
                        metric_name,
                        COUNT(*)            AS cnt,
                        AVG(metric_value)   AS mean_val,
                        MIN(metric_value)   AS min_val,
                        MAX(metric_value)   AS max_val
                    FROM ab_test_results
                    WHERE experiment_id = %s
                      AND created_at >= NOW() - make_interval(days => %s)
                    GROUP BY variant, metric_name
                    ORDER BY variant, metric_name
                    """,
                    (experiment_id, int(days)),
                )

                variants: dict = {}
                for row in rows:
                    v = row["variant"]
                    m = row["metric_name"]
                    if v not in variants:
                        variants[v] = {"sample_count": 0, "metrics": {}}
                    variants[v]["metrics"][m] = {
                        "count": int(row["cnt"]),
                        "mean": round(float(row["mean_val"]), 4),
                        "min": round(float(row["min_val"]), 4),
                        "max": round(float(row["max_val"]), 4),
                    }
                    variants[v]["sample_count"] += int(row["cnt"])

                return {
                    "experiment_id": experiment_id,
                    "period_days": days,
                    "config": config_info,
                    "variants": variants,
                }
        except Exception as exc:
            logger.warning("[AB] DB 집계 실패, 인메모리 버퍼 사용: %s", exc)

        # 인메모리 버퍼 집계 fallback
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        relevant = [
            r for r in self._buffer
            if r["experiment_id"] == experiment_id
            and datetime.fromisoformat(r["created_at"]) >= cutoff
        ]

        variants_buf: dict = {}
        for r in relevant:
            v = r["variant"]
            m = r["metric_name"]
            val = r["metric_value"]
            if v not in variants_buf:
                variants_buf[v] = {"sample_count": 0, "metrics": {}}
            if m not in variants_buf[v]["metrics"]:
                variants_buf[v]["metrics"][m] = {
                    "_values": [],
                    "count": 0,
                    "mean": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                }
            variants_buf[v]["metrics"][m]["_values"].append(val)
            variants_buf[v]["sample_count"] += 1

        # 통계 계산
        for v_data in variants_buf.values():
            for m_name, m_data in v_data["metrics"].items():
                vals = m_data.pop("_values", [])
                if vals:
                    m_data["count"] = len(vals)
                    m_data["mean"] = round(sum(vals) / len(vals), 4)
                    m_data["min"] = round(min(vals), 4)
                    m_data["max"] = round(max(vals), 4)

        return {
            "experiment_id": experiment_id,
            "period_days": days,
            "config": config_info,
            "variants": variants_buf,
        }


# ── 싱글턴 인스턴스 ──────────────────────────────────────────────────────────

_manager: Optional[ABTestManager] = None


def get_ab_manager() -> ABTestManager:
    """ABTestManager 싱글턴 반환."""
    global _manager
    if _manager is None:
        _manager = ABTestManager()
    return _manager
