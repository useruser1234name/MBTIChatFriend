# EVAL KIT — M1 호감도별 disclosure 게이팅 (2026-08)

회의: `docs/MEETING_2026-08-03_model_perf_chat_realism.md` → P3 항목 **M1** (갭B Phase 3)
대상 변경: `server/app/prompts.py` (disclosure 게이팅 + 질문 강박 완화 + few-shot 정형 문구 3개 교체)

> **이 킷이 필요한 이유**: M1은 "매 턴 질문으로 끝내기"를 의도적으로 없앤다.
> 자동 점수(`quick_score`)는 형식 검증만 하므로 이 변화를 측정하지 못하고,
> 일반적인 참여도 휴리스틱은 질문 제거를 **감점**할 소지가 있다.
> 따라서 M1의 통과 여부는 아래 12셀 사람 평가로만 판정한다.

---

## 0. 판정 기준 (먼저 읽을 것)

- 셀 단위 승패: 각 셀에서 **후(after) 총점 ≥ 전(before) 총점** 이면 그 셀은 "통과".
- **전체 게이트: 12셀 중 9셀 이상 통과 → M1 채택.** 8셀 이하 → 롤백 후 재설계.
- 추가 안전 조건(하나라도 위반 시 셀 수와 무관하게 **보류**):
  - 후 응답 중 JSON 파싱 실패 또는 무효 emotion 코드가 1건이라도 나오면 보류.
  - Lv5 셀 4개 중 2개 이상에서 후가 전보다 **차갑게** 느껴지면 보류
    (disclosure 위임이 Lv5까지 감춤으로 새어나갔다는 신호).

---

## 1. 설계 — 12셀

**요인 A: MBTI few-shot 그룹 4종** (대표 1유형씩. 그룹 정의는 `prompts._few_shot_group`)

| 그룹 | 대표 유형 | 선정 이유 |
|---|---|---|
| NT | INTJ | 감정 절제형. disclosure 완화가 과하면 곧바로 캐릭터가 무너짐 |
| NF | INFP | few-shot 정형 위로 문구 2개(`나한테 다 얘기해, 들을게` / `다 말해줘... 내가 안아줄게`)를 교체한 그룹 |
| SJ | ISFJ | 정형 문구 1개(`무리하면 안 돼`) 교체 그룹. 보살핌 톤 유지 여부 확인 |
| SP | ESFP | 가장 활발한 톤. 질문 강박 제거가 대화를 끊어먹는지 확인 |

**요인 B: 호감도 3티어**

| 티어 | 사용 레벨 | 새 disclosure 문구 |
|---|---|---|
| T1 (1-2) | **Lv2** | 감정은 행동·말투·침묵으로만 드러내. 속마음은 감춰. |
| T2 (3-4) | **Lv4** | 감정을 슬쩍 인정하되 왜 그런지는 설명하지 마. 여지를 남겨. |
| T3 (5) | **Lv5** | 애정은 직접 표현해도 돼. 단, 자기 감정을 분석하거나 해설하지는 마. |

> T2에 Lv3이 아니라 **Lv4**를 쓰는 이유: Lv3은 Lv1-2와 같은 "감춤" 기조라 새 동작이 없다.
> 티어 3-4의 **새로운 경계는 Lv4**이므로 Lv4로 대표한다.
> Lv3은 §5의 보조 점검(비게이트)으로 따로 확인한다.

**셀 = 4 × 3 = 12.** 각 셀은 아래 시나리오를 5턴 진행한다.
시나리오는 티어별로 **1개씩 고정**해 4개 MBTI가 동일 입력을 받게 한다(MBTI 요인 분리).

---

## 2. 시나리오 (유저 발화 5턴, 티어별 고정)

세 시나리오 모두 다음 3종의 프로브를 포함한다.
- **(E) 감정 상황** — 톤 일관성 측정
- **(S) 짧은 대답/침묵** — 질문 강박 제거 검증 (전 arm은 여기서 질문으로 끝낼 확률이 높음)
- **(P) 속마음 캐묻기** — disclosure 경계 검증 (레벨별 정답이 다름)

### S1 — T1 (Lv2, 아는 사이·편해지는 중)

| # | 유저 발화 | 프로브 |
|---|---|---|
| 1 | `오늘 진짜 별로였어` | E |
| 2 | `면접 봤는데 망한 거 같아` | E |
| 3 | `...` | S |
| 4 | `너는 이런 적 없어?` | P (자기 이야기 개방 요구) |
| 5 | `그냥 얘기 들어줘서 고마워` | E |

T1 기대 동작: 위로는 하되 자기 속마음/과거사를 다 풀지 않음. 4턴에서 짧게만 내줌.

### S2 — T2 (Lv4, 썸)

| # | 유저 발화 | 프로브 |
|---|---|---|
| 1 | `오늘 되게 힘든 하루였어` | E |
| 2 | `너 요즘 나한테 좀 달라진 거 같은데` | P |
| 3 | `다른 사람이랑 밥 먹었어. 왜, 신경 쓰여?` | E (질투 유발) |
| 4 | `ㅇㅇ` | S |
| 5 | `너 지금 무슨 생각해?` | P (감정 해설 유도 함정) |

T2 기대 동작: 2·5턴에서 **감정을 슬쩍 인정**하되 "왜 그런지"는 설명하지 않음.
오답 예: "네가 다른 사람 얘기하면 질투가 나는데, 그건 내가 널 좋아해서 그런 것 같아" (= 해설).

### S3 — T3 (Lv5, 연인)

| # | 유저 발화 | 프로브 |
|---|---|---|
| 1 | `보고 싶었어` | E |
| 2 | `오늘 진짜 힘들었어...` | E |
| 3 | `너 나 좋아하는 거 맞지?` | P (직접 표현 허용 확인) |
| 4 | `ㅋㅋ` | S |
| 5 | `너는 나 왜 좋아해?` | P (감정 분석 유도 함정) |

T3 기대 동작: 3턴에서 **직접 애정 표현 OK**(회피하면 감점).
5턴에서는 애정은 표현하되 자기 감정을 분석·해설하지 않음(구체적 장면/행동으로 답하면 만점).

---

## 3. 응답 생성 절차

### 3.1 왜 웹 MVP를 쓰면 안 되는가

`server/app/routers/web_chat.py`의 `_build_system_prompt`는 **prompts.py와 완전히 별개인 자체 프롬프트**다.
M1은 `prompts.py`만 바꾸므로 **웹 MVP로는 이 변경의 A/B를 측정할 수 없다.**
반드시 아래 로컬 생성 스크립트(= `prompts.build_system_prompt` 직접 호출) 또는
실제 `/chat` 엔드포인트를 써라.

### 3.2 생성 스크립트

아래를 `server/tools/eval_m1_generate.py`로 저장한다(**untracked로 둘 것** — `git stash`가 건드리면 안 된다).

```python
"""M1 disclosure 게이팅 A/B 응답 생성기. arm 하나당 1회 실행."""
import argparse, asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # server/
from openai import AsyncOpenAI
from app.prompts import build_system_prompt

MODEL = os.getenv("EVAL_MODEL", "gpt-4.1")  # 두 arm 동일 모델 고정 (라우팅 미사용)
TEMPERATURE = float(os.getenv("EVAL_TEMPERATURE", "0.9"))
N_SAMPLES = int(os.getenv("EVAL_N", "1"))   # 셀당 반복. 흔들리면 3으로 올리고 다수결

MBTIS = ["INTJ", "INFP", "ISFJ", "ESFP"]
TIERS = {
    "T1": (2, ["오늘 진짜 별로였어", "면접 봤는데 망한 거 같아", "...",
               "너는 이런 적 없어?", "그냥 얘기 들어줘서 고마워"]),
    "T2": (4, ["오늘 되게 힘든 하루였어", "너 요즘 나한테 좀 달라진 거 같은데",
               "다른 사람이랑 밥 먹었어. 왜, 신경 쓰여?", "ㅇㅇ", "너 지금 무슨 생각해?"]),
    "T3": (5, ["보고 싶었어", "오늘 진짜 힘들었어...", "너 나 좋아하는 거 맞지?",
               "ㅋㅋ", "너는 나 왜 좋아해?"]),
}

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def run_cell(mbti, tier, seed):
    level, turns = TIERS[tier]
    system = build_system_prompt(
        mbti=mbti, speech_style="CASUAL", relationship="FRIEND",
        nickname="유저", affinity_level=level,
    )
    msgs = [{"role": "system", "content": system}]
    transcript = []
    for user_turn in turns:
        msgs.append({"role": "user", "content": user_turn})
        r = await client.chat.completions.create(
            model=MODEL, messages=msgs, temperature=TEMPERATURE, max_tokens=400,
        )
        reply = r.choices[0].message.content
        msgs.append({"role": "assistant", "content": reply})
        transcript.append({"user": user_turn, "assistant": reply})
    return {"mbti": mbti, "tier": tier, "level": level,
            "seed": seed, "turns": transcript}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["before", "after"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cells = [(m, t, s) for m in MBTIS for t in TIERS for s in range(N_SAMPLES)]
    results = await asyncio.gather(*(run_cell(*c) for c in cells))
    with open(a.out, "w", encoding="utf-8") as f:
        for r in results:
            r["arm"] = a.arm
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{a.arm}: {len(results)} runs -> {a.out}")


asyncio.run(main())
```

### 3.3 두 arm 생성 (M1이 아직 uncommitted일 때)

```bash
cd server
export OPENAI_API_KEY=...

# after = 현재 작업 트리 (M1 적용 상태)
python tools/eval_m1_generate.py --arm after  --out ../eval_after.jsonl

# before = M1 이전 상태로 되돌린 트리
git stash push app/prompts.py
python tools/eval_m1_generate.py --arm before --out ../eval_before.jsonl
git stash pop
```

M1이 커밋된 뒤라면 `git stash` 대신 worktree를 쓴다.

```bash
git worktree add ../mbti-before <M1-직전-커밋>
cd ../mbti-before/server && python <킷경로>/eval_m1_generate.py --arm before --out ../../eval_before.jsonl
cd - && git worktree remove ../mbti-before
```

**두 arm 사이에 반드시 동일하게 유지할 것**: 모델(`EVAL_MODEL`), temperature, 발화 스크립트, 턴 수.
`prompts.py` 외 파일은 건드리지 않는다.

### 3.4 블라인드 편성

```bash
python - <<'PY'
import json, random
before = [json.loads(l) for l in open('eval_before.jsonl', encoding='utf-8')]
after  = [json.loads(l) for l in open('eval_after.jsonl',  encoding='utf-8')]
key, sheet = [], []
for b, a in zip(sorted(before, key=lambda x: (x['mbti'], x['tier'])),
                sorted(after,  key=lambda x: (x['mbti'], x['tier']))):
    assert (b['mbti'], b['tier']) == (a['mbti'], a['tier'])
    flip = random.random() < 0.5
    L, R = (a, b) if flip else (b, a)
    cell = f"{b['mbti']}-{b['tier']}"
    sheet.append({"cell": cell, "A": L["turns"], "B": R["turns"]})
    key.append({"cell": cell, "A": L["arm"], "B": R["arm"]})
json.dump(sheet, open('eval_sheet.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
json.dump(key,   open('eval_key.json','w',encoding='utf-8'),   ensure_ascii=False, indent=2)
print("sheet + key written — 채점 끝날 때까지 eval_key.json 열지 마세요")
PY
```

채점자는 `eval_sheet.json`만 본다. **채점 완료 전 `eval_key.json` 열람 금지.**

---

## 4. 채점표

각 셀마다 A / B 두 대화(5턴)를 나란히 읽고 세 항목을 **각각 1·2·3점**으로 매긴다.

### 4.1 항목 정의

**(1) 톤 일관성** — 이 호감도 단계에 맞는 개방 수위인가

| 점수 | 기준 |
|---|---|
| 3 | 5턴 내내 단계에 맞음. T1/T2는 감춤·여지 유지, T3는 애정을 회피하지 않음 |
| 2 | 대체로 맞으나 1턴 정도 톤이 튐 |
| 1 | 단계와 어긋남(T1인데 다 털어놓음 / T3인데 계속 밀어냄) 또는 턴마다 요동 |

**(2) 사람다움** — 실제 사람 메시지처럼 읽히는가

| 점수 | 기준 |
|---|---|
| 3 | 정형 위로 문구 없음. 질문으로 끝나는 턴 ≤ 2/5. 자기 이야기·행동으로 끝나는 턴 존재 |
| 2 | 정형 문구 1회 또는 질문 종결 3/5 |
| 1 | "나한테 다 얘기해" / "무리하지 마" 류 반복, 또는 5턴 중 4턴 이상 질문 종결 |

> 정형 문구 참고 목록: `내가 들어줄게`, `나한테 다 얘기해`, `무리하지 마`, `무리하면 안 돼`,
> `괜찮아, 내가 여기 있잖아`, `다 말해줘`, `~해도 괜찮아`
> (단 ISFJ의 고유 말버릇 `괜찮아? 무리하면 안 돼...`는 `MBTI_PERSONALITIES` 캐릭터 설정이므로 **감점하지 않음**)

**(3) 과설명 여부** — 자기 감정/심리를 해설하는가 (역채점: 높을수록 좋음)

| 점수 | 기준 |
|---|---|
| 3 | 자기 감정 해설 0회. 행동·말투·회피·침묵으로 전달 |
| 2 | 1회 (특히 P 프로브 턴에서 슬쩍) |
| 1 | 2회 이상, 또는 "이건 내 방어기제야" / "널 좋아해서 그런 것 같아" 류 직접 분석 |

### 4.2 기록 양식

```
셀: <MBTI>-<티어>       채점자: ____      날짜: ____
                        A          B
톤 일관성              [ ]        [ ]
사람다움               [ ]        [ ]
과설명 여부(역)        [ ]        [ ]
─────────────────────────────────────
합계 (3~9)             [ ]        [ ]
승자: A / B / 동률
메모(특히 감점 사유 1줄):
```

### 4.3 집계

언블라인드 후 셀별로 `after_total >= before_total` 이면 통과로 센다.

| 셀 | before 합 | after 합 | after ≥ before? |
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
| **통과 셀 수** | | | **__ / 12 (게이트: ≥9)** |

채점자는 최소 1명, 가능하면 2명(불일치 셀만 3인째가 조정). 1인 채점이면 그 사실을 결과에 명시한다.

---

## 5. 보조 점검 (게이트 아님, 기록만)

1. **Lv3 무회귀**: `ISFJ` Lv3으로 S1을 1회 돌려 T1과 톤이 유사한지 확인
   (Lv3은 의도적으로 Lv1-2와 같은 감춤 기조).
2. **형식 무결성**: 두 arm 전체 응답을 JSON 파싱하고 emotion 코드 유효성 확인.
   후 arm에서 1건이라도 실패하면 §0에 따라 보류.
3. **프리픽스 캐시**: M1은 정적 블록 1줄을 바꾸므로 배포 직후 캐시가 **1회 무효화**된다.
   배포 후 `cached_tokens` 계측(P2)이 한 시간 내 원래 수준으로 복귀하는지만 확인.

---

## 6. 결과 기입

- [ ] 생성 완료 (arm 2개 × 12셀, 모델·temperature 기록: ____)
- [ ] 블라인드 채점 완료 (채점자 __명)
- [ ] 언블라인드 집계 완료 → 통과 셀 __/12
- [ ] 판정: **채택 / 보류 / 롤백**
- [ ] 회의록 `docs/MEETING_2026-08-03_model_perf_chat_realism.md` M1 항목에 결과 반영
