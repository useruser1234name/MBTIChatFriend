# M1 블라인드 배정표 + 객관 지표 (2026-08)

> ⚠ **채점을 모두 끝낸 뒤에 여세요.** 이 문서를 먼저 보면 12셀 평가가 무효가 됩니다.

## A/B 배정

| 셀 | A | B |
|---|---|---|
| INTJ-T1 | before | after |
| INTJ-T2 | after | before |
| INTJ-T3 | after | before |
| INFP-T1 | after | before |
| INFP-T2 | before | after |
| INFP-T3 | after | before |
| ISFJ-T1 | before | after |
| ISFJ-T2 | before | after |
| ISFJ-T3 | before | after |
| ESFP-T1 | after | before |
| ESFP-T2 | after | before |
| ESFP-T3 | before | after |

배정 난수 시드: `20260811` (`server/tools/eval_m1_packet.py --seed`).

- **before** = `git show ce515aa~1:server/app/prompts.py` (M1 직전)
- **after** = 현재 워킹 트리 `server/app/prompts.py` (M1 반영, ce515aa)

## 집계

셀별로 `after 합계 >= before 합계` 이면 통과. **9/12 이상이면 M1 채택.**

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

## 참고 — 자동 집계한 객관 지표 (채점 점수가 아님)

사람 채점이 게이트입니다. 아래는 채점 결과를 해석할 때 참고만 하세요.
`질문종결`은 마지막 말풍선이 `?`로 끝난 턴 수(5턴 중),
`정형문구`는 EVAL_KIT §4.1 목록에 걸린 횟수(ISFJ 고유 말버릇 제외 안 함 — 육안 확인 필요),
`평균길이`는 턴당 총 글자 수입니다.

| 셀 | before 질문종결 | after 질문종결 | before 정형문구 | after 정형문구 | before 평균길이 | after 평균길이 |
|---|---|---|---|---|---|---|
| INTJ-T1 | 0/5 | 0/5 | 0 | 0 | 52 | 63 |
| INTJ-T2 | 3/5 | 0/5 | 0 | 1 | 62 | 80 |
| INTJ-T3 | 0/5 | 0/5 | 0 | 0 | 47 | 52 |
| INFP-T1 | 1/5 | 0/5 | 0 | 0 | 84 | 78 |
| INFP-T2 | 3/5 | 0/5 | 0 | 0 | 90 | 86 |
| INFP-T3 | 0/5 | 2/5 | 0 | 0 | 93 | 65 |
| ISFJ-T1 | 1/5 | 1/5 | 1 | 0 | 91 | 57 |
| ISFJ-T2 | 3/5 | 2/5 | 0 | 0 | 98 | 87 |
| ISFJ-T3 | 0/5 | 1/5 | 0 | 0 | 78 | 83 |
| ESFP-T1 | 0/5 | 0/5 | 1 | 0 | 83 | 66 |
| ESFP-T2 | 0/5 | 0/5 | 0 | 0 | 81 | 74 |
| ESFP-T3 | 0/5 | 0/5 | 0 | 0 | 68 | 67 |
| **합계** | **11/60** | **6/60** | **2** | **1** | | |

**정형 문구 적중 상세**

- before: ISFJ-T1: T2:무리하면 안 돼; ESFP-T1: T1:내가 들어줄게
- after: INTJ-T2: T4:무리하지 마
