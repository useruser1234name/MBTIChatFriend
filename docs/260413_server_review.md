# MBTIChatFriend Server Code Review

**Date**: 2026-04-13
**Scope**: `server/app/` Python 전체 (6,056줄, 19개 파일)
**Reviewer**: AI Expert (LLM + Backend + Security)

---

## 목차

1. [Critical - 즉시 수정](#1-critical---즉시-수정)
2. [High Priority - 단기 수정](#2-high-priority---단기-수정)
3. [Medium Priority - 중장기 개선](#3-medium-priority---중장기-개선)
4. [Low Priority](#4-low-priority)
5. [잘 된 점](#5-잘-된-점)
6. [파일별 요약](#6-파일별-요약)

---

## 1. Critical - 즉시 수정

### 1.1 메모리 추출이 사용자 응답을 블로킹

- **파일**: `chat_service.py:514-529`
- **분류**: 성능 / 사용자 체감

10턴마다 실행되는 `summarize_conversation`, `extract_facts`, `extract_memories`, `extract_episodes` 4개의 LLM 호출이 순차 `await`으로 실행된다. 각 호출이 2-5초씩 걸리면 사용자는 10-20초를 기다리게 된다.

**현재 코드**:
```python
if hist_len >= 4 and hist_len % 10 == 0:
    summary = await summarize_conversation(...)
    facts = await extract_facts(...)
    memories = await extract_memories(...)
    episodes = await extract_episodes(...)
```

**수정 방안**:
```python
if hist_len >= 4 and hist_len % 10 == 0:
    asyncio.create_task(_background_memory_extraction(
        character_name, nickname, conversation_history, character_id
    ))
```

---

### 1.2 호감도 태스크 에러가 전체 응답 실패 유발

- **파일**: `chat_service.py:608-613`
- **분류**: 안정성

`asyncio.create_task()`로 생성된 호감도 분석이 실패하면 `await affinity_task`에서 예외가 전파되어, 이미 생성된 LLM 응답도 전송 실패한다.

**수정 방안**:
```python
if affinity_task is not None:
    try:
        affinity_delta = await affinity_task
    except Exception as e:
        logger.warning(f"호감도 분석 태스크 실패: {e}")
        affinity_delta = 0
```

---

### 1.3 FCM send 엔드포인트에 소유권 검증 없음

- **파일**: `main.py:390-417`
- **분류**: 보안

`/api/v1/fcm/send`에서 `user_id` 파라미터를 임의로 지정해 타인에게 알림 전송이 가능하다. `verify_firebase_token`만 사용하고 있어 인증된 사용자라면 누구든 타인에게 푸시를 보낼 수 있다.

**수정 방안**:
- `require_auth_always`로 인증 강화
- 요청자의 `uid`와 `user_id`가 일치하는지 소유권 검증 추가

---

### 1.4 SQL Injection 위험 - INTERVAL 파라미터

- **파일**: `quality_service.py:322, 333, 349, 364`
- **분류**: 보안

```sql
-- 현재 (위험)
AND created_at >= NOW() - INTERVAL '%s days'

-- 수정 (안전)
AND created_at >= NOW() - INTERVAL '1 day' * %s
```

psycopg는 `INTERVAL` 내부의 `%s` 바인딩을 안전하게 처리하지 못할 수 있다. `INTERVAL '1 day' * %s` 패턴으로 변경해야 한다.

---

## 2. High Priority - 단기 수정

### 2.1 Prefix Caching 비효율

- **파일**: `chat_service.py:571-576`
- **분류**: 비용 최적화

```python
# 현재: Anthropic 전용 파라미터 (OpenAI에서 무의미)
{"role": "system", "content": combined_prompt, "cache_control": {"type": "ephemeral"}}
```

`cache_control`은 Anthropic Claude API 전용이다. OpenAI API에서는 무시된다. 또한 `safety_prompt`와 `mood`를 하나의 문자열로 합쳐서 `mood`가 바뀔 때마다 전체 시스템 프롬프트의 캐시가 무효화된다.

**수정 방안**:
```python
messages = [
    {"role": "system", "content": system_prompt},      # 정적 (캐시됨)
    {"role": "system", "content": safety_prompt},       # 반정적
]
if mood:
    messages.append({"role": "system", "content": f"[사용자 오늘 기분: {mood}]"})
```

**예상 효과**: 캐시 히트율 향상으로 비용 30-50% 절감 가능

---

### 2.2 복잡도 라우팅 허점

- **파일**: `chat_service.py:119-142`
- **분류**: 비용 최적화

| 문제 | 설명 |
|------|------|
| `len(msg) > 50` | 51자 일상 메시지도 gpt-4.1 사용 (비용 5배) |
| `"왜"` in complex_patterns | "왜?" 한 글자도 complex 분류 |
| `history_len > 5` | 5턴 이후 모든 메시지가 complex → mini 활용률 급감 |

**수정 방안**: 점수제 도입
```python
def _classify_message_complexity(message: str, history_len: int) -> str:
    score = 0
    for w in complex_patterns:
        if w in msg_lower:
            score += 1
    if len(msg) > 100:
        score += 1
    elif len(msg) > 50:
        score += 0.5
    if "?" in msg and len(msg) > 30:
        score += 0.5
    return "complex" if score >= 1.5 else "simple"
```

---

### 2.3 `thinking` 필드가 프롬프트에서 미사용

- **파일**: `prompts.py` (build_system_prompt)
- **분류**: 캐릭터 품질

16개 MBTI 전부에 `thinking` 필드(사고방식, 관심 주제, 대화 선호도)가 정의되어 있지만 `build_system_prompt`에서 사용하지 않는다. 캐릭터의 대화 주제 선택이 피상적이 된다.

**예시** (INTP):
> "꼬리에 꼬리를 물고 사고가 확장됩니다"

이런 내용이 프롬프트에 반영되지 않으면 LLM이 피상적 스테레오타입에 의존한다.

**수정**: `build_system_prompt`에서 `personality['thinking']`을 정적 블록에 추가 (+약 60-80 토큰, 캐시 영역이므로 비용 영향 미미)

---

### 2.4 Few-shot 그룹 분류 오류

- **파일**: `prompts.py:770-805`
- **분류**: 캐릭터 품질

주석과 코드가 불일치한다. `_get_mbti_group`은 `mbti[1]+mbti[2]`를 반환하므로:

| 그룹 | 실제 포함 유형 | 문제 |
|------|---------------|------|
| ST | ISTJ, ESTJ, ISTP, ESTP | ISTJ(규칙중시)와 ESTP(즉흥적)가 같은 few-shot |
| SF | ISFJ, ESFJ, ISFP, ESFP | ISFJ(헌신적 수호자)와 ESFP(에너지 폭발)가 같은 few-shot |
| NT | INTJ, ENTJ, INTP, ENTP | 비교적 적절 |
| NF | INFJ, ENFJ, INFP, ENFP | 비교적 적절 |

**수정**: 최소한 SJ/SP를 분리하여 8그룹으로 확장. 이상적으로는 J/P 축 반영.

---

### 2.5 memory_service.py 동기 DB가 이벤트 루프 블로킹

- **파일**: `memory_service.py:83, 107`
- **분류**: 성능

`_load_from_db`, `_save_to_db`가 동기 `fetchone`/`execute`를 직접 호출한다. `async` 함수 내에서 호출되면 이벤트 루프가 차단된다.

**수정**: `asyncio.to_thread`로 감싸거나 `async_fetchone`/`async_execute`로 교체

---

### 2.6 Prompt Injection 방어 부재

- **파일**: `chat_service.py:586`
- **분류**: 보안

사용자 메시지가 `messages.append({"role": "user", "content": message})`로 직접 삽입된다. `content_filter.py`는 성적/폭력 콘텐츠만 필터링하며 prompt injection 패턴은 검사하지 않는다.

**수정 방안**:
```python
# 최소 방어: 사용자 메시지를 명시적 경계로 감싸기
messages.append({"role": "user", "content": f"[사용자 메시지 시작]\n{message}\n[사용자 메시지 끝]"})
```

추가로 `content_filter.py`에 prompt injection 패턴 감지 추가 권장.

---

### 2.7 submit_feedback 동기 DB 블로킹

- **파일**: `main.py:570`
- **분류**: 성능

`async def` 핸들러에서 동기 `pg_execute`를 직접 호출하여 이벤트 루프를 블로킹한다.

**수정**: `await asyncio.to_thread(pg_execute, ...)` 또는 asyncpg 사용

---

## 3. Medium Priority - 중장기 개선

### 3.1 야간 일기에 gpt-4.1 사용

- **파일**: `chat_service.py:822`

`generate_night_diary`는 `gpt-4.1`을 사용하지만, `generate_diary`는 `gpt-4.1-mini`를 사용한다. 야간 일기가 `next_hook`/`next_goal` 필드를 추가로 생성하지만 `gpt-4.1-mini`로도 충분하다.

**예상 비용 절감**: 일기 생성당 약 80%

---

### 3.2 재생성 시 품질 비교 없음

- **파일**: `chat_service.py:620-640`

재생성된 응답의 `quick_score`를 다시 측정하지 않고 무조건 교체한다. 재생성 시 `temperature`를 0.9로 올려 형식 준수율이 오히려 낮아질 수 있다.

**수정 방안**:
```python
retry_score = await quick_score(message, retry_content, mbti)
if retry_score > score:
    replies = retry_replies
    content = retry_content
```

---

### 3.3 콘텐츠 안전 가드레일이 prompts.py에 없음

- **파일**: `prompts.py`

`content_filter.py`에서 입력 필터링만 하고, 프롬프트 레벨에서 캐릭터의 부적절한 콘텐츠 생성을 방지하는 지시가 없다. 호감도 5에서 "적극적 스킨십 표현"이 에스컬레이션될 위험이 있다.

**추가 권장**:
```
# 안전 규칙
- 성적으로 노골적인 표현은 절대 하지 마. 애정 표현은 "뽀뽀", "안아줘" 수준까지만.
- 자해/자살 관련 이야기가 나오면 공감하되 전문 도움(1393)을 부드럽게 안내해.
- 의료/법률 조언은 하지 마. "전문가에게 물어보는 게 좋을 것 같아"로 유도해.
```

---

### 3.4 MBTI별 호감도 행동 차이 미반영

- **파일**: `prompts.py:665-736`

`AFFINITY_BEHAVIORS`가 모든 MBTI에 동일 적용된다. INTJ 레벨 5에서 "적극적 스킨십 표현"은 캐릭터 이탈이다.

**수정**: MBTI 그룹별 오버라이드 추가 또는 "호감도 행동보다 캐릭터 성격이 우선"이라는 명시적 우선순위 지시

---

### 3.5 delete_conversation 트랜잭션 미사용

- **파일**: `main.py:679-726`

5개 테이블을 순차적으로 `pg_execute`로 삭제하는데, 중간 실패 시 부분 삭제 상태가 된다.

**수정**: `async with conn.transaction():` 패턴으로 트랜잭션 묶기

---

### 3.6 memory_service.py 키 충돌 가능성

- **파일**: `memory_service.py:78-80`

```python
def get_memory_key(character_name: str, nickname: str) -> str:
    return f"{character_name}_{nickname}"
```

`character_name="A_B"`, `nickname="C"` 와 `character_name="A"`, `nickname="B_C"`가 동일한 키 `A_B_C`를 생성한다.

**수정**: 구분자를 `::` 또는 `|`로 변경

---

### 3.7 vector_store.py `_neg_cache` 크기 제한 없음

- **파일**: `vector_store.py:65`

존재하지 않는 컬렉션명이 계속 쌓이면 메모리 누수가 된다. `_COL_CACHE_MAX`와 같이 크기 제한 필요.

---

### 3.8 finetune 엔드포인트 인증 강화 필요

- **파일**: `main.py:517, 548`

파인튜닝은 비용이 발생하는 관리 기능인데 `verify_firebase_token` 사용. `require_auth_always` 적용이 맞다.

---

### 3.9 rate limit 미적용 엔드포인트

- **파일**: `main.py`

| 엔드포인트 | 라인 | 위험 |
|-----------|------|------|
| `/api/v1/fcm/register` | 379 | FCM 토큰 등록 어뷰징 |
| `/api/v1/fcm/send` | 390 | 알림 스팸 |
| `/api/v1/finetune/activate` | 548 | 비용 발생 |
| `/api/v1/quality/dashboard` | 591 | DB 부하 |

---

### 3.10 감정 코드 7/10 설명 누락

- **파일**: `prompts.py:1080-1084`

10개 감정 중 PLAYFUL, WORRIED, TOUCHED만 설명이 있고, NEUTRAL, HAPPY, SHY, SAD, ANGRY, SURPRISED, LOVE는 설명 없이 코드명만 나열. SHY와 LOVE의 차이 등 가이드 필요.

---

### 3.11 위기 감지 코드 중복

- **파일**: `main.py:263-274, 306-317`

`send_message`와 `stream_message` 양쪽에 Tier1/Tier2 위기 감지 처리가 거의 동일하게 반복된다.

**수정**: `_handle_crisis_check(req, is_crisis, tier, intervention, result)` 헬퍼로 추출

---

### 3.12 memory 조회 순차 I/O

- **파일**: `main.py:840-841`

```python
# 현재 (순차)
summary = await asyncio.to_thread(get_existing_summary, ...)
facts = await asyncio.to_thread(get_existing_facts, ...)

# 개선 (병렬)
summary, facts = await asyncio.gather(
    asyncio.to_thread(get_existing_summary, ...),
    asyncio.to_thread(get_existing_facts, ...),
)
```

---

## 4. Low Priority

| # | 이슈 | 파일 |
|---|------|------|
| 4.1 | 비용 추적에서 캐시 토큰 미분리 | `chat_service.py:652-668` |
| 4.2 | `main.py` 871줄 → APIRouter 도메인 분리 필요 | `main.py` 전체 |
| 4.3 | `quality_service.py` N+1 쿼리 패턴 (3개 쿼리 → 1개 통합 가능) | `quality_service.py:238-280` |
| 4.4 | 출력 객체 수(1~5개) 상황별 가이드 부재 | `prompts.py:1057` |
| 4.5 | 세대 부적합 표현 ("오마이갓") | `prompts.py:622` |
| 4.6 | `asyncio.to_thread(lambda: ...)` 패턴 과도 사용 | `main.py:208,225` |
| 4.7 | MBTI 유효성 검증 중복 (models.py + main.py) | `main.py:813-822` |
| 4.8 | 지연 임포트 남용 | `main.py:270,309,846` |
| 4.9 | 중복 memory_context 조회 | `chat_service.py:483-485,530` |
| 4.10 | `quick_score`가 async이지만 I/O 없음 | `quality_service.py` |

---

## 5. 잘 된 점

### 아키텍처
- **Prefix caching 구조**: 정적 블록을 프롬프트 최상단에 배치하여 캐시 효율 확보
- **Layered 구조**: endpoint → service → DB/LLM 분리가 명확
- **fire-and-forget 품질 평가**: `score_response_async`가 메인 응답 지연을 방지

### LLM/AI
- **호감도 시스템**: 5단계 체계적 정의 (tone, emoji_freq, message_length, behaviors)
- **quick_score**: ~1ms 형식 검증으로 저품질 응답을 빠르게 필터링
- **복잡도 기반 모델 라우팅**: gpt-4.1/gpt-4.1-mini 분기로 비용 최적화 시도

### 캐릭터
- **MBTI 개성**: 말투, 습관, 감정 표현이 16유형별로 잘 차별화됨
- **감정 코드 가이드**: "NEUTRAL만 반복하지 마"라는 직접적 지시가 효과적
- **출력 형식 제어**: JSON 배열 강제가 프롬프트 최상단에 배치되어 준수율 높음

### 안전
- **콘텐츠 필터**: Tier1/Tier2 위기 감지 + 허용 목록 분리
- **위기 감지**: 자해/자살(Tier1 즉시 개입) + 무의미/포기(Tier2 부드러운 안내)
- **rate limiting**: SlowAPI 30 req/min 적용

---

## 6. 파일별 요약

| 파일 | 줄 수 | 심각도 | 핵심 이슈 |
|------|-------|--------|-----------|
| `chat_service.py` | 1,162 | Critical | 메모리 추출 블로킹, 호감도 에러 전파, 캐싱 비효율, 라우팅 허점 |
| `main.py` | 871 | Critical | FCM 소유권 미검증, 동기 DB 블로킹, 트랜잭션 미사용 |
| `prompts.py` | 1,117 | High | thinking 미사용, few-shot 그룹 오류, 안전 가드레일 부재 |
| `quality_service.py` | 435 | Critical | SQL Injection (INTERVAL), N+1 쿼리 |
| `memory_service.py` | 334 | High | 동기 DB 블로킹, 키 충돌, 레이스 컨디션 위험 |
| `postgres.py` | 292 | Medium | args 전달 불일치, 폴백 경로 |
| `vector_store.py` | 297 | Medium | neg_cache 누수, ID sanitize 미흡 |
| `content_filter.py` | 143 | Medium | prompt injection 미감지, 차단 로그 context 없음 |
| `models.py` | 266 | Low | MBTI 검증 중복 |
| `image_service.py` | 227 | Low | - |
| `finetune_service.py` | 248 | Medium | 인증 강화 필요 |
| `firebase_service.py` | 114 | Low | - |
| `story_state_store.py` | 239 | Low | - |
| `diary_store.py` | 70 | Low | - |
| `metrics_service.py` | 38 | Low | - |
| `config.py` | 37 | Low | - |
| `compatibility.py` | 90 | Low | - |

---

## 수정 우선순위 로드맵

### Phase 1 - 즉시 (1-2일)
- [ ] 1.1 메모리 추출 백그라운드 처리
- [ ] 1.2 호감도 태스크 try/except 감싸기
- [ ] 1.3 FCM send 소유권 검증
- [ ] 1.4 INTERVAL SQL 수정

### Phase 2 - 단기 (3-5일)
- [ ] 2.1 시스템 메시지 정적/동적 분리 (prefix caching)
- [ ] 2.2 복잡도 라우팅 점수제 도입
- [ ] 2.3 thinking 필드 프롬프트 활성화
- [ ] 2.5 memory_service async 전환
- [ ] 2.6 prompt injection 방어
- [ ] 2.7 submit_feedback async 전환

### Phase 3 - 중기 (1-2주)
- [ ] 2.4 Few-shot 8그룹 세분화
- [ ] 3.3 프롬프트 안전 가드레일
- [ ] 3.4 MBTI별 호감도 행동 오버라이드
- [ ] 3.5 delete_conversation 트랜잭션
- [ ] 3.8-3.9 인증 강화 + rate limit

### Phase 4 - 장기 (2-4주)
- [ ] 4.2 APIRouter 도메인 분리
- [ ] 4.3 쿼리 최적화
- [ ] 기타 Low priority 항목
