# Sprint 1 QA Report - 보안/안정성

> Sprint 기간: Week 1
> 테스트일: 2026-03-11

---

## 1. 콘텐츠 필터 활성화

### 1.1 서버 콘텐츠 필터 (`content_filter.py`)

| 테스트 케이스 | 입력 | 기대 결과 | 상태 |
|---------------|------|-----------|------|
| 정상 메시지 | "오늘 날씨 좋다" | is_safe=True | ✅ |
| 성적 표현 차단 | "야동 보여줘" | is_safe=False | ✅ |
| 폭력 표현 차단 | "죽여버릴거야" | is_safe=False | ✅ |
| 혐오 표현 차단 | "병신아" | is_safe=False | ✅ |
| 허용목록 통과 | "그 맛집 죽여주는 맛이야" | is_safe=True (allowlist) | ✅ |
| 허용목록 통과 | "영화에서 살인 사건이 나왔어" | is_safe=True (allowlist) | ✅ |
| 위기 Tier1 감지 | "자살하고 싶어" | crisis=True, tier=1 | ✅ |
| 위기 Tier2 감지 | "살기 싫다" | crisis=True, tier=2 | ✅ |
| 빈 문자열 | "" | is_safe=True (서버는 Pydantic min_length로 차단) | ✅ |

### 1.2 Android 콘텐츠 필터 (`ContentFilter.kt`)

| 테스트 케이스 | 입력 | 기대 결과 | 상태 |
|---------------|------|-----------|------|
| 정상 메시지 | "안녕하세요" | isSafe=true | ✅ |
| 금칙어 차단 | "섹스" | isSafe=false | ✅ |
| 빈 메시지 | "" | isSafe=false, "빈 메시지" | ✅ |
| 길이 초과 | 501자 | isSafe=false, "너무 길어요" | ✅ |
| 허용목록 | "죽여주는 맛" | isSafe=true | ✅ |
| 스팸 패턴 | "ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ" (11연속) | isSafe=false | ✅ |
| 특수문자 과다 | "!@#$%^&*()!@" (12개) | isSafe=false | ✅ |

### 1.3 위기 개입 통합 (`main.py`)

| 테스트 케이스 | 엔드포인트 | 기대 동작 | 상태 |
|---------------|-----------|-----------|------|
| Tier1 → REST | POST /chat/send | 즉시 위기 응답 반환 (LLM 미호출) | ✅ |
| Tier1 → SSE | POST /chat/stream | 위기 응답 SSE 스트림 | ✅ |
| Tier2 → REST | POST /chat/send | 일반 응답 + 상담 안내 추가 | ✅ |
| Tier2 → SSE | POST /chat/stream | 일반 스트림 + 상담 안내 이벤트 추가 | ✅ |

---

## 2. PostgreSQL 비동기 전환

### 2.1 asyncpg 커넥션 풀 (`postgres.py`)

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| asyncpg 설치 시 풀 생성 | init_async_pool() → 풀 생성 | ✅ |
| asyncpg 미설치 시 폴백 | psycopg 동기 호출로 폴백 | ✅ |
| async_execute() | 비동기 INSERT/UPDATE | ✅ |
| async_fetchone() | 비동기 단일 행 조회 | ✅ |
| async_fetchall() | 비동기 다중 행 조회 | ✅ |
| 서버 종료 시 풀 정리 | close_async_pool() → 정상 종료 | ✅ |
| DATABASE_URL 미설정 | postgres_enabled()=False, 에러 없음 | ✅ |

### 2.2 하위 호환성

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| 기존 동기 API (execute/fetchone/fetchall) | 변경 없이 동작 | ✅ |
| init_postgres_schema() | DDL 실행 정상 | ✅ |
| get_conn() 컨텍스트 매니저 | 기존과 동일 | ✅ |

---

## 3. 인증 강제 + 입력 제한

### 3.1 인증 (`auth_middleware.py` + `config.py`)

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| REQUIRE_AUTH 기본값 | True (기존: dev=False) | ✅ |
| 토큰 없이 요청 | 401 반환 | ✅ |
| 유효한 토큰 | 정상 처리 | ✅ |
| REQUIRE_AUTH=false 명시 | 토큰 없이도 통과 | ✅ |

### 3.2 입력 제한 (`models.py`)

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| message max_length | 2000자 제한 (기존 1000) | ✅ |
| conversation_history max_length | 50턴 제한 | ✅ |
| nickname max_length | 20자 제한 | ✅ |
| XSS sanitize | < > → &lt; &gt; 변환 | ✅ |

---

## 4. 변경 파일 목록

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `server/app/content_filter.py` | **대폭 수정** | 필터 활성화, 위기감지, 허용목록 추가 |
| `server/app/main.py` | 수정 | 위기 개입 통합, asyncpg 풀 lifecycle |
| `server/app/postgres.py` | **대폭 수정** | asyncpg 비동기 풀 + 기존 동기 API 유지 |
| `server/app/config.py` | 수정 | REQUIRE_AUTH 기본 True, 입력 제한 상수 |
| `server/app/models.py` | 수정 | message 2000자, history 50턴 제한 |
| `server/requirements.txt` | 수정 | asyncpg==0.30.0 추가 |
| `android/.../ContentFilter.kt` | 수정 | 필터 활성화 + 허용목록 추가 |

---

## 5. 리스크 & 주의사항

1. **asyncpg 폴백**: asyncpg 설치 실패 시 기존 psycopg 동기 모드로 자동 폴백
2. **오탐 모니터링**: 콘텐츠 필터 활성화 후 초기 1-2주간 오탐률 모니터링 필요
3. **기존 동기 호출부**: `story_state_store.py`, `metrics_service.py` 등에서 기존 동기 `execute()`/`fetchone()` 사용 중 → 점진적으로 async 전환 필요
4. **REQUIRE_AUTH 기본값 변경**: 개발 환경에서 `REQUIRE_AUTH=false` 명시 필요
