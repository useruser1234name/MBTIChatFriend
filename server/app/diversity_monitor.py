"""MBTI 응답 다양성 자동 평가 파이프라인.

DATA-C 권도현 + DATA-A 오재원 설계 (2차 회의 W2-2 합의).
매주 diversity score를 자동 측정하고 임계값 이하 시 경고 기록.

사용법:
    from .diversity_monitor import DiversityMonitor
    monitor = DiversityMonitor()
    report = await monitor.weekly_report(character_id)
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Optional

from .postgres import fetchall, execute as pg_execute

logger = logging.getLogger(__name__)

# 다양성 임계값 — 이 값 이하면 경고 (DATA-C 권도현 제안)
DIVERSITY_ALERT_THRESHOLD = 0.55

# 평가 대상 최근 응답 수
EVAL_WINDOW = 50


class DiversityMonitor:
    """MBTI 캐릭터별 응답 다양성 모니터링.

    다양성 지표:
    - bigram_diversity: 응답 내 bigram 유니크 비율
    - cross_diversity: 최근 N개 응답 간 bigram 중복 비율
    - final_score: 두 지표의 가중 평균 (0.4 + 0.6)
    """

    def _get_bigrams(self, text: str) -> list[tuple[str, str]]:
        """텍스트를 bigram 리스트로 변환."""
        tokens = re.findall(r"[가-힣a-zA-Z]+", text)
        return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]

    def score_single(self, response: str) -> float:
        """단일 응답 내부 다양성 점수 (0~1)."""
        bigrams = self._get_bigrams(response)
        if not bigrams:
            return 1.0
        unique_ratio = len(set(bigrams)) / len(bigrams)
        return unique_ratio

    def score_cross(self, responses: list[str]) -> float:
        """여러 응답 간 참신성 점수 (0~1).

        최근 응답들의 bigram 풀 대비 신규 bigram 비율.
        """
        if len(responses) < 2:
            return 1.0

        all_bigrams: list[set] = [set(self._get_bigrams(r)) for r in responses]

        novelty_scores = []
        for i in range(1, len(all_bigrams)):
            current = all_bigrams[i]
            previous_pool: set = set()
            for j in all_bigrams[max(0, i - 5):i]:
                previous_pool.update(j)

            if not current:
                novelty_scores.append(1.0)
                continue

            novel = current - previous_pool
            novelty_scores.append(len(novel) / len(current))

        return sum(novelty_scores) / len(novelty_scores) if novelty_scores else 1.0

    def compute_diversity_score(self, responses: list[str]) -> float:
        """최종 다양성 점수 계산.

        final = 0.4 * avg_internal_diversity + 0.6 * cross_novelty
        """
        if not responses:
            return 1.0

        internal_scores = [self.score_single(r) for r in responses]
        avg_internal = sum(internal_scores) / len(internal_scores)
        cross = self.score_cross(responses)

        return 0.4 * avg_internal + 0.6 * cross

    async def weekly_report(self, character_id: str) -> dict:
        """캐릭터의 최근 50개 응답 다양성 리포트 생성.

        Returns:
            {
                "character_id": str,
                "sample_count": int,
                "diversity_score": float,
                "internal_diversity": float,
                "cross_novelty": float,
                "alert": bool,
                "alert_message": str
            }
        """
        rows = fetchall(
            """
            SELECT payload->>'ai_response' AS response
            FROM metric_events
            WHERE event_type = 'quality_score'
              AND character_id = %s
              AND payload->>'ai_response' IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (character_id, EVAL_WINDOW),
        )

        responses = [r["response"] for r in rows if r.get("response")]
        if not responses:
            return {
                "character_id": character_id,
                "sample_count": 0,
                "diversity_score": 1.0,
                "internal_diversity": 1.0,
                "cross_novelty": 1.0,
                "alert": False,
                "alert_message": "",
            }

        internal_scores = [self.score_single(r) for r in responses]
        avg_internal = sum(internal_scores) / len(internal_scores)
        cross = self.score_cross(responses)
        final_score = 0.4 * avg_internal + 0.6 * cross

        alert = final_score < DIVERSITY_ALERT_THRESHOLD
        alert_message = (
            f"[경고] {character_id} 다양성 점수 {final_score:.2f} "
            f"(임계값 {DIVERSITY_ALERT_THRESHOLD} 이하). "
            "자기강화 루프 발생 가능성 검토 필요."
            if alert
            else ""
        )

        if alert:
            logger.warning(alert_message)
            # PostgreSQL에 경고 이벤트 기록
            try:
                pg_execute(
                    """
                    INSERT INTO metric_events
                        (event_type, character_id, payload)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (
                        "diversity_alert",
                        character_id,
                        f'{{"score": {final_score:.4f}, '
                        f'"sample_count": {len(responses)}, '
                        f'"threshold": {DIVERSITY_ALERT_THRESHOLD}}}',
                    ),
                )
            except Exception as e:
                logger.warning(f"diversity_alert 기록 실패: {e}")

        return {
            "character_id": character_id,
            "sample_count": len(responses),
            "diversity_score": round(final_score, 4),
            "internal_diversity": round(avg_internal, 4),
            "cross_novelty": round(cross, 4),
            "alert": alert,
            "alert_message": alert_message,
        }

    def get_most_repeated_phrases(
        self, responses: list[str], top_n: int = 10
    ) -> list[tuple[str, int]]:
        """가장 자주 반복되는 bigram을 반환. 자기강화 루프 디버깅용."""
        all_bigrams: list[tuple[str, str]] = []
        for r in responses:
            all_bigrams.extend(self._get_bigrams(r))
        counter = Counter(all_bigrams)
        return [(f"{a} {b}", cnt) for (a, b), cnt in counter.most_common(top_n)]


# 전역 싱글톤
_monitor = DiversityMonitor()


def get_diversity_monitor() -> DiversityMonitor:
    return _monitor
