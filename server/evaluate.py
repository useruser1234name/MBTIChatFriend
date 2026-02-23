"""MBTI Chat 모델 성능 평가 스크립트

평가 영역:
1. 채팅 응답 품질 (MBTI 성격 일관성, 응답 형식, 감정 태그)
2. 호감도 분석 정확도 (LLM delta vs 기대값)
3. 메모리 추출 품질
4. 응답 지연 시간 (Latency)
5. 파인튜닝 모델 비교 (선택)
"""

import asyncio
import json
import time
import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY
from app.chat_service import (
    analyze_affinity_with_llm,
    calculate_affinity_delta,
    _parse_reply,
    generate_reply,
)
from app.memory_service import summarize_conversation, extract_facts
from app.models import HistoryMessage, MemoryItem
from app.finetune_service import get_model_for_character

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── 평가 상수 ──────────────────────────────────────────────────
VALID_EMOTIONS = {
    "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
    "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
}

MBTI_TYPES = [
    "ENFP", "ENFJ", "ENTP", "ENTJ",
    "INFP", "INFJ", "INTP", "INTJ",
    "ESFP", "ESFJ", "ESTP", "ESTJ",
    "ISFP", "ISFJ", "ISTP", "ISTJ",
]

# 평가 테스트 케이스
TEST_SCENARIOS = [
    # (메시지, 기대_호감도_방향, 설명)
    {"message": "안녕! 오늘 기분이 너무 좋아!", "expected_direction": "positive", "label": "긍정 인사"},
    {"message": "너 정말 대단해! 최고야!", "expected_direction": "positive", "label": "칭찬"},
    {"message": "고마워, 덕분에 힘이 났어", "expected_direction": "positive", "label": "감사"},
    {"message": "보고 싶었어... 사랑해", "expected_direction": "positive", "label": "애정 표현"},
    {"message": "짜증나, 그만 좀 해", "expected_direction": "negative", "label": "짜증/불만"},
    {"message": "별로야, 관심 없어", "expected_direction": "negative", "label": "무관심"},
    {"message": "오늘 날씨 좋다", "expected_direction": "neutral", "label": "중립 일상"},
    {"message": "응", "expected_direction": "neutral", "label": "짧은 중립"},
    {"message": "나 요즘 일이 힘들어서... 위로해줄 수 있어?", "expected_direction": "positive", "label": "위로 요청"},
    {"message": "너는 어떤 음식 좋아해?", "expected_direction": "positive", "label": "관심/질문"},
]

# MBTI 성격 특성 키워드 (검증용)
MBTI_TRAIT_INDICATORS = {
    "E": ["!", "ㅋㅋ", "ㅎㅎ", "~", "헐", "대박", "와"],
    "I": [],  # 내향형은 부재로 판단하기 어려움
    "N": [],
    "S": [],
    "T": [],
    "F": ["ㅠㅠ", "ㅜㅜ", "💕", "🥰", "😊", "❤", "♡"],
    "J": [],
    "P": ["ㅋㅋㅋ", "~", "!!"],
}

MEMORY_TEST_CONVERSATIONS = [
    HistoryMessage(role="user", content="나 이름은 김수진이야, 26살이고 디자이너로 일하고 있어"),
    HistoryMessage(role="assistant", content="수진아 반가워! 디자이너라니 멋지다~"),
    HistoryMessage(role="user", content="취미는 그림 그리기랑 카페 탐방이야"),
    HistoryMessage(role="assistant", content="오 그림 그려? 나한테도 그려줘!"),
    HistoryMessage(role="user", content="좋아하는 음식은 파스타, 싫어하는 건 민트초코야"),
    HistoryMessage(role="assistant", content="파스타 좋지~ 민트초코는 나도 별로야 ㅋㅋ"),
    HistoryMessage(role="user", content="요즘 이직 고민 중이야, 현재 회사가 좀 힘들어서"),
    HistoryMessage(role="assistant", content="힘들겠다... 어떤 부분이 제일 힘들어?"),
]

EXPECTED_MEMORY_KEYS = ["이름", "나이", "직업", "취미", "좋아하는 음식", "싫어하는 음식", "고민"]


@dataclass
class EvalResult:
    """평가 결과"""
    category: str
    test_name: str
    passed: bool
    score: float  # 0.0 ~ 1.0
    detail: str
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    """전체 평가 리포트"""
    results: List[EvalResult] = field(default_factory=list)

    def add(self, result: EvalResult):
        self.results.append(result)

    def summary(self) -> Dict[str, Any]:
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = {"total": 0, "passed": 0, "scores": [], "latencies": []}
            cat = categories[r.category]
            cat["total"] += 1
            if r.passed:
                cat["passed"] += 1
            cat["scores"].append(r.score)
            if r.latency_ms > 0:
                cat["latencies"].append(r.latency_ms)

        summary = {}
        for cat_name, cat_data in categories.items():
            avg_score = statistics.mean(cat_data["scores"]) if cat_data["scores"] else 0
            avg_latency = statistics.mean(cat_data["latencies"]) if cat_data["latencies"] else 0
            summary[cat_name] = {
                "pass_rate": f"{cat_data['passed']}/{cat_data['total']}",
                "avg_score": round(avg_score, 3),
                "avg_latency_ms": round(avg_latency, 1),
            }
        return summary

    def print_report(self):
        print("\n" + "=" * 70)
        print("  MBTI Chat 모델 성능 평가 리포트")
        print("=" * 70)

        current_cat = None
        for r in self.results:
            if r.category != current_cat:
                current_cat = r.category
                print(f"\n{'─' * 60}")
                print(f"  📊 {current_cat}")
                print(f"{'─' * 60}")

            status = "✅" if r.passed else "❌"
            score_bar = "█" * int(r.score * 10) + "░" * (10 - int(r.score * 10))
            latency_str = f" ({r.latency_ms:.0f}ms)" if r.latency_ms > 0 else ""
            print(f"  {status} {r.test_name}: [{score_bar}] {r.score:.1%}{latency_str}")
            if not r.passed or r.score < 0.8:
                print(f"     → {r.detail}")

        print(f"\n{'=' * 70}")
        print("  📈 카테고리별 요약")
        print(f"{'=' * 70}")
        summary = self.summary()
        for cat_name, data in summary.items():
            print(f"  {cat_name}:")
            print(f"    통과율: {data['pass_rate']}, 평균 점수: {data['avg_score']:.1%}", end="")
            if data["avg_latency_ms"] > 0:
                print(f", 평균 지연: {data['avg_latency_ms']:.0f}ms")
            else:
                print()

        # 전체 점수
        all_scores = [r.score for r in self.results]
        total_passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        overall = statistics.mean(all_scores) if all_scores else 0
        print(f"\n  🎯 전체 점수: {overall:.1%} ({total_passed}/{total} 통과)")
        print("=" * 70)


report = EvalReport()


# ── 1. 응답 형식 검증 ───────────────────────────────────────────

async def eval_response_format():
    """응답이 올바른 JSON 배열 형식인지 검증"""
    print("\n🔍 [1/5] 응답 형식 검증 중...")

    test_mbti_list = ["ENFP", "INTJ", "ESFJ", "ISTP"]

    for mbti in test_mbti_list:
        start = time.time()
        try:
            replies, delta = await generate_reply(
                message="안녕! 오늘 뭐 했어?",
                mbti=mbti,
                speech_style="CASUAL",
                relationship="FRIEND",
                nickname="테스터",
                affinity_level=3,
                conversation_history=[],
                character_name=f"테스트캐릭터_{mbti}",
            )
            latency = (time.time() - start) * 1000

            # 검증 1: replies가 비어있지 않은지
            has_replies = len(replies) > 0
            # 검증 2: 각 reply에 text, emotion이 있는지
            valid_structure = all(
                hasattr(r, "text") and hasattr(r, "emotion") and r.text.strip()
                for r in replies
            )
            # 검증 3: emotion이 유효한 값인지
            valid_emotions = all(r.emotion in VALID_EMOTIONS for r in replies)
            # 검증 4: 여러 메시지 분할이 되었는지 (선호)
            multi_message = len(replies) >= 2

            score = (
                (0.3 if has_replies else 0) +
                (0.3 if valid_structure else 0) +
                (0.3 if valid_emotions else 0) +
                (0.1 if multi_message else 0.05)
            )

            emotions_used = [r.emotion for r in replies]
            texts = [r.text[:30] for r in replies]

            report.add(EvalResult(
                category="1. 응답 형식",
                test_name=f"{mbti} 응답 형식",
                passed=has_replies and valid_structure and valid_emotions,
                score=score,
                detail=f"replies={len(replies)}, emotions={emotions_used}, texts={texts}",
                latency_ms=latency,
            ))

        except Exception as e:
            report.add(EvalResult(
                category="1. 응답 형식",
                test_name=f"{mbti} 응답 형식",
                passed=False,
                score=0.0,
                detail=f"오류: {e}",
                latency_ms=(time.time() - start) * 1000,
            ))


# ── 2. MBTI 성격 일관성 ─────────────────────────────────────────

async def eval_mbti_consistency():
    """MBTI 유형별 응답이 성격 특성과 일치하는지 GPT-4o-mini로 평가"""
    print("🔍 [2/5] MBTI 성격 일관성 검증 중...")

    test_pairs = [
        ("ENFP", "너 요즘 뭐 하고 지내?"),
        ("INTJ", "이 문제에 대해 어떻게 생각해?"),
        ("ESFJ", "오늘 기분이 좀 안 좋아..."),
        ("ISTP", "주말에 뭐 할 거야?"),
    ]

    for mbti, message in test_pairs:
        start = time.time()
        try:
            replies, _ = await generate_reply(
                message=message,
                mbti=mbti,
                speech_style="CASUAL",
                relationship="FRIEND",
                nickname="평가자",
                affinity_level=3,
                character_name=f"캐릭터_{mbti}",
            )
            latency = (time.time() - start) * 1000
            response_text = " ".join(r.text for r in replies)

            # GPT-4o-mini로 MBTI 일관성 평가
            eval_prompt = f"""다음은 {mbti} 성격의 AI 캐릭터가 생성한 응답입니다.
이 응답이 {mbti} 성격 특성과 얼마나 일치하는지 0~100 점수로 평가해주세요.

{mbti} 핵심 특성:
- {'외향적(E)' if mbti[0]=='E' else '내향적(I)'}: {'활발하고 적극적' if mbti[0]=='E' else '조용하고 신중함'}
- {'직관적(N)' if mbti[1]=='N' else '감각적(S)'}: {'추상적/미래지향' if mbti[1]=='N' else '현실적/구체적'}
- {'사고형(T)' if mbti[2]=='T' else '감정형(F)'}: {'논리적/분석적' if mbti[2]=='T' else '공감적/감성적'}
- {'판단형(J)' if mbti[3]=='J' else '인식형(P)'}: {'계획적/체계적' if mbti[3]=='J' else '유연/즉흥적'}

사용자 메시지: "{message}"
캐릭터 응답: "{response_text}"

JSON만 출력: {{"score": 0~100, "reason": "이유", "matching_traits": ["일치하는 특성들"], "missing_traits": ["부족한 특성들"]}}"""

            eval_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.2,
                max_tokens=200,
            )

            eval_content = eval_response.choices[0].message.content or ""
            eval_start = eval_content.find("{")
            eval_end = eval_content.rfind("}") + 1
            if eval_start >= 0 and eval_end > eval_start:
                eval_data = json.loads(eval_content[eval_start:eval_end])
                consistency_score = eval_data.get("score", 50) / 100
                reason = eval_data.get("reason", "")
                matching = eval_data.get("matching_traits", [])
                missing = eval_data.get("missing_traits", [])
            else:
                consistency_score = 0.5
                reason = "평가 파싱 실패"
                matching = []
                missing = []

            report.add(EvalResult(
                category="2. MBTI 일관성",
                test_name=f"{mbti} 성격 일관성",
                passed=consistency_score >= 0.6,
                score=consistency_score,
                detail=f"{reason} | 일치: {matching} | 부족: {missing}",
                latency_ms=latency,
            ))

        except Exception as e:
            report.add(EvalResult(
                category="2. MBTI 일관성",
                test_name=f"{mbti} 성격 일관성",
                passed=False,
                score=0.0,
                detail=f"오류: {e}",
            ))


# ── 3. 호감도 분석 정확도 ────────────────────────────────────────

async def eval_affinity_accuracy():
    """호감도 delta가 메시지 감정과 일치하는지 검증"""
    print("🔍 [3/5] 호감도 분석 정확도 검증 중...")

    for scenario in TEST_SCENARIOS:
        start = time.time()
        try:
            delta = await analyze_affinity_with_llm(
                message=scenario["message"],
                affinity_level=3,
                char_mbti="ENFP",
            )
            latency = (time.time() - start) * 1000

            expected = scenario["expected_direction"]
            if expected == "positive":
                correct = delta > 0
                score = min(delta / 3, 1.0) if delta > 0 else 0.0
            elif expected == "negative":
                correct = delta < 0
                score = min(abs(delta) / 2, 1.0) if delta < 0 else 0.0
            else:  # neutral
                correct = -1 <= delta <= 1
                score = 1.0 if delta == 0 else (0.7 if abs(delta) == 1 else 0.3)

            report.add(EvalResult(
                category="3. 호감도 분석",
                test_name=f"{scenario['label']}",
                passed=correct,
                score=score,
                detail=f"delta={delta}, 기대={expected}",
                latency_ms=latency,
            ))

        except Exception as e:
            report.add(EvalResult(
                category="3. 호감도 분석",
                test_name=f"{scenario['label']}",
                passed=False,
                score=0.0,
                detail=f"오류: {e}",
            ))

    # 키워드 기반 vs LLM 비교
    print("  → 키워드 vs LLM 비교 중...")
    discrepancy_count = 0
    for scenario in TEST_SCENARIOS[:5]:
        keyword_delta = calculate_affinity_delta(
            scenario["message"], 3, None, None, "ENFP"
        )
        llm_delta = await analyze_affinity_with_llm(
            scenario["message"], 3, "ENFP"
        )
        if (keyword_delta > 0) != (llm_delta > 0) and keyword_delta != 0 and llm_delta != 0:
            discrepancy_count += 1

    agreement_rate = 1.0 - (discrepancy_count / 5)
    report.add(EvalResult(
        category="3. 호감도 분석",
        test_name="키워드-LLM 일치율",
        passed=agreement_rate >= 0.6,
        score=agreement_rate,
        detail=f"불일치: {discrepancy_count}/5",
    ))


# ── 4. 메모리 추출 품질 ─────────────────────────────────────────

async def eval_memory_extraction():
    """대화에서 핵심 정보를 정확히 추출하는지 검증"""
    print("🔍 [4/5] 메모리 추출 품질 검증 중...")

    start = time.time()
    try:
        # 대화 요약 테스트
        summary = await summarize_conversation(
            character_name="평가캐릭터",
            nickname="수진",
            conversation_history=MEMORY_TEST_CONVERSATIONS,
        )
        summary_latency = (time.time() - start) * 1000

        # 요약에 핵심 정보가 포함되어 있는지
        key_info = ["수진", "디자이너", "그림", "카페", "파스타", "이직"]
        found = sum(1 for k in key_info if k in summary)
        summary_score = found / len(key_info)

        report.add(EvalResult(
            category="4. 메모리 추출",
            test_name="대화 요약 품질",
            passed=summary_score >= 0.5,
            score=summary_score,
            detail=f"포함된 핵심 정보: {found}/{len(key_info)} | 요약: {summary[:80]}...",
            latency_ms=summary_latency,
        ))

        # 핵심 정보 추출 테스트
        start2 = time.time()
        facts = await extract_facts(
            character_name="평가캐릭터",
            nickname="수진",
            conversation_history=MEMORY_TEST_CONVERSATIONS,
        )
        facts_latency = (time.time() - start2) * 1000

        # 추출된 사실에 핵심 키워드가 있는지
        facts_text = " ".join(facts)
        fact_keywords = ["수진", "26", "디자이너", "그림", "카페", "파스타", "민트초코", "이직"]
        facts_found = sum(1 for k in fact_keywords if k in facts_text)
        facts_score = facts_found / len(fact_keywords)

        report.add(EvalResult(
            category="4. 메모리 추출",
            test_name="핵심 정보 추출",
            passed=facts_score >= 0.5,
            score=facts_score,
            detail=f"포함된 키워드: {facts_found}/{len(fact_keywords)} | 추출: {facts[:3]}...",
            latency_ms=facts_latency,
        ))

    except Exception as e:
        report.add(EvalResult(
            category="4. 메모리 추출",
            test_name="메모리 추출",
            passed=False,
            score=0.0,
            detail=f"오류: {e}",
        ))


# ── 5. 호감도 레벨별 응답 차이 ───────────────────────────────────

async def eval_affinity_level_behavior():
    """호감도 1 vs 5에서 응답 톤이 달라지는지 검증"""
    print("🔍 [5/5] 호감도 레벨별 응답 차이 검증 중...")

    message = "오늘 하루 어땠어?"
    mbti = "ENFP"

    responses = {}
    for level in [1, 5]:
        start = time.time()
        replies, _ = await generate_reply(
            message=message,
            mbti=mbti,
            speech_style="CASUAL",
            relationship="FRIEND",
            nickname="테스터",
            affinity_level=level,
            character_name="친구캐릭터",
        )
        latency = (time.time() - start) * 1000
        text = " ".join(r.text for r in replies)
        emotions = [r.emotion for r in replies]
        responses[level] = {"text": text, "emotions": emotions, "latency": latency}

    # GPT-4o-mini로 차이 평가
    eval_prompt = f"""아래는 같은 캐릭터가 호감도 1(낯선 사이)과 5(깊은 관계)에서 같은 질문에 대해 한 응답입니다.

호감도 1 응답: "{responses[1]['text']}"
호감도 5 응답: "{responses[5]['text']}"

두 응답의 톤, 친밀도, 말투 차이를 0~100으로 평가해주세요.
- 0: 차이 없음 (나쁨)
- 50: 약간의 차이
- 100: 명확한 차이 (좋음 - 호감도 1은 거리감, 5는 친밀함)

JSON만 출력: {{"difference_score": 0~100, "level1_tone": "설명", "level5_tone": "설명", "analysis": "분석"}}"""

    eval_response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": eval_prompt}],
        temperature=0.2,
        max_tokens=200,
    )

    eval_content = eval_response.choices[0].message.content or ""
    try:
        eval_start = eval_content.find("{")
        eval_end = eval_content.rfind("}") + 1
        eval_data = json.loads(eval_content[eval_start:eval_end])
        diff_score = eval_data.get("difference_score", 50) / 100
        analysis = eval_data.get("analysis", "")
    except Exception:
        diff_score = 0.5
        analysis = "평가 파싱 실패"

    avg_latency = (responses[1]["latency"] + responses[5]["latency"]) / 2

    report.add(EvalResult(
        category="5. 호감도 레벨 차이",
        test_name="레벨 1 vs 5 톤 차이",
        passed=diff_score >= 0.5,
        score=diff_score,
        detail=f"{analysis} | L1감정={responses[1]['emotions']} L5감정={responses[5]['emotions']}",
        latency_ms=avg_latency,
    ))

    # 존댓말/반말 차이 확인
    l1_text = responses[1]["text"]
    l5_text = responses[5]["text"]

    honorific_markers = ["요", "니다", "세요", "습니다", "에요"]
    casual_markers = ["야", "어", "지", "냐", "ㅋ", "ㅎ"]

    l1_formal = sum(1 for m in honorific_markers if m in l1_text)
    l5_casual = sum(1 for m in casual_markers if m in l5_text)

    # 호감도 1은 격식, 5는 비격식이면 좋음
    formality_score = min((l1_formal + l5_casual) / 6, 1.0)

    report.add(EvalResult(
        category="5. 호감도 레벨 차이",
        test_name="말투 변화 (격식↔비격식)",
        passed=formality_score >= 0.3,
        score=formality_score,
        detail=f"L1 격식 마커={l1_formal}, L5 비격식 마커={l5_casual}",
    ))


# ── 메인 실행 ────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("  MBTI Chat 모델 성능 평가 시작")
    print("  평가 모델: gpt-4o (채팅), gpt-4o-mini (호감도/메모리)")
    print("=" * 70)

    total_start = time.time()

    await eval_response_format()
    await eval_mbti_consistency()
    await eval_affinity_accuracy()
    await eval_memory_extraction()
    await eval_affinity_level_behavior()

    total_time = time.time() - total_start

    report.print_report()
    print(f"\n  ⏱️  총 평가 시간: {total_time:.1f}초")

    # JSON 리포트 저장
    json_report = {
        "eval_time_seconds": round(total_time, 1),
        "summary": report.summary(),
        "details": [
            {
                "category": r.category,
                "test": r.test_name,
                "passed": r.passed,
                "score": round(r.score, 3),
                "detail": r.detail,
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in report.results
        ],
    }
    with open("eval_report.json", "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    print(f"  📄 상세 리포트 저장: eval_report.json\n")


if __name__ == "__main__":
    asyncio.run(main())
