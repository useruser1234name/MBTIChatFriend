"""
100회+ 대화 품질 평가 스크립트
- 16 MBTI 유형 x 다양한 시나리오
- 응답 형식 검증, 감정 코드 검증, 응답 시간 측정
- 캐릭터 일관성, 안전 필터 테스트
"""

import json
import time
import sys
import re
import httpx
from dataclasses import dataclass, field
from collections import Counter

BASE_URL = "http://localhost:8090/api/v1"
TIMEOUT = 60.0

ALL_MBTI = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

VALID_EMOTIONS = {
    "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
    "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
}

SPEECH_STYLES = ["CASUAL", "FORMAL", "TSUNDERE", "SWEET"]

# 시나리오별 테스트 메시지
SCENARIOS = {
    "인사": [
        "안녕! 오늘 뭐했어?",
        "하이~ 오랜만이다!",
        "좋은 아침이야!",
    ],
    "일상대화": [
        "오늘 점심에 파스타 먹었는데 진짜 맛있었어",
        "주말에 영화 보러 갈 건데 뭐 추천해줄 수 있어?",
        "요즘 날씨가 너무 좋다 어디 놀러 갈까?",
        "나 어제 새로운 카페 발견했어!",
        "오늘 출근길에 귀여운 강아지를 봤어",
    ],
    "감정대화": [
        "오늘 시험 망쳤어... 진짜 속상해",
        "나 너무 기뻐! 합격했어!!",
        "요즘 왜 이렇게 피곤한지 모르겠어",
        "친구랑 싸웠는데 어떡하지",
        "고민이 있는데 들어줄 수 있어?",
    ],
    "깊은대화": [
        "너는 행복이 뭐라고 생각해?",
        "진짜 친구가 뭔지 잘 모르겠어 가끔",
        "나중에 어떤 사람이 되고 싶어?",
        "요즘 의미 없이 시간만 흘러가는 느낌이야",
    ],
    "장난/유머": [
        "야 나 사실 외계인이야 ㅋㅋㅋ",
        "너 없으면 나 어떡해~ ㅎㅎ",
        "오늘 운세 봤는데 대박 운이래!",
    ],
    "칭찬": [
        "너 말 진짜 잘한다 대단해",
        "너랑 얘기하면 항상 기분이 좋아져",
        "넌 진짜 착한 것 같아",
    ],
    "짧은반응": [
        "ㅋㅋㅋ",
        "응",
        "그래?",
        "ㅎㅎ 좋아",
        "오키",
    ],
    "안전필터": [
        "죽여주는 맛집 추천해줘",  # 허용 (오탐 방지)
        "이 영화에서 살인 사건이 나오는데 무서웠어",  # 허용 (미디어 맥락)
    ],
}


@dataclass
class TestResult:
    test_id: int
    mbti: str
    scenario: str
    message: str
    speech_style: str
    affinity_level: int
    # 결과
    success: bool = False
    response_time_ms: float = 0
    reply_count: int = 0
    emotions: list = field(default_factory=list)
    total_text_len: int = 0
    json_valid: bool = False
    emotion_valid: bool = False
    has_emoji: bool = False
    error: str = ""


def send_chat(mbti: str, message: str, style: str = "CASUAL",
              affinity_level: int = 1, nickname: str = "테스터",
              history: list = None) -> dict:
    """채팅 API 호출"""
    payload = {
        "message": message,
        "mbti": mbti,
        "speech_style": style,
        "relationship": "FRIEND",
        "nickname": nickname,
        "affinity_level": affinity_level,
        "conversation_history": history or [],
        "character_name": f"{mbti}_캐릭터",
        "character_id": f"test_{mbti.lower()}",
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(f"{BASE_URL}/chat/send", json=payload)
        resp.raise_for_status()
        return resp.json()


def check_emoji(text: str) -> bool:
    """이모지/유니코드 그림문자 포함 여부"""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001f900-\U0001f9FF"
        "\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF"
        "\U0000FE00-\U0000FE0F\U0000200D]+",
        flags=re.UNICODE,
    )
    return bool(emoji_pattern.search(text))


def analyze_result(result: TestResult) -> dict:
    """단일 결과 분석"""
    issues = []
    if not result.json_valid:
        issues.append("JSON_INVALID")
    if not result.emotion_valid:
        issues.append("EMOTION_INVALID")
    if result.has_emoji:
        issues.append("EMOJI_DETECTED")
    if result.reply_count == 0:
        issues.append("EMPTY_REPLY")
    if result.reply_count > 5:
        issues.append("TOO_MANY_PARTS")
    if result.total_text_len < 2:
        issues.append("TOO_SHORT")
    if result.total_text_len > 2000:
        issues.append("TOO_LONG")
    if result.response_time_ms > 30000:
        issues.append("SLOW_RESPONSE")
    return {"issues": issues, "quality": "PASS" if not issues else "FAIL"}


def run_tests():
    results: list[TestResult] = []
    test_id = 0

    print("=" * 70)
    print("  MBTI Chat Quality Test - 100+ Conversations")
    print("=" * 70)

    # 테스트 매트릭스 구성
    test_cases = []

    # 1) 모든 MBTI x 기본 시나리오 (16 * 2 = 32)
    for mbti in ALL_MBTI:
        test_cases.append((mbti, "인사", SCENARIOS["인사"][0], "CASUAL", 1))
        test_cases.append((mbti, "일상대화", SCENARIOS["일상대화"][0], "CASUAL", 2))

    # 2) 감정 대화 - 다양한 MBTI (5 * 4 = 20)
    feeling_types = ["INFP", "ENFJ", "ISFJ", "ESFP"]
    for mbti in feeling_types:
        for msg in SCENARIOS["감정대화"]:
            test_cases.append((mbti, "감정대화", msg, "CASUAL", 3))

    # 3) 깊은 대화 - 사고형 (4 * 4 = 16)
    thinking_types = ["INTJ", "INTP", "ENTJ", "ENTP"]
    for mbti in thinking_types:
        for msg in SCENARIOS["깊은대화"]:
            test_cases.append((mbti, "깊은대화", msg, "CASUAL", 4))

    # 4) 장난/유머 - 외향형 (3 * 4 = 12)
    extroverts = ["ENFP", "ESTP", "ESFP", "ENTP"]
    for mbti in extroverts:
        for msg in SCENARIOS["장난/유머"]:
            test_cases.append((mbti, "장난/유머", msg, "CASUAL", 3))

    # 5) 말투 스타일 테스트 (4 * 2 = 8)
    for style in SPEECH_STYLES:
        test_cases.append(("INFP", "일상대화", "오늘 하루 어땠어?", style, 2))
        test_cases.append(("ENTJ", "일상대화", "주말 계획 있어?", style, 3))

    # 6) 호감도 단계별 (5 * 2 = 10)
    for level in range(1, 6):
        test_cases.append(("INFJ", "칭찬", SCENARIOS["칭찬"][0], "CASUAL", level))
        test_cases.append(("ESTP", "칭찬", SCENARIOS["칭찬"][1], "CASUAL", level))

    # 7) 짧은 반응 (5)
    for msg in SCENARIOS["짧은반응"]:
        test_cases.append(("ISFP", "짧은반응", msg, "CASUAL", 2))

    # 8) 안전 필터 (허용 목록 테스트) (2)
    for msg in SCENARIOS["안전필터"]:
        test_cases.append(("ENFJ", "안전필터", msg, "CASUAL", 2))

    # 9) 연속 대화 (멀티턴) (5)
    multi_turn_msgs = [
        "안녕! 오늘 기분 어때?",
        "나는 좀 피곤해... 어제 늦게 잤거든",
        "ㅋㅋ 그래도 네 덕분에 좀 나아진다",
        "고마워! 너는 진짜 좋은 친구야",
        "우리 다음에 같이 뭐 하자!",
    ]
    history = []
    for msg in multi_turn_msgs:
        test_cases.append(("ENFP", "멀티턴", msg, "CASUAL", 3))

    total = len(test_cases)
    print(f"\n총 {total}개 테스트 케이스 준비 완료\n")

    multi_turn_history = []
    fail_count = 0

    for i, (mbti, scenario, message, style, level) in enumerate(test_cases):
        test_id = i + 1
        result = TestResult(
            test_id=test_id,
            mbti=mbti,
            scenario=scenario,
            message=message,
            speech_style=style,
            affinity_level=level,
        )

        # 멀티턴이면 히스토리 누적
        hist = multi_turn_history if scenario == "멀티턴" else []

        try:
            start = time.time()
            resp = send_chat(mbti, message, style, level, history=hist)
            elapsed = (time.time() - start) * 1000
            result.response_time_ms = round(elapsed, 1)

            replies = resp.get("replies", [])
            result.reply_count = len(replies)
            result.json_valid = True

            if replies:
                result.emotions = [r.get("emotion", "") for r in replies]
                result.emotion_valid = all(e in VALID_EMOTIONS for e in result.emotions)
                texts = [r.get("text", "") for r in replies]
                result.total_text_len = sum(len(t) for t in texts)
                result.has_emoji = any(check_emoji(t) for t in texts)
                full_text = " ".join(texts)

                # 멀티턴 히스토리 누적
                if scenario == "멀티턴":
                    multi_turn_history.append({"role": "user", "content": message})
                    multi_turn_history.append({"role": "assistant", "content": full_text})

            result.success = True

        except httpx.HTTPStatusError as e:
            result.error = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
        except Exception as e:
            result.error = str(e)[:100]

        results.append(result)

        # 분석
        analysis = analyze_result(result)
        status = "PASS" if analysis["quality"] == "PASS" else "FAIL"
        if status == "FAIL":
            fail_count += 1

        # 진행률 출력
        emotions_str = ",".join(result.emotions[:3]) if result.emotions else "N/A"
        marker = "O" if status == "PASS" else "X"
        print(
            f"[{marker}] #{test_id:3d}/{total} | {mbti} | {scenario:<8s} | "
            f"{result.response_time_ms:6.0f}ms | "
            f"parts={result.reply_count} | emotions={emotions_str} | "
            f"len={result.total_text_len}"
            + (f" | ISSUES: {analysis['issues']}" if analysis["issues"] else "")
        )

        # rate limit 방지
        if test_id % 5 == 0:
            time.sleep(0.5)

    # ========== 종합 리포트 ==========
    print("\n" + "=" * 70)
    print("  ANALYSIS REPORT")
    print("=" * 70)

    total_tests = len(results)
    passed = sum(1 for r in results if analyze_result(r)["quality"] == "PASS")
    failed = total_tests - passed

    print(f"\n## 전체 결과: {passed}/{total_tests} PASS ({passed/total_tests*100:.1f}%)")
    print(f"   실패: {failed}건")

    # 응답 시간 분석
    times = [r.response_time_ms for r in results if r.success]
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"\n## 응답 시간")
        print(f"   평균: {avg_time:.0f}ms | 최소: {min_time:.0f}ms | 최대: {max_time:.0f}ms | P95: {p95:.0f}ms")

    # 감정 분포
    all_emotions = []
    for r in results:
        all_emotions.extend(r.emotions)
    emotion_counts = Counter(all_emotions)
    print(f"\n## 감정 코드 분포 (총 {len(all_emotions)}개)")
    for emotion, count in emotion_counts.most_common():
        bar = "#" * (count // 2)
        print(f"   {emotion:<12s}: {count:3d} ({count/len(all_emotions)*100:5.1f}%) {bar}")

    # 이모지 위반
    emoji_violations = sum(1 for r in results if r.has_emoji)
    print(f"\n## 이모지 위반: {emoji_violations}/{total_tests}건")

    # 감정 유효성
    emotion_invalid = sum(1 for r in results if not r.emotion_valid and r.success)
    print(f"## 감정 코드 무효: {emotion_invalid}/{total_tests}건")

    # JSON 형식 실패
    json_invalid = sum(1 for r in results if not r.json_valid)
    print(f"## JSON 파싱 실패: {json_invalid}/{total_tests}건")

    # 시나리오별 성공률
    print(f"\n## 시나리오별 성공률")
    scenario_groups = {}
    for r in results:
        if r.scenario not in scenario_groups:
            scenario_groups[r.scenario] = {"pass": 0, "fail": 0, "times": []}
        a = analyze_result(r)
        if a["quality"] == "PASS":
            scenario_groups[r.scenario]["pass"] += 1
        else:
            scenario_groups[r.scenario]["fail"] += 1
        if r.success:
            scenario_groups[r.scenario]["times"].append(r.response_time_ms)

    for scenario, data in scenario_groups.items():
        total_s = data["pass"] + data["fail"]
        rate = data["pass"] / total_s * 100 if total_s > 0 else 0
        avg_t = sum(data["times"]) / len(data["times"]) if data["times"] else 0
        print(f"   {scenario:<10s}: {data['pass']}/{total_s} ({rate:5.1f}%) | 평균 {avg_t:.0f}ms")

    # MBTI별 성공률
    print(f"\n## MBTI별 성공률")
    mbti_groups = {}
    for r in results:
        if r.mbti not in mbti_groups:
            mbti_groups[r.mbti] = {"pass": 0, "fail": 0, "times": []}
        a = analyze_result(r)
        if a["quality"] == "PASS":
            mbti_groups[r.mbti]["pass"] += 1
        else:
            mbti_groups[r.mbti]["fail"] += 1
        if r.success:
            mbti_groups[r.mbti]["times"].append(r.response_time_ms)

    for mbti in ALL_MBTI:
        if mbti in mbti_groups:
            data = mbti_groups[mbti]
            total_m = data["pass"] + data["fail"]
            rate = data["pass"] / total_m * 100 if total_m > 0 else 0
            avg_t = sum(data["times"]) / len(data["times"]) if data["times"] else 0
            print(f"   {mbti}: {data['pass']}/{total_m} ({rate:5.1f}%) | 평균 {avg_t:.0f}ms")

    # 호감도 단계별 응답 길이
    print(f"\n## 호감도 단계별 평균 응답 길이")
    level_lens = {}
    for r in results:
        if r.success:
            if r.affinity_level not in level_lens:
                level_lens[r.affinity_level] = []
            level_lens[r.affinity_level].append(r.total_text_len)
    for level in sorted(level_lens.keys()):
        lens = level_lens[level]
        avg_len = sum(lens) / len(lens)
        print(f"   Level {level}: 평균 {avg_len:.0f}자 ({len(lens)}건)")

    # 이슈 상세 (실패 건)
    all_issues = Counter()
    for r in results:
        a = analyze_result(r)
        for issue in a["issues"]:
            all_issues[issue] += 1

    if all_issues:
        print(f"\n## 이슈 유형별 빈도")
        for issue, count in all_issues.most_common():
            print(f"   {issue}: {count}건")

    # 실패 상세 출력
    failed_results = [r for r in results if analyze_result(r)["quality"] == "FAIL"]
    if failed_results:
        print(f"\n## 실패 건 상세 (최대 10건)")
        for r in failed_results[:10]:
            a = analyze_result(r)
            print(f"   #{r.test_id} {r.mbti}/{r.scenario}: {a['issues']} | msg='{r.message[:30]}' | err={r.error[:50] if r.error else 'N/A'}")

    print("\n" + "=" * 70)
    print(f"  테스트 완료: {passed}/{total_tests} PASS")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
