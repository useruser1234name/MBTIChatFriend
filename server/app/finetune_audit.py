"""파인튜닝 데이터 품질 감사 모듈 — W1-5.

FT-C 전영석 + FT-A 노재민 설계, AI-C 한나현 검증 (2차 회의 합의).

감사 항목:
1. MBTI 유형별 데이터 분포 균형
2. 합성 데이터 vs 실제 대화 비율 추정
3. 응답 다양성 지표 (bigram diversity score)
4. 동일/유사 응답 패턴 반복 비율
5. 자기강화 루프 발생 여부 판단

사용법:
    from .finetune_audit import run_audit
    report = run_audit(jsonl_path="finetune_data.jsonl")
    print(report.summary())
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# MBTI 16가지 유형
_ALL_MBTI = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

# 자기강화 루프 판단 기준: 동일 응답이 전체의 N% 이상 반복
LOOP_THRESHOLD = 0.05

# 다양성 경고 임계값
DIVERSITY_WARNING = 0.55


def _extract_bigrams(text: str) -> list[tuple[str, str]]:
    tokens = re.findall(r"[가-힣a-zA-Z]+", text)
    return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]


def _bigram_diversity(text: str) -> float:
    bigrams = _extract_bigrams(text)
    if not bigrams:
        return 1.0
    return len(set(bigrams)) / len(bigrams)


def _cross_novelty(responses: list[str]) -> float:
    """최근 응답들의 bigram 풀 대비 신규 bigram 비율."""
    if len(responses) < 2:
        return 1.0
    all_bigrams = [set(_extract_bigrams(r)) for r in responses]
    scores = []
    for i in range(1, len(all_bigrams)):
        current = all_bigrams[i]
        pool: set = set()
        for prev in all_bigrams[max(0, i - 5):i]:
            pool.update(prev)
        if not current:
            scores.append(1.0)
            continue
        scores.append(len(current - pool) / len(current))
    return sum(scores) / len(scores) if scores else 1.0


@dataclass
class AuditReport:
    """파인튜닝 데이터 품질 감사 결과."""

    total_samples: int = 0
    mbti_distribution: dict[str, int] = field(default_factory=dict)
    synthetic_ratio: float = 0.0          # 합성 데이터 추정 비율 (메타데이터 기반)
    avg_internal_diversity: float = 0.0   # 응답 내 bigram 다양성
    cross_novelty: float = 0.0            # 응답 간 신규 bigram 비율
    diversity_score: float = 0.0          # 최종 다양성 점수
    repetition_rate: float = 0.0          # 동일 응답 반복 비율
    self_reinforcement_detected: bool = False
    top_repeated: list[tuple[str, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mbti_imbalance_score: float = 0.0     # 0 = 완벽 균형, 1 = 완전 불균형

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "파인튜닝 데이터 품질 감사 리포트 (W1-5)",
            "=" * 60,
            f"총 샘플 수       : {self.total_samples}",
            f"합성 데이터 비율 : {self.synthetic_ratio:.1%}",
            f"MBTI 분포 불균형 : {self.mbti_imbalance_score:.3f} (0=균형, 1=불균형)",
            "",
            "── 다양성 지표 ──────────────────────────────────",
            f"  내부 다양성     : {self.avg_internal_diversity:.4f}",
            f"  응답간 참신성   : {self.cross_novelty:.4f}",
            f"  최종 다양성점수 : {self.diversity_score:.4f}  "
            f"{'⚠️ 경고' if self.diversity_score < DIVERSITY_WARNING else '✅ 정상'}",
            f"  반복 응답 비율  : {self.repetition_rate:.1%}  "
            f"{'⚠️ 자기강화 의심' if self.self_reinforcement_detected else '✅ 정상'}",
            "",
            "── MBTI 분포 ────────────────────────────────────",
        ]
        for mbti in _ALL_MBTI:
            cnt = self.mbti_distribution.get(mbti, 0)
            pct = cnt / self.total_samples if self.total_samples else 0
            bar = "█" * int(pct * 40)
            lines.append(f"  {mbti:4s} {cnt:5d} ({pct:5.1%}) {bar}")

        if self.top_repeated:
            lines += [
                "",
                "── 반복 패턴 Top 10 ─────────────────────────────",
            ]
            for phrase, cnt in self.top_repeated[:10]:
                lines.append(f"  {cnt:5d}회  {phrase[:60]}")

        if self.warnings:
            lines += ["", "── 경고 ─────────────────────────────────────────"]
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")

        lines.append("=" * 60)
        return "\n".join(lines)


def run_audit(
    jsonl_path: str,
    mbti_field: str = "mbti",
    response_field: str = "assistant",
    synthetic_marker: str = "__synthetic__",
) -> AuditReport:
    """JSONL 파인튜닝 데이터를 읽어 품질 감사를 수행한다.

    JSONL 포맷 (OpenAI fine-tuning):
        {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}],
         "mbti": "INTJ",
         "__synthetic__": true}   ← 선택적 합성 데이터 마커

    Args:
        jsonl_path: 감사할 JSONL 파일 경로.
        mbti_field: MBTI 유형을 담은 최상위 키.
        response_field: assistant role 응답을 담은 role 값.
        synthetic_marker: 합성 데이터 표시 키.

    Returns:
        AuditReport 인스턴스.
    """
    path = Path(jsonl_path)
    if not path.exists():
        logger.error(f"파인튜닝 데이터 파일 없음: {jsonl_path}")
        report = AuditReport()
        report.warnings.append(f"파일 없음: {jsonl_path}")
        return report

    samples: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 파싱 오류 (스킵): {e}")

    if not samples:
        report = AuditReport()
        report.warnings.append("유효한 샘플 없음")
        return report

    report = AuditReport(total_samples=len(samples))

    # ── 1. MBTI 분포 ──────────────────────────────────────────
    mbti_counter: Counter = Counter()
    for s in samples:
        mbti = s.get(mbti_field, "")
        if mbti in _ALL_MBTI:
            mbti_counter[mbti] += 1
        # messages 안에서 MBTI 탐색 (system prompt 기반)
        elif not mbti:
            system_text = ""
            for msg in s.get("messages", []):
                if msg.get("role") == "system":
                    system_text = msg.get("content", "")
                    break
            for candidate in _ALL_MBTI:
                if candidate in system_text:
                    mbti_counter[candidate] += 1
                    break

    report.mbti_distribution = dict(mbti_counter)

    # 불균형 점수: Gini 계수 기반
    counts = [mbti_counter.get(m, 0) for m in _ALL_MBTI]
    total = sum(counts) or 1
    proportions = [c / total for c in counts]
    ideal = 1.0 / len(_ALL_MBTI)
    report.mbti_imbalance_score = sum(abs(p - ideal) for p in proportions) / 2.0

    if report.mbti_imbalance_score > 0.3:
        under = [m for m in _ALL_MBTI if mbti_counter.get(m, 0) < total / len(_ALL_MBTI) * 0.5]
        report.warnings.append(
            f"MBTI 분포 불균형 심각 (score={report.mbti_imbalance_score:.3f}). "
            f"데이터 부족 유형: {', '.join(under) if under else '없음'}"
        )

    # ── 2. 합성 데이터 비율 ────────────────────────────────────
    synthetic_count = sum(1 for s in samples if s.get(synthetic_marker))
    report.synthetic_ratio = synthetic_count / len(samples)
    if report.synthetic_ratio > 0.7:
        report.warnings.append(
            f"합성 데이터 비율 {report.synthetic_ratio:.1%} — 자기강화 루프 위험 높음."
        )

    # ── 3. 응답 추출 ──────────────────────────────────────────
    responses: list[str] = []
    for s in samples:
        for msg in s.get("messages", []):
            if msg.get("role") == response_field:
                content = msg.get("content", "").strip()
                if content:
                    responses.append(content)

    if not responses:
        report.warnings.append("assistant 응답 추출 실패 — messages 구조 확인 필요")
        return report

    # ── 4. 다양성 지표 ────────────────────────────────────────
    internal_scores = [_bigram_diversity(r) for r in responses]
    report.avg_internal_diversity = sum(internal_scores) / len(internal_scores)
    report.cross_novelty = _cross_novelty(responses)
    report.diversity_score = (
        0.4 * report.avg_internal_diversity + 0.6 * report.cross_novelty
    )

    if report.diversity_score < DIVERSITY_WARNING:
        report.warnings.append(
            f"다양성 점수 {report.diversity_score:.3f} — 임계값({DIVERSITY_WARNING}) 이하. "
            "자기강화 루프 가능성 검토 필요."
        )

    # ── 5. 반복 패턴 탐지 ─────────────────────────────────────
    response_counter: Counter = Counter(responses)
    most_common = response_counter.most_common(10)
    report.top_repeated = [(text[:80], cnt) for text, cnt in most_common if cnt > 1]

    # 자기강화 루프: 상위 응답이 전체의 LOOP_THRESHOLD 이상
    if most_common:
        top_text, top_cnt = most_common[0]
        report.repetition_rate = top_cnt / len(responses)
        if report.repetition_rate >= LOOP_THRESHOLD:
            report.self_reinforcement_detected = True
            report.warnings.append(
                f"자기강화 루프 감지: 최다 반복 응답 {top_cnt}회 ({report.repetition_rate:.1%}). "
                f"응답: '{top_text[:60]}...'"
            )

    return report


def run_audit_from_db(character_id: str = "", limit: int = 500) -> AuditReport:
    """PostgreSQL metric_events에서 ai_response를 추출해 감사 수행.

    DB 연결이 없는 경우 빈 리포트를 반환.
    """
    try:
        from .postgres import fetchall
        rows = fetchall(
            """
            SELECT
                character_id,
                payload->>'ai_response' AS response,
                payload->>'mbti' AS mbti
            FROM metric_events
            WHERE event_type = 'quality_score'
              AND payload->>'ai_response' IS NOT NULL
              AND (%(cid)s = '' OR character_id = %(cid)s)
            ORDER BY created_at DESC
            LIMIT %(lim)s
            """,
            {"cid": character_id, "lim": limit},
        )
    except Exception as e:
        logger.error(f"DB 감사 데이터 조회 실패: {e}")
        r = AuditReport()
        r.warnings.append(f"DB 조회 실패: {e}")
        return r

    if not rows:
        r = AuditReport()
        r.warnings.append("감사 대상 응답 없음 (metric_events 비어있음)")
        return r

    responses = [row["response"] for row in rows if row.get("response")]
    mbti_counter: Counter = Counter(
        row["mbti"] for row in rows if row.get("mbti") in _ALL_MBTI
    )

    report = AuditReport(total_samples=len(rows))
    report.mbti_distribution = dict(mbti_counter)

    counts = [mbti_counter.get(m, 0) for m in _ALL_MBTI]
    total = sum(counts) or 1
    proportions = [c / total for c in counts]
    ideal = 1.0 / len(_ALL_MBTI)
    report.mbti_imbalance_score = sum(abs(p - ideal) for p in proportions) / 2.0

    if responses:
        internal_scores = [_bigram_diversity(r) for r in responses]
        report.avg_internal_diversity = sum(internal_scores) / len(internal_scores)
        report.cross_novelty = _cross_novelty(responses)
        report.diversity_score = (
            0.4 * report.avg_internal_diversity + 0.6 * report.cross_novelty
        )

        response_counter: Counter = Counter(responses)
        most_common = response_counter.most_common(10)
        report.top_repeated = [(text[:80], cnt) for text, cnt in most_common if cnt > 1]

        if most_common:
            top_text, top_cnt = most_common[0]
            report.repetition_rate = top_cnt / len(responses)
            if report.repetition_rate >= LOOP_THRESHOLD:
                report.self_reinforcement_detected = True
                report.warnings.append(
                    f"자기강화 루프 감지: 최다 반복 응답 {top_cnt}회 ({report.repetition_rate:.1%})."
                )

        if report.diversity_score < DIVERSITY_WARNING:
            report.warnings.append(
                f"다양성 점수 {report.diversity_score:.3f} — 임계값({DIVERSITY_WARNING}) 이하."
            )

    return report
