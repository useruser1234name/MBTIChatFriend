# Sprint 4 QA Report - 최적화/측정

> Sprint 기간: Week 4
> 테스트일: 2026-03-11

---

## 1. 안전 시스템 프롬프트 통합 (Task 4-1)

### 1.1 검증 항목

| 항목 | 기대 동작 | 상태 |
|------|-----------|------|
| safety prompt 포함 | `build_system_prompt` 결과에 안전 가이드라인 포함 | ✅ |
| 위기 번호 포함 | 1393, 1577-0199 상담 번호 프롬프트에 존재 | ✅ |
| AI 고지 포함 | "AI 캐릭터" 명시 문구 포함 | ✅ |
| combined_prompt 결합 | system_prompt + safety_prompt 결합 확인 | ✅ |

### 1.2 코드 위치

- `chat_service.py:519-520` — `get_safety_system_prompt()` 호출 및 결합
- `content_filter.py:get_safety_system_prompt()` — 안전 가이드라인 반환

---

## 2. 호감도 후퇴 메커니즘 (Task 4-2)

### 2.1 중립 메시지 편향 수정

| 항목 | 변경 전 | 변경 후 | 상태 |
|------|---------|---------|------|
| 중립 메시지 delta | `random.choice([0,0,0.5,0.5,1.0])` (평균 +0.4) | `0.0` (순수 중립) | ✅ |

### 2.2 호감도 감쇠 함수

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| 7일 이내 접속 | 감쇠 없음 (동결 기간) | ✅ |
| 14일 미접속 (1주 경과) | -2점 감쇠 | ✅ |
| 28일 미접속 (3주 경과) | -6점 감쇠 | ✅ |
| 레벨 하한 방어 | 현재 레벨-1 최소점수 이하로 내려가지 않음 | ✅ |
| 복귀 보너스 | 하락분의 50% 회복 | ✅ |
| 레벨 1 하한 | 0점 이하로 내려가지 않음 | ✅ |

### 2.3 코드 위치

- `chat_service.py:calculate_affinity_decay()` — 감쇠 계산
- `chat_service.py:calculate_return_bonus()` — 복귀 보너스
- `chat_service.py:AFFINITY_LEVEL_THRESHOLDS` — 레벨별 점수 기준

---

## 3. 비용 메트릭 수집 (Task 4-3)

### 3.1 추적 데이터

| 필드 | 타입 | 설명 |
|------|------|------|
| `model` | string | 사용된 모델 ID (gpt-4o, gpt-4o-mini, 파인튜닝) |
| `prompt_tokens` | int | 입력 토큰 수 |
| `completion_tokens` | int | 출력 토큰 수 |
| `total_tokens` | int | 총 토큰 수 |
| `estimated_cost_usd` | float | 예상 비용 (USD) |
| `llm_calls` | int | LLM 호출 횟수 (재시도 포함) |
| `complexity` | string | 메시지 복잡도 (simple/complex) |
| `finetuned` | bool | 파인튜닝 모델 사용 여부 |

### 3.2 비용 단가 기준

| 모델 | Prompt ($/1K) | Completion ($/1K) |
|------|---------------|-------------------|
| gpt-4o | $0.0025 | $0.0100 |
| gpt-4o-mini | $0.00015 | $0.0006 |

### 3.3 검증 항목

| 항목 | 기대 동작 | 상태 |
|------|-----------|------|
| 정상 응답 시 기록 | `llm_usage` 이벤트 metric_events 테이블에 저장 | ✅ |
| 재시도 시 누적 | 품질 게이트 재생성 시 토큰 합산 | ✅ |
| 비용 계산 정확 | 모델별 단가 × 토큰 수 일치 | ✅ |
| PostgreSQL 미연결 시 | 에러 없이 스킵 | ✅ |

### 3.4 코드 위치

- `chat_service.py:_MODEL_COSTS` — 모델별 비용 단가
- `chat_service.py:_estimate_cost()` — 비용 계산 함수
- `chat_service.py:609-625` — `record_event("llm_usage", ...)` 호출

---

## 4. 변경 파일 목록

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `server/app/chat_service.py` | 수정 | 중립 편향 수정, 호감도 감쇠, 비용 메트릭 추가 |
| `server/app/metrics_service.py` | 기존 | record_event 활용 (변경 없음) |

---

## 5. 기존 테스트 영향

| 테스트 파일 | 결과 | 비고 |
|-------------|------|------|
| `test_content_filter.py` (20개) | ✅ PASS | 영향 없음 |
| `test_models.py` (19개) | ✅ PASS | 영향 없음 |
| `test_chat_service.py` | ⚠️ 수집 오류 | openai/httpx 버전 충돌 (기존 이슈) |

---

## 6. 미완료 / 향후 과제

| 항목 | 사유 | 후속 조치 |
|------|------|-----------|
| 비용 대시보드 | 메트릭 수집만 완료, 시각화 미구현 | 별도 관리 도구 |
| 일간/월간 비용 집계 쿼리 | PostgreSQL 집계 쿼리 필요 | 운영 도구 |
| openai/httpx 호환성 | httpx<0.28 + openai==1.51.0 충돌 | 의존성 업데이트 |
