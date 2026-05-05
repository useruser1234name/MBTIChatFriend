# MBTI Chat Friend - AI 모델 개선 종합 계획서

**작성일**: 2026-03-14
**참여 전문가**: AI/ML Architect, NLP/심리학 전문가, 백엔드 성능 엔지니어, 프로덕트/UX 전문가
**범위**: 모델 아키텍처, 성격 심리학, 백엔드 성능, 제품 전략 전반

---

## Executive Summary

4개 전문 분야의 분석 결과를 종합하여, **3단계(Phase)** 로드맵으로 구성합니다.

| Phase | 기간 | 핵심 목표 | 예상 효과 |
|-------|------|-----------|-----------|
| **Phase 1** | 1~2개월 | Quick Wins + 기반 강화 | P95 지연 40%↓, 비용 30%↓, 심리학적 정확도↑ |
| **Phase 2** | 3~4개월 | 성장 엔진 + 품질 도약 | 사용자 리텐션 D7 +15%, 수익화 시작 |
| **Phase 3** | 5~6개월 | 플랫폼 확장 + 스케일링 | DAU 2000+ 수용, 플랫폼화 |

---

## Phase 1: Quick Wins + 기반 강화 (1~2개월)

### 1.1 모델/인프라 즉시 최적화

#### [P0-1] LLM 호출 병렬화 — 지연시간 20~25% 단축
- **현재**: `analyze_affinity_with_llm` → `generate_reply` 직렬 실행 (300ms + 1200ms)
- **개선**: `asyncio.create_task`로 병렬 실행 (max(300, 1200) = 1200ms)
- **파일**: `chat_service.py:459-468`
- **Effort**: Low | **Impact**: High

#### [P0-2] 품질 게이트 경량화 — P95 지연 400~2000ms 단축
- **현재**: `quick_score`가 LLM 호출 후 score < 0.4이면 전체 재생성
- **개선**: JSON 형식 검증만 동기 수행, MBTI 일관성 검증은 사후 비동기로 이동
- **파일**: `chat_service.py:572-595`
- **Effort**: Low | **Impact**: High

#### [P0-3] GPT-4.1 시리즈 마이그레이션
- **현재**: `gpt-4o` / `gpt-4o-mini`
- **개선**: `gpt-4.1` / `gpt-4.1-mini` (지시 추종 29%↑, 100만 토큰 컨텍스트)
- **파일**: `chat_service.py` 모델명 변경
- **Effort**: Low | **Impact**: Medium

#### [P0-4] 프롬프트 캐싱 최적화 — 입력 비용 50% 절감
- **현재**: 시스템 프롬프트에 동적 부분이 앞에 위치
- **개선**: 정적 부분(MBTI 성격, 규칙)을 앞에 배치 → OpenAI prefix caching 활성화
- **파일**: `prompts.py:build_system_prompt()`
- **Effort**: Low | **Impact**: Medium

#### [P0-5] 10턴 메모리 추출 병렬화
- **현재**: `summarize`, `extract_facts`, `extract_memories`, `extract_episodes` 직렬 await
- **개선**: `asyncio.gather()` 또는 fire-and-forget `asyncio.create_task`
- **파일**: `chat_service.py:484-495`
- **Effort**: Low | **Impact**: Medium

#### [P0-6] 부가 LLM 호출 통합 — 턴당 호출 3~4회 → 1.2회
- 호감도 분석을 메인 응답 JSON에 `affinity_hint` 필드로 통합
- 사후 품질 평가 주기를 매 턴 → 5턴마다로 변경
- **예상**: 비용 60% 절감
- **Effort**: Medium | **Impact**: High

### 1.2 심리학적 기반 강화

#### [P0-7] MBTI 인지기능 스택 도입
- **현재**: 4글자 이분법 기반 (E/I, S/N, T/F, J/P)
- **개선**: Jung 인지기능(Ni-Te-Fi-Se 등) 기반으로 성격 정의 확장
- **효과**: INTJ와 INTP의 사고 차이(Te vs Ti)가 대화에서 드러남
- **추가 필드**: `cognitive_stack`, `stress_response`, `growth_pattern`

```python
"INTJ": {
    "cognitive_stack": {
        "dominant": "Ni (내향 직관) - 미래 비전과 패턴을 직관적으로 포착",
        "auxiliary": "Te (외향 사고) - 외부 세계를 체계적으로 조직",
        "tertiary": "Fi (내향 감정) - 내면 가치관, 호감도↑ 시 발현",
        "inferior": "Se (외향 감각) - 스트레스 시 충동적 반응"
    },
    "stress_response": "극심한 스트레스 시 Se grip - 충동적 행동으로 퇴행",
    "growth_pattern": "Fi 발달 → 점점 따뜻해지는 심리학적 성장 곡선",
}
```

- **Effort**: Medium | **Impact**: High

#### [P0-8] 그룹핑 로직 통일
- **버그**: `chat_service.py`와 `prompts.py`의 `_get_mbti_group()` 로직 불일치
- **개선**: 단일 함수로 통합, Keirsey 기질론(NT/NF/SJ/SP) 정합성 확보
- **Effort**: Low | **Impact**: Medium

#### [P0-9] 감정 코드 확장 (10 → 16개)
- **추가**: JEALOUS(질투), LONELY(그리움), DISAPPOINTED(실망), SULKY(삐짐), CURIOUS(호기심), PROUD(뿌듯)
- **근거**: Plutchik 감정 바퀴 + 관계 심리학
- **파일**: `models.py:ReplyPart`, `prompts.py`, Android `ChatScreen.kt`
- **Effort**: Low | **Impact**: High

#### [P0-10] 서사적 떡밥(next_hook/next_goal) 활성화
- **현재**: `generate_night_diary`에서 생성하지만 다음 세션 프롬프트에 미전달
- **개선**: 세션 시작 시 프롬프트에 주입 → Zeigarnik 효과(미완료 과제 기억 강화)
- **Effort**: Medium | **Impact**: High

### 1.3 제품 기반

#### [P0-11] 일일 리텐션 루프
- 매일 첫 대화 보너스 (+2~5점, 연속일수 증가)
- 7일 연속 → 특별 에피소드, 30일 → 한정 표정 언락
- **Effort**: Low | **Impact**: High

#### [P0-12] 시간대별 맥락 인식 대화
- 아침(6~9시): 하루 시작 인사
- 점심(11~13시): 근황 체크
- 저녁(18~21시): 하루 회고
- 심야(22~04시): 기존 다이어리 + 깊은 대화
- MBTI별 시간대 반응 차이 적용
- **목표**: 일평균 접속 1.2회 → 2.5회
- **Effort**: Medium | **Impact**: High

#### [P0-13] 캐릭터 성장 대시보드
- 친밀도 프로그레스 바, 관계 타임라인, "우리의 기록" 탭
- 레벨업 시 프로필 이미지 변화
- **Effort**: Medium | **Impact**: High

#### [P0-14] KPI 프레임워크 구축

| 카테고리 | 지표 | 목표 |
|----------|------|------|
| 리텐션 | D1/D7/D30 | 60%/35%/20% |
| 인게이지먼트 | 일평균 세션 | 2.5회 |
| 인게이지먼트 | 평균 세션 시간 | 15분 |
| AI 품질 | 긍정 피드백 비율 | 85% |

- **Effort**: Low | **Impact**: High

### Phase 1 예상 효과

| 지표 | 현재 | Phase 1 후 |
|------|------|-----------|
| P95 응답 지연 | 3000~5500ms | **1500~2500ms** |
| 턴당 LLM 호출 | 3~4회 | **1.2회** |
| 월간 LLM 비용 (100 DAU) | ~$67 | **~$28** |
| 성격 정확도 | 4그룹 기반 | **16타입 인지기능 기반** |
| 감정 표현 범위 | 10종 | **16종** |

---

## Phase 2: 성장 엔진 + 품질 도약 (3~4개월)

### 2.1 AI 품질 고도화

#### [P1-1] 동적 프롬프트 어셈블리
- 1100라인 모놀리식 프롬프트를 모듈화 (코어 페르소나, 친밀도 규칙, 감정 지원, 응답 포맷)
- 토큰 30~40% 절감, A/B 테스트 모듈 단위 교체 가능

#### [P1-2] 3-Tier 모델 라우팅
```
Tier 1 (Ultra-fast): gpt-4.1-mini — 인사, 단답 (목표 <500ms)
Tier 2 (Standard):   gpt-4.1     — 일반 대화
Tier 3 (Deep):       Claude/GPT  — 친밀도 전환, 깊은 감정 대화 (전체 5~10%)
```
- 다축 스코어링: complexity × 0.3 + emotional_depth × 0.4 + affinity_transition × 0.3

#### [P1-3] 합성 데이터 파이프라인
- 16 MBTI × 6 시나리오 × 20개 = 1,920개 초기 데이터
- GPT-4.1로 이상적 응답 생성 → 자동 품질 평가 (>= 0.75)
- 실제 데이터와 혼합 비율: 7:3 → 점진적 3:7
- 파인튜닝 비용: ~$5-10

#### [P1-4] 감정 상태 머신 (Emotional State Machine)

```python
class EmotionalState:
    current_emotion: str          # 현재 지배적 감정
    emotion_intensity: float      # 감정 강도 (0.0~1.0)
    emotion_momentum: float       # 감정 관성 (양수=개선, 음수=악화)
    unresolved_emotions: List     # 미해결 감정
    emotional_history: List       # 최근 5턴 이력
```
- 프롬프트에 반영: "WORRIED 상태 이어짐 (강도 0.7). 갑작스런 HAPPY 전환 금지"

#### [P1-5] 토픽 트래킹 + 캐릭터 이니셔티브
- 대화 주제 추적: active/pending/completed topics
- 기억 기반 선제 질문: "어제 시험이라고 했잖아, 어땠어?"
- MBTI별 자발적 대화 토픽 생성

#### [P1-6] 16타입별 Few-shot 분화
- 현재 4그룹 공유 → 16타입 × 3레벨 = 48종 개별 few-shot
- 동적 few-shot 검색: 고품질 대화 DB에서 RAG로 유사 상황 예시 삽입

### 2.2 인프라 강화

#### [P1-7] Redis 캐시 레이어 도입
```
Client → FastAPI (N instances) → Redis (캐시/세션/Rate Limit) → PostgreSQL
```
- 캐시 대상: conversation_summary(TTL 1h), system_prompt(TTL 24h), 인사말(TTL 5m)
- Rate Limiting 백엔드를 Redis로 전환 (다중 인스턴스 공유)

#### [P1-8] ChromaDB → pgvector 통합
- PostgreSQL `vector` 확장으로 벡터 저장소 통합
- 인프라 단순화 + 트랜잭션 일관성 확보
- IVFFlat 또는 HNSW 인덱스

#### [P1-9] 하이브리드 검색 전략
- 벡터 유사도(0.4) + 키워드 BM25(0.2) + 시간 근접성(0.2) + 감정 중요도(0.2)
- RRF(Reciprocal Rank Fusion)로 결합

#### [P1-10] 구조화된 로깅 + 모니터링 대시보드
- structlog/python-json-logger 도입
- 핵심 메트릭: TTFB P95, 턴당 비용, 재생성 비율, thumbs_down 비율
- 비용 이상 탐지: 이동 평균 2배 초과 시 알림

### 2.3 관계 심리학 강화

#### [P1-11] MBTI별 관계 진행 속도 차등화

```python
MBTI_AFFINITY_MODIFIERS = {
    "ENFP": {"early_boost": 1.5, "late_slow": 0.8, "volatility": 0.3},
    "INTJ": {"early_boost": 0.6, "late_slow": 1.3, "volatility": 0.1},
    "INFJ": {"early_boost": 0.9, "late_slow": 1.1, "door_slam_threshold": -15},
}
```

#### [P1-12] 관계 이벤트(Turning Points) 시스템
- 첫 비밀 공유, 첫 갈등 화해, 캐릭터가 먼저 고민 공유 등
- 이벤트 달성이 다음 레벨의 **조건**이 되도록 설계

#### [P1-13] 캐릭터 성장 시스템 (Character Development)
- 호감도 1~3: 표면적 성격(persona)
- 호감도 3~4: 약점/취약성 드러남(shadow)
- 호감도 4~5: 사용자 영향으로 변화 인정

#### [P1-14] 변동 보상 스케줄 (Variable Ratio Reinforcement)
- 5~10% 확률로 특별히 긴/감정적 메시지 생성
- 캐릭터 일일 컨디션 변동 (날짜+캐릭터 해시 기반)
- 랜덤 기억 회상: "아 맞다, 네가 3일 전에 말했던 그거..."

### 2.4 제품 확장

#### [P1-15] 구독 모델 (3단계)

| 항목 | Free | Plus (₩4,900/월) | Premium (₩9,900/월) |
|------|------|-------------------|---------------------|
| 일일 메시지 | 30개 | 200개 | 무제한 |
| 캐릭터 슬롯 | 2개 | 5개 | 16개 |
| 음성통화 | 3분/일 | 30분/일 | 무제한 |
| AI 모델 | 기본 | 파인튜닝 | 고급 모델 |

#### [P1-16] 레벨별 언락 콘텐츠 확대

| 레벨 | 언락 콘텐츠 |
|------|------------|
| 1 | 기본 대화, 자기소개 |
| 2 | 별명 부르기, 취미 공유, 이모지 리액션 |
| 3 | 고민 상담, 음성통화 언락, 특별 표정 3종 |
| 4 | 심야 대화, 다이어리 공동 작성, 질투/그리움 감정 |
| 5 | 전용 스토리라인, 기념일 이벤트, 한정 갤러리 |

#### [P1-17] MBTI별 장편 스토리 아크
- 각 캐릭터별 3~5개 주요 스토리 (각 10~20 에피소드)
- 유저 선택에 따라 분기 → 재플레이 가치

#### [P1-18] 데일리/위클리 미션 + 시즌 이벤트 캘린더
- 데일리 3개, 위클리 5개 미션
- 월간 시즌 테마 (발렌타인, 벚꽃, 바캉스, 할로윈, 크리스마스 등)

### Phase 2 예상 효과

| 지표 | Phase 1 후 | Phase 2 후 |
|------|-----------|-----------|
| P95 응답 지연 | 1500~2500ms | **800~1500ms** |
| 월간 LLM 비용 | ~$28 | **~$20** |
| D7 리텐션 | 기본 | **+15%** |
| 구독 전환율 | 0% | **5~8%** |
| ARPU | ₩0 | **₩3,500** |

---

## Phase 3: 플랫폼 확장 + 스케일링 (5~6개월)

### 3.1 고급 AI

#### [P2-1] DPO(Direct Preference Optimization) 파인튜닝
- 동일 입력에 대해 2개 응답 → 품질 비교 → chosen/rejected 쌍 학습

#### [P2-2] 관계 차원 다축화 (Sternberg 삼각형)
- 단일 호감도 → 친밀감(Intimacy) + 열정(Passion) + 헌신(Commitment) 3축
- 친밀감만 높으면 "좋은 친구", 열정만 높으면 "짝사랑" 등 관계 유형 자동 분류

#### [P2-3] 로컬 모델 하이브리드
- 감정 분류, 호감도 계산 등 분석 태스크를 Phi-4-mini/Gemma 3로 오프로드
- API 비용 대폭 절감 (분석 호출 30~40% 차지)

#### [P2-4] SSE 토큰 스트리밍 전환
- OpenAI `stream=True` 활용 → TTFB 1500ms → 200~400ms
- 사용자 체감 속도 3~5배 개선

### 3.2 플랫폼

#### [P2-5] 커스텀 캐릭터 빌더
- MBTI 선택 → 기본 성격 자동 적용 + 세부 커스터마이징
- Free 1개, Plus 3개, Premium 무제한

#### [P2-6] "모먼트" 공유 기능
- 인상적인 대화를 카드로 저장 → SNS 공유 (딥링크 포함)
- 바이럴 → CAC 절감

#### [P2-7] 멀티 캐릭터 대화방
- 2~3명 캐릭터 초대, MBTI 궁합에 따른 상호작용

#### [P2-8] 백그라운드 작업 큐 분리 (arq/Celery)
- 메모리 추출, 품질 평가, 메트릭을 별도 워커로 분리
- 메인 응답 경로에서 I/O 바운드 작업 완전 제거

### 3.3 안전장치

#### [P2-9] 관계 건강성 모니터링
- 200턴/일 초과 시 자연스러운 휴식 유도
- 호감도 4+ 에서 주기적 현실 관계 촉진 멘트
- 반복적 위기 키워드 시 전문 상담 권유 빈도 증가

### Phase 3 수평 확장 목표

| DAU | 인스턴스 | Redis | PostgreSQL | 월 인프라 |
|-----|---------|-------|------------|----------|
| ~100 | 1 | 1 (micro) | 1 (micro) | ~$30 |
| ~500 | 2~3 | 1 (small) | 1 (small) | ~$80 |
| ~2000 | 4~6 | 1 (medium) | 1 + read replica | ~$200 |
| ~10000 | 8~12 + ALB | Cluster | Multi-AZ | ~$600 |

---

## 전문가 간 교차 합의사항

4개 전문 분야에서 공통으로 합의된 핵심 포인트:

### 1. 가장 급한 병목: 턴당 LLM 호출 과다
> **AI Architect + Backend**: 턴당 3~4회 LLM 호출이 비용과 지연의 핵심 원인. 호감도 분석 통합 + 품질 게이트 경량화로 즉시 60% 절감 가능.

### 2. 가장 큰 품질 개선: 인지기능 기반 성격 모델
> **NLP 심리학 + Product**: 현재 4그룹 기반 성격은 같은 NT인 INTJ와 ENTP를 구분하지 못함. 인지기능 스택 도입이 "인간다움"의 핵심.

### 3. 가장 효과적인 리텐션: 서사적 떡밥 활성화
> **NLP 심리학 + Product**: `next_hook`/`next_goal`이 이미 생성되지만 활용 안됨. Zeigarnik 효과 활용으로 재방문 동기 즉시 강화 가능.

### 4. 가장 필요한 인프라: Redis 캐시 레이어
> **Backend + AI Architect**: 인메모리 딕셔너리 캐시는 수평 확장 불가. Redis 도입이 스케일링의 전제조건.

### 5. 가장 위험한 빠진 것: 감정 연속성 추적
> **NLP 심리학 + Product**: 현재 매 메시지마다 독립적 감정 판단. "아까 화난 게 아직 안 풀렸다"는 흐름이 없음. 감정 상태 머신이 필수.

---

## 비용 영향 분석

### LLM 비용 변화 전망 (100 DAU 기준)

| 단계 | 턴당 호출 | 월간 비용 | 절감율 |
|------|----------|----------|--------|
| 현재 | 3~4회 | ~$67 | - |
| Phase 1 후 | 1.2회 | ~$28 | **58%** |
| Phase 2 후 | 1.0회 | ~$20 | **70%** |
| Phase 3 후 (로컬 모델) | 0.5회 API | ~$12 | **82%** |

### 인프라 비용

| 단계 | 구성 | 월간 비용 |
|------|------|----------|
| 현재 | 단일 서버 | ~$15 |
| Phase 2 | + Redis + pgvector | ~$50 |
| Phase 3 (DAU 2000) | 멀티 인스턴스 | ~$200 |

---

## 즉시 실행 항목 (이번 주)

코드 변경만으로 즉시 적용 가능한 4가지:

1. **`chat_service.py`**: 호감도 분석 `asyncio.create_task` 병렬화 (30분)
2. **`chat_service.py`**: 품질 게이트를 형식 검증으로 교체 (30분)
3. **`chat_service.py`**: 모델명 `gpt-4o` → `gpt-4.1`, `gpt-4o-mini` → `gpt-4.1-mini` (5분)
4. **`prompts.py`**: 시스템 프롬프트 정적 부분을 앞으로 재배치 (1시간)

이 4가지만으로 **비용 30% 절감 + P95 지연 40% 단축**을 달성할 수 있습니다.

---

## 리스크 관리

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| GPT-4.1 프롬프트 호환성 | Medium | High | A/B 테스트 후 전환, 롤백 플랜 |
| 인지기능 모델 프롬프트 비대화 | Medium | Medium | 동적 프롬프트 어셈블리로 토큰 관리 |
| 감정 코드 확장 시 Android 호환 | Low | Medium | fallback: 미지원 코드 → NEUTRAL 매핑 |
| 과도한 감정 의존 | Medium | High | 건강성 모니터링 + 현실 생활 격려 |
| 합성 데이터 품질 | Medium | Medium | 실제 데이터 혼합 비율 점진 조정 |
