"""M1 12셀 블라인드 채점 패킷 + 답안지 생성기.

eval_m1_generate.py 가 만든 두 arm의 jsonl을 읽어
  docs/EVAL_M1_RESPONSES_2026-08.md   (채점자용 — arm 라벨 없음)
  docs/EVAL_M1_ANSWER_KEY_2026-08.md  (배정표 + 객관 지표 — 채점 후 열람)
을 만든다.

사용:
    python tools/eval_m1_packet.py --before <before.jsonl> --after <after.jsonl>
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"

PROBES = {
    "T1": ["E", "E", "S", "P", "E"],
    "T2": ["E", "P", "E", "S", "P"],
    "T3": ["E", "E", "P", "S", "P"],
}
TIER_META = {
    "T1": (2, "S1 — 아는 사이·편해지는 중",
           "위로는 하되 자기 속마음/과거사를 다 풀지 않음. 4턴(P)에서 짧게만 내줌."),
    "T2": (4, "S2 — 썸",
           "2·5턴(P)에서 감정을 슬쩍 인정하되 '왜 그런지'는 설명하지 않음."),
    "T3": (5, "S3 — 연인",
           "3턴(P)에서 직접 애정 표현 OK(회피하면 감점). "
           "5턴(P)은 애정 표현하되 자기 감정을 분석·해설하지 않음."),
}
PROBE_DESC = {"E": "감정 상황", "S": "짧은 대답/침묵", "P": "속마음 캐묻기"}

# 채점 기준 §4.1 의 정형 위로 문구 목록 (객관 카운트용)
FORMULAIC = [
    "내가 들어줄게", "나한테 다 얘기해", "무리하지 마", "무리하면 안 돼",
    "괜찮아, 내가 여기 있잖아", "다 말해줘", "내가 안아줄게", "내가 여기 있잖아",
]


def load(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[(r["mbti"], r["tier"])] = r
    return out


def render_bubbles(turn: dict) -> str:
    """말풍선들을 마크다운 표 셀 하나로 렌더."""
    parts = []
    for b in turn["bubbles"]:
        text = b["text"].replace("|", "\\|").replace("\n", " ")
        parts.append(f"`{b['emotion']}` {text}")
    return "<br>".join(parts)


def ends_with_question(turn: dict) -> bool:
    if not turn["bubbles"]:
        return False
    return turn["bubbles"][-1]["text"].rstrip().endswith(("?", "？"))


def formulaic_hits(rec: dict) -> list[str]:
    hits = []
    for t in rec["turns"]:
        for b in t["bubbles"]:
            for p in FORMULAIC:
                if p in b["text"]:
                    hits.append(f"T{t['turn']}:{p}")
    return hits


def arm_metrics(rec: dict) -> dict:
    q = sum(1 for t in rec["turns"] if ends_with_question(t))
    chars = sum(len(b["text"]) for t in rec["turns"] for b in t["bubbles"])
    bubbles = sum(len(t["bubbles"]) for t in rec["turns"])
    return {
        "question_end_turns": q,
        "formulaic": formulaic_hits(rec),
        "avg_chars_per_turn": round(chars / max(1, len(rec["turns"]))),
        "bubbles": bubbles,
    }


HEADER = """# M1 disclosure 게이팅 — 블라인드 채점 패킷 (2026-08)

> 절차 원본: `docs/EVAL_KIT_M1_disclosure_2026-08.md`
> 배정표: `docs/EVAL_M1_ANSWER_KEY_2026-08.md` — **채점을 모두 끝내기 전에는 열지 마세요.**

이 문서는 같은 캐릭터·같은 호감도·같은 유저 발화 5턴에 대해
**두 가지 프롬프트 버전**이 만든 응답을 A/B로 나란히 놓은 것입니다.
어느 쪽이 어느 버전인지는 셀마다 무작위로 섞여 있습니다(셀별로 다릅니다 —
A가 계속 같은 버전이 아닙니다).

## 채점 방법

셀마다 A와 B의 5턴 대화를 처음부터 끝까지 읽고, 아래 세 항목을 **각각 1·2·3점**으로 매깁니다.
A와 B는 독립적으로 채점합니다(둘 다 3점이어도, 둘 다 1점이어도 됩니다).

### (1) 톤 일관성 — 이 호감도 단계에 맞는 개방 수위인가

| 점수 | 기준 |
|---|---|
| 3 | 5턴 내내 단계에 맞음. Lv2/Lv4는 감춤·여지 유지, Lv5는 애정을 회피하지 않음 |
| 2 | 대체로 맞으나 1턴 정도 톤이 튐 |
| 1 | 단계와 어긋남(Lv2인데 다 털어놓음 / Lv5인데 계속 밀어냄) 또는 턴마다 요동 |

### (2) 사람다움 — 실제 사람이 보낸 메시지처럼 읽히는가

| 점수 | 기준 |
|---|---|
| 3 | 정형 위로 문구 없음. 질문으로 끝나는 턴 ≤ 2/5. 자기 이야기·행동으로 끝나는 턴 존재 |
| 2 | 정형 문구 1회 또는 질문 종결 3/5 |
| 1 | 정형 문구 반복, 또는 5턴 중 4턴 이상 질문 종결 |

> 정형 문구 참고: `내가 들어줄게` `나한테 다 얘기해` `무리하지 마` `무리하면 안 돼`
> `괜찮아, 내가 여기 있잖아` `다 말해줘` `내가 안아줄게`
> 단 **ISFJ의 고유 말버릇 `괜찮아? 무리하면 안 돼...` 는 캐릭터 설정이므로 감점하지 않습니다.**

### (3) 과설명 여부 (역채점 — 높을수록 좋음)

| 점수 | 기준 |
|---|---|
| 3 | 자기 감정 해설 0회. 행동·말투·회피·침묵으로 전달 |
| 2 | 1회 (특히 P 프로브 턴에서 슬쩍) |
| 1 | 2회 이상, 또는 "이건 내 방어기제야" / "널 좋아해서 그런 것 같아" 류 직접 분석 |

### 프로브 표기

각 턴 옆의 **(E)/(S)/(P)** 는 그 유저 발화의 의도입니다.
- **E 감정 상황** — 톤 일관성을 봅니다
- **S 짧은 대답/침묵** — 억지 질문으로 때우는지 봅니다
- **P 속마음 캐묻기** — 호감도 단계에 맞는 개방 수위인지 봅니다 (단계마다 정답이 다름)

### 표기

말풍선 앞의 `HAPPY` 같은 대문자는 그 말풍선에 붙은 감정 코드입니다(앱에서 표정으로 표시됨).
채점 대상에 포함해 읽되, 감정 코드만 따로 점수 매기지는 않습니다.

---
"""

FOOTER_FORM = """
---

## 집계표 (채점 끝난 뒤 작성)

| 셀 | A 합계 | B 합계 | 승자(A/B/동률) |
|---|---|---|---|
| INTJ-T1 | | | |
| INTJ-T2 | | | |
| INTJ-T3 | | | |
| INFP-T1 | | | |
| INFP-T2 | | | |
| INFP-T3 | | | |
| ISFJ-T1 | | | |
| ISFJ-T2 | | | |
| ISFJ-T3 | | | |
| ESFP-T1 | | | |
| ESFP-T2 | | | |
| ESFP-T3 | | | |

이 표를 다 채운 **다음에** `docs/EVAL_M1_ANSWER_KEY_2026-08.md` 를 열어
A/B를 before/after로 치환하고, 셀마다 `after 합계 >= before 합계` 인지 셉니다.

- **통과 셀 9개 이상 → M1 채택**
- 8개 이하 → 롤백 후 재설계
- 추가 보류 조건: Lv5(T3) 셀 4개 중 2개 이상에서 after가 before보다 **차갑게** 느껴지면,
  셀 수와 무관하게 보류합니다. 채점 중 T3 셀에서 그런 인상을 받았다면 메모에 남겨 주세요.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--seed", type=int, default=20260811)
    a = ap.parse_args()

    before = load(Path(a.before))
    after = load(Path(a.after))
    assert set(before) == set(after), "두 arm의 셀 집합이 다르다"

    rng = random.Random(a.seed)
    order = [(m, t) for m in ["INTJ", "INFP", "ISFJ", "ESFP"] for t in ["T1", "T2", "T3"]]
    # 균형 배정: A=after 인 셀이 정확히 6개가 되도록 섞는다.
    # 순수 무작위(coin flip)로 두면 10:2 같은 쏠림이 나와 채점자가 패턴을 눈치챌 수 있다.
    # 티어별로도 2:2가 되게 층화(stratify)해 티어 단위 쏠림도 막는다.
    flips: dict[tuple, bool] = {}
    for tier in ["T1", "T2", "T3"]:
        pattern = [True, True, False, False]
        rng.shuffle(pattern)
        for (m, _), f in zip([c for c in order if c[1] == tier], pattern):
            flips[(m, tier)] = f

    sheet = [HEADER]
    key_rows = []
    metrics_rows = []
    fmt_total = fmt_strict_fail = fmt_retry = 0
    bad_emotion = 0
    _mc: dict[str, int] = {}
    for rec in after.values():
        for t in rec["turns"]:
            _mc[t["model"]] = _mc.get(t["model"], 0) + 1
    model_dist = ", ".join(f"{m} {n}/60턴" for m, n in sorted(_mc.items()))

    for n, (mbti, tier) in enumerate(order, start=1):
        b, af = before[(mbti, tier)], after[(mbti, tier)]
        flip = flips[(mbti, tier)]
        A, B = (af, b) if flip else (b, af)
        key_rows.append((f"{mbti}-{tier}", "after" if flip else "before",
                         "before" if flip else "after"))
        metrics_rows.append((f"{mbti}-{tier}", arm_metrics(b), arm_metrics(af)))

        level, scen, expect = TIER_META[tier]
        sheet.append(f"\n## 셀 {n}/12 — {mbti} · 호감도 Lv{level}\n")
        sheet.append(f"시나리오 {scen}. 말투 CASUAL, 관계 FRIEND, 호칭 '유저'.\n")
        sheet.append(f"> 이 단계의 기대 동작: {expect}\n")

        for t, probe in zip(af["turns"], PROBES[tier]):
            tb = next(x for x in A["turns"] if x["turn"] == t["turn"])
            tb2 = next(x for x in B["turns"] if x["turn"] == t["turn"])
            sheet.append(
                f"\n**턴 {t['turn']} — 유저: 「{t['user']}」  ({probe} {PROBE_DESC[probe]})**\n")
            sheet.append("\n| A | B |\n|---|---|\n")
            sheet.append(f"| {render_bubbles(tb)} | {render_bubbles(tb2)} |\n")

        sheet.append(f"""
**채점 — {mbti}-{tier} (Lv{level})**   채점자: ______   날짜: ______

| 항목 | A | B |
|---|---|---|
| (1) 톤 일관성 | [ ] | [ ] |
| (2) 사람다움 | [ ] | [ ] |
| (3) 과설명 여부(역) | [ ] | [ ] |
| **합계 (3~9)** | [ ] | [ ] |

승자: ☐ A  ☐ B  ☐ 동률
메모(감점 사유 한 줄):

---
""")

        for rec in (b, af):
            for t in rec["turns"]:
                fmt_total += 1
                if not t["strict_ok"]:
                    fmt_strict_fail += 1
                if t["attempts"] > 1:
                    fmt_retry += 1
                for bb in t["bubbles"]:
                    if bb["emotion"] == "PARSE_FAILED":
                        bad_emotion += 1

    sheet.append(FOOTER_FORM)
    sheet.append(f"""
---

## 부록 — 형식 무결성 점검 (EVAL_KIT §0 보류 조건 / §5-2)

응답 생성 중 자동 집계한 결과입니다. 채점 항목이 아니라 배포 게이트의 **안전 조건** 판정용입니다.

| 항목 | 값 |
|---|---|
| 총 응답(턴) 수 | {fmt_total} (12셀 × 5턴 × 2 arm) |
| JSON 배열 파싱 최종 실패 | **{fmt_strict_fail}** |
| 무효 emotion 코드 | **{bad_emotion}** |
| 형식 재시도 발생 턴 | {fmt_retry} |

EVAL_KIT §0: *"후 응답 중 JSON 파싱 실패 또는 무효 emotion 코드가 1건이라도 나오면 보류"*
→ 최종 실패 {fmt_strict_fail}건, 무효 emotion {bad_emotion}건.

### 생성 조건 (두 버전 완전 동일)

| 항목 | 값 |
|---|---|
| 모델 | 메인 앱과 동일한 복잡도 라우팅 사용 ({model_dist}). 60턴 전부 두 버전이 **같은 모델**로 생성됨 |
| temperature / max_tokens | 0.85 / 1200 (프로덕션 채팅 경로와 동일) |
| seed | 20260811 (양쪽 동일 — 샘플링 잡음 축소) |
| 프롬프트 조립 | `chat_service._build_chat_messages` 공유. `build_system_prompt` 심볼만 교체 |
| 히스토리 | 프로덕션과 동일하게 유저 원문 1건 + 말풍선별 assistant 1건씩 누적 |
| 형식 재시도 | 프로덕션 품질 게이트와 동일(quick_score < 0.4 시 1회, ≤0.2면 형식 환기 메시지 첨부) |

두 버전 사이에서 다른 것은 `server/app/prompts.py` 단 하나뿐입니다.
""")

    DOCS.mkdir(exist_ok=True)
    (DOCS / "EVAL_M1_RESPONSES_2026-08.md").write_text("".join(sheet), encoding="utf-8")

    key = ["""# M1 블라인드 배정표 + 객관 지표 (2026-08)

> ⚠ **채점을 모두 끝낸 뒤에 여세요.** 이 문서를 먼저 보면 12셀 평가가 무효가 됩니다.

## A/B 배정

| 셀 | A | B |
|---|---|---|
"""]
    for cell, aa, bb in key_rows:
        key.append(f"| {cell} | {aa} | {bb} |\n")

    key.append(f"""
배정 난수 시드: `{a.seed}` (`server/tools/eval_m1_packet.py --seed`).

- **before** = `git show ce515aa~1:server/app/prompts.py` (M1 직전)
- **after** = 현재 워킹 트리 `server/app/prompts.py` (M1 반영, ce515aa)

## 집계

셀별로 `after 합계 >= before 합계` 이면 통과. **9/12 이상이면 M1 채택.**

| 셀 | before 합 | after 합 | after ≥ before? |
|---|---|---|---|
""")
    for cell, _, _ in key_rows:
        key.append(f"| {cell} | | | |\n")
    key.append("| **통과 셀 수** | | | **__ / 12 (게이트: ≥9)** |\n")

    key.append("""
## 참고 — 자동 집계한 객관 지표 (채점 점수가 아님)

사람 채점이 게이트입니다. 아래는 채점 결과를 해석할 때 참고만 하세요.
`질문종결`은 마지막 말풍선이 `?`로 끝난 턴 수(5턴 중),
`정형문구`는 EVAL_KIT §4.1 목록에 걸린 횟수(ISFJ 고유 말버릇 제외 안 함 — 육안 확인 필요),
`평균길이`는 턴당 총 글자 수입니다.

| 셀 | before 질문종결 | after 질문종결 | before 정형문구 | after 정형문구 | before 평균길이 | after 평균길이 |
|---|---|---|---|---|---|---|
""")
    for cell, mb, ma in metrics_rows:
        key.append(
            f"| {cell} | {mb['question_end_turns']}/5 | {ma['question_end_turns']}/5 "
            f"| {len(mb['formulaic'])} | {len(ma['formulaic'])} "
            f"| {mb['avg_chars_per_turn']} | {ma['avg_chars_per_turn']} |\n")

    tot_qb = sum(m[1]["question_end_turns"] for m in metrics_rows)
    tot_qa = sum(m[2]["question_end_turns"] for m in metrics_rows)
    tot_fb = sum(len(m[1]["formulaic"]) for m in metrics_rows)
    tot_fa = sum(len(m[2]["formulaic"]) for m in metrics_rows)
    key.append(f"| **합계** | **{tot_qb}/60** | **{tot_qa}/60** | **{tot_fb}** | **{tot_fa}** | | |\n")

    hits_b = [f"{c}: {', '.join(m['formulaic'])}" for c, m, _ in metrics_rows if m["formulaic"]]
    hits_a = [f"{c}: {', '.join(m['formulaic'])}" for c, _, m in metrics_rows if m["formulaic"]]
    key.append("\n**정형 문구 적중 상세**\n\n- before: " +
               ("; ".join(hits_b) or "없음") + "\n- after: " +
               ("; ".join(hits_a) or "없음") + "\n")

    (DOCS / "EVAL_M1_ANSWER_KEY_2026-08.md").write_text("".join(key), encoding="utf-8")
    print(f"packet + key written. format: total={fmt_total} "
          f"strict_fail={fmt_strict_fail} bad_emotion={bad_emotion} retried={fmt_retry}")
    print(f"question-end turns: before={tot_qb}/60 after={tot_qa}/60 | "
          f"formulaic: before={tot_fb} after={tot_fa}")


if __name__ == "__main__":
    main()
