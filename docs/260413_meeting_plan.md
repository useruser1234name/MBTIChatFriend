# PM 주도 에이전트 작업 분배 회의 계획서

**회의 일시**: 2026-04-13  
**작성자**: PM (Senior Product Manager)  
**기준 문서**: 코드 리뷰(31건) / 보안 감사(37건) / 디자인 리뷰(39건) / 서버 AI 리뷰(33건) — 총 140건 원시 이슈  
**중복 제거 후 실질 작업 단위**: 약 89건

---

## 1. 회의 개요

### 목적

2026-04-13에 4개 영역(코드 품질, 보안, UX/디자인, 서버 AI)에서 수행된 리뷰 결과를 통합하여, 5개 에이전트에게 명확한 작업 범위와 우선순위를 부여한다. 이 문서는 단순 이슈 목록이 아니라 "누가, 언제, 무엇을, 어떤 기준으로 완료하는가"를 정의한 실행 계획서다.

### 참석 에이전트 및 전문 영역

| 에이전트 | 전문 영역 | 이번 작업 핵심 |
|---------|---------|--------------|
| **backend-dev** | FastAPI/Python, PostgreSQL, API 인증, 인프라 | Critical 보안 패치 + 비동기 전환 + DB 안정성 |
| **frontend-dev** | Android/Kotlin/Jetpack Compose, Room DB, Navigation | 보안 크래시 수정 + UI 버그 + DB 마이그레이션 |
| **llm-expert** | 프롬프트 엔지니어링, 모델 라우팅, 캐릭터 품질 | 캐시 비효율 해소 + 캐릭터 깊이 강화 |
| **ux-designer** | UI/UX 설계, 감정 설계, 접근성 | Critical UX 버그 + 유대감 강화 개선안 |
| **data-analyst** | 리텐션 분석, A/B 테스트, 이벤트 설계 | 개선 효과 측정 설계 + 이벤트 데이터 품질 |

---

## 2. 리뷰 결과 종합 대시보드

### 2.1 원시 이슈 집계

| 리뷰 문서 | Critical | High | Medium | Low/Enhancement | 합계 |
|---------|---------|------|--------|----------------|------|
| 코드 리뷰 | 5 | 9 | 11 | 6 | 31 |
| 보안 감사 | 4 | 11 | 13 | 9 | 37 |
| 디자인 리뷰 | 6 | (18 Important + 4 High) | (10 Enhancement) | (5 Accessibility) | 39 |
| 서버 AI 리뷰 | 4 | 7 | 12 | 10 | 33 |
| **원시 합계** | **19** | **49** | **46** | **30** | **140** |

### 2.2 도메인별 교차 분석 — 동일 이슈 중복 지적 현황

아래 표는 2개 이상의 리뷰에서 같은 이슈를 지적한 경우다. 교차 지적 수가 많을수록 실제 위험도/중요도가 높다.

| 이슈 | 코드리뷰 | 보안감사 | 서버리뷰 | 디자인리뷰 | 교차수 | 실제 심각도 |
|------|--------|--------|--------|---------|------|----------|
| FCM 엔드포인트 소유권 미검증 | C-1/C-2 | CRIT-S2/S3 | SR-1.3 | - | 3 | **Critical** |
| delete_conversation 인증/IDOR | C-1 | HIGH-S1 | - | - | 2 | **Critical** |
| get_memories LIKE 인젝션 + 소유권 | C-3 | HIGH-S2/S3 | SR-1.4 | - | 3 | **Critical** |
| quality_service INTERVAL SQL 인젝션 | - | MED-S6 | SR-1.4 | - | 2 | **Critical** |
| 호감도 분석 태스크 에러 전파 | H-4 | - | SR-1.2 | - | 2 | **High** |
| session_start 동기 블로킹 | H-5 | - | SR-2.7 | - | 2 | **High** |
| finetune 엔드포인트 보호 미흡 | - | HIGH-S5 | SR-3.8 | - | 2 | **High** |
| rate limit 미적용 엔드포인트 | - | MED-S1 | SR-3.9 | - | 2 | **High** |
| vector_store neg_cache 크기 무제한 | L-3 | - | SR-3.7 | - | 2 | Medium |
| 프롬프트 지시 충돌 (AI 정체성) | M-3 | - | SR-3.3 | - | 2 | Medium |
| MbtiGroup enum Room 호환성 | M-8 | - | - | E-4(간접) | 2 | **High** |
| 홈 화면 Settings 진입점 중복 | - | - | - | I-10 / C-4(간접) | 2 | Medium |
| room_id 포맷 파괴적 변경 | M-1 | - | - | - | 1 | **High** (데이터 손실) |
| FCM 토큰 로그 평문 노출 | - | CRIT-A1 | - | - | 1 | **Critical** (Android) |
| Room DB 암호화 미적용 | - | HIGH-A2 | - | - | 1 | High (중기) |
| 메모리 추출 응답 블로킹 | - | - | SR-1.1 | - | 1 | **Critical** (성능) |

### 2.3 중복 제거 후 실질 작업 단위 분류

| 심각도 | 건수 | 비고 |
|--------|------|------|
| Critical (즉시, 1-2일) | 11 | 보안 8 + 성능 크래시 3 |
| High (이번 스프린트, 3-7일) | 24 | 코드 품질 + UX 버그 + LLM |
| Medium (다음 스프린트, 1-2주) | 32 | 기능 정확성 + 감성 설계 |
| Low/Enhancement (백로그) | 22 | 코드 품질 + 폴리시 |
| **합계** | **89** | |

---

## 3. 에이전트별 역할 부여

---

### 3.1 backend-dev

**담당 범위**: FastAPI 서버 보안 패치, PostgreSQL 안정성, 비동기 전환, 인프라 설정

#### Phase 1 — Critical (1-2일)

| 이슈 ID | 내용 | 예상 공수 | 참조 |
|--------|------|---------|------|
| BD-C1 | FCM send/register 엔드포인트 소유권 검증 (`require_auth_always` + uid 비교) | 1h | CRIT-S2, CRIT-S3, SR-1.3 |
| BD-C2 | delete_conversation 인증 누락 수정 + IDOR 방어 | 1h | C-1, HIGH-S1 |
| BD-C3 | get_memories LIKE 와일드카드 이스케이프 + 소유권 검증 | 1.5h | C-3, HIGH-S2/S3, HIGH-S4 |
| BD-C4 | quality_service INTERVAL SQL 안전 패턴으로 교체 | 1h | SR-1.4 |
| BD-C5 | session_start `require_auth_always` + character_id 소유권 검증 | 0.5h | C-2 |
| BD-C6 | OpenAI API 키 폐기 및 재발급, Secret Manager 이전 계획 수립 | 즉시 | CRIT-S1 |
| BD-C7 | Production `/docs`, `/redoc`, `/openapi.json` 비활성화 | 0.5h | HIGH-S6 |

#### Phase 2 — High (3-5일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| BD-H1 | session_start `record_event` → `asyncio.to_thread` 전환 | 0.5h |
| BD-H2 | submit_feedback 동기 DB → async 전환 | 0.5h |
| BD-H3 | memory_service `_load_from_db`/`_save_to_db` async 전환 | 1.5h |
| BD-H4 | memory 조회 순차 I/O → `asyncio.gather` 병렬화 | 1h |
| BD-H5 | finetune 엔드포인트 `require_auth_always` + 관리자 UID 화이트리스트 + rate limit | 1h |
| BD-H6 | rate limit 미적용 엔드포인트 4개 SlowAPI 추가 | 1h |
| BD-H7 | PostgreSQL 스키마 초기화 asyncpg 지원 추가 또는 명시 에러 처리 (H-2) | 2h |
| BD-H8 | async_execute 폴백 시 플레이스홀더 변환 로직 (H-3) | 1.5h |
| BD-H9 | return_bonus 캡핑 로직 추가 `min(adjusted_score + bonus, current)` | 0.5h |
| BD-H10 | room_id 포맷 변경 PostgreSQL 마이그레이션 스크립트 작성 (M-1) | 3h |

#### Phase 3 — Medium (1-2주)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| BD-M1 | Rate limit IP 기반 → uid 기반 전환 | 2h |
| BD-M2 | HistoryMessage.content `max_length=2000` 제한 추가 | 0.5h |
| BD-M3 | ImageSetRequest.size Literal 제한 추가 | 0.5h |
| BD-M4 | CORS `credentials=True` + `origins=["*"]` 조합 분리 | 1h |
| BD-M5 | `quality/dashboard` days 파라미터 범위 검증 | 0.5h |
| BD-M6 | delete_conversation 트랜잭션 묶기 | 1h |
| BD-M7 | memory_service 키 충돌 구분자 `::` 변경 | 0.5h |
| BD-M8 | uvicorn reload=True production 잔류 제거 | 0.5h |
| BD-M9 | 위기 감지 헬퍼 함수 추출 (코드 중복 제거) | 1h |
| BD-M10 | Firebase Storage 미설정 시 명시 에러 반환 (M-6) | 0.5h |

#### Phase 4 — 백로그

| 이슈 ID | 내용 |
|--------|------|
| BD-L1 | APIRouter 도메인 분리 (main.py 871줄) |
| BD-L2 | quality_service N+1 쿼리 통합 |
| BD-L3 | `asyncio.to_thread(lambda: ...)` 패턴 정리 |
| BD-L4 | MBTI 유효성 검증 중복 제거 |
| BD-L5 | firebase-admin 6.5.0 → 7.x 업데이트 |
| BD-L6 | llm_usage 이벤트 room_id 기록 수정 |

**다른 에이전트와의 의존성**

- BD-H10 (room_id 마이그레이션) → frontend-dev FE-H1과 반드시 동시 조율 필요
- BD-H7/H8 (PostgreSQL 폴백) → llm-expert LLM-C1 (메모리 추출 백그라운드)과 순서 조율
- BD-M1 (rate limit uid 기반) → frontend-dev의 AuthInterceptor 수정과 연동

**Definition of Done**

- [ ] 모든 Critical 엔드포인트에서 `require_auth_always` 사용, Optional auth 제거
- [ ] 소유권 검증 로직에 단위 테스트 추가 (pytest)
- [ ] LIKE 와일드카드 이스케이프 테스트 케이스 통과
- [ ] room_id 마이그레이션 스크립트 dry-run 성공
- [ ] `cd server && python -m pytest tests/ -v` 전체 통과

---

### 3.2 frontend-dev

**담당 범위**: Android 보안 패치, Room DB 마이그레이션, UI 버그 수정, Compose 안정성

#### Phase 1 — Critical (1-2일)

| 이슈 ID | 내용 | 예상 공수 | 참조 |
|--------|------|---------|------|
| FE-C1 | FCM 토큰 로그 마스킹 (`if (BuildConfig.DEBUG)` + 뒤 6자리만) | 0.5h | CRIT-A1 |
| FE-C2 | AuthInterceptor `runBlocking(Dispatchers.IO)` → `runBlocking {}` + 토큰 캐시 Mutex 적용 | 1h | C-4, MED-A3 |
| FE-C3 | OfflineMessageQueue `tryLock()` → `withLock {}` 교체 (뮤텍스 영구 잠금 방지) | 1h | C-5 |
| FE-C4 | 로그아웃 시 Room DB 전체 삭제 (`deleteAll()` 추가) | 1h | HIGH-A5 |
| FE-C5 | 백업 규칙 설정 — Room DB/DataStore `/backup_rules.xml` 제외 | 0.5h | HIGH-A3 |

#### Phase 2 — High (3-5일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| FE-H1 | room_id 포맷 변경 대응 — Android Room 데이터 마이그레이션 v8 작성 | 3h |
| FE-H2 | MbtiGroup enum `SJ/SP → ST/SF` Room Migration 추가 또는 TypeConverter 레거시 처리 | 2h |
| FE-H3 | `CharacterProfileScreen` `compatibility!!` → `val compat = compatibility ?: return` 대체 | 1h |
| FE-H4 | `TypewriterText` 키 `remember(fullText, messageId)` 수정 | 0.5h |
| FE-H5 | `selectMood` 첫 번째 캐릭터에만 전달 버그 수정 — 활성 캐릭터 로직 명확화 | 1h |
| FE-H6 | MBTI 그리드 3열 → 4열 복원 | 0.5h |
| FE-H7 | `expressionSet` taskId 타임아웃/not_found 응답 시 DataStore 정리 | 1h |
| FE-H8 | `userMessageCount` Room/DataStore 영속화 또는 초기값 0 트리거 제외 | 1h |
| FE-H9 | BASE_URL `local.properties`에서 읽도록 외부화 | 1h |
| FE-H10 | `LaunchedEffect(character, userMbti)` → `LaunchedEffect(character?.id, userMbti)` | 0.5h |
| FE-H11 | HIGH-A1: debug 전용 network security config 분리 | 1h |

#### Phase 3 — Medium (1-2주)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| FE-M1 | DataStore FCM 토큰/UID `EncryptedSharedPreferences` 또는 Keystore 이전 | 2h |
| FE-M2 | Room DB SQLCipher 암호화 적용 | 4h |
| FE-M3 | `@Deprecated` API 키 코드 완전 삭제 (UserPreferences) | 0.5h |
| FE-M4 | 인증서 피닝 `CertificatePinner` OkHttpClient 적용 | 2h |
| FE-M5 | 입력 길이 클라이언트(1000자) ↔ 서버(2000자) 불일치 통일 | 0.5h |
| FE-M6 | FCM 메시지 데이터 길이/내용 검증 추가 | 0.5h |
| FE-M7 | 딥링크 `characterId.toInt()` → `toLongOrNull()` 안전 처리 | 0.5h |
| FE-M8 | ProGuard keep 규칙 최소화 (data/remote 전체 보존 → 필요 클래스만) | 1h |
| FE-M9 | `MbtiGroup.values()` → `MbtiGroup.entries` 교체 | 0.5h |
| FE-M10 | `requirements.txt` openai 버전 상한 핀닝 `>=1.54.0,<2.0.0` | 0.5h |

#### Phase 4 — 백로그

| 이슈 ID | 내용 |
|--------|------|
| FE-L1 | LOW-A2: Firestore 연령/성별 저장 PIPA 검토 |
| FE-L2 | LOW-A3: Remote Config 무결성 보장 |
| FE-L3 | LOW-A5: NotificationHelper requestCode Int 범위 제한 |
| FE-L4 | `LevelUpOverlay` exit 애니메이션 무효 수정 (L-6) |
| FE-L5 | SettingsScreen AlertDialog → Snackbar 교체 (L-5) |

**다른 에이전트와의 의존성**

- FE-H1 (room_id 마이그레이션) → backend-dev BD-H10과 동시 착수, 서버/Android 마이그레이션 순서 합의 필요
- FE-H2 (MbtiGroup enum) → ux-designer UX-H6 (MBTI 선택 화면 개선)과 연동 확인
- FE-H9 (BASE_URL 외부화) → backend-dev 서버 배포 URL 확정 후 진행

**Definition of Done**

- [ ] logcat에서 FCM 토큰 전체가 출력되지 않음 (릴리즈 빌드)
- [ ] OfflineMessageQueue 뮤텍스 데드락 재현 불가
- [ ] Room Migration v8 적용 후 기존 데이터 정상 조회
- [ ] MbtiGroup 변경 후 기존 Room DB 역직렬화 크래시 없음
- [ ] 로그아웃 후 Room DB 쿼리 결과 0건

---

### 3.3 llm-expert

**담당 범위**: 프롬프트 엔지니어링, 모델 라우팅, Prefix Caching, 캐릭터 품질, 파인튜닝

#### Phase 1 — Critical (1-2일)

| 이슈 ID | 내용 | 예상 공수 | 참조 |
|--------|------|---------|------|
| LLM-C1 | 메모리 추출 블로킹 → `asyncio.create_task()` 백그라운드 처리 | 1.5h | SR-1.1 |
| LLM-C2 | 호감도 태스크 `await affinity_task` try/except 감싸기 + 키워드 폴백 복원 | 1h | SR-1.2, H-4 |

#### Phase 2 — High (3-5일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| LLM-H1 | Prefix Caching: 시스템 메시지 정적/동적 분리 (mood를 별도 메시지로) | 2h |
| LLM-H2 | 복잡도 라우팅 점수제 도입 (현재 단순 조건 → 가중 점수) | 2h |
| LLM-H3 | `thinking` 필드 `build_system_prompt`에 활성화 (+60-80 토큰, 캐시 영역) | 1h |
| LLM-H4 | Prompt Injection 방어 — 사용자 메시지 명시적 경계 래핑 + content_filter 패턴 추가 | 1.5h |
| LLM-H5 | `mood_checkin` 프롬프트 인젝션 방어 — `MoodCheckinRequest` max_length + 허용 문자 validator | 1h |
| LLM-H6 | 프롬프트 지시 충돌 해소 — AI 정체성 노출 규칙 단일화 (M-3) | 0.5h |
| LLM-H7 | Few-shot 그룹 4 → 8그룹 세분화 (SJ/SP/NJ/NP 분리) | 3h |

#### Phase 3 — Medium (1-2주)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| LLM-M1 | 프롬프트 안전 가드레일 추가 — 성적/의료/법률 경계선 명시 | 1.5h |
| LLM-M2 | MBTI별 호감도 행동 오버라이드 — INTJ/INTJ 등 내향형 고레벨 행동 재정의 | 2h |
| LLM-M3 | 야간 일기 `gpt-4.1` → `gpt-4.1-mini` 전환 (비용 80% 절감) | 0.5h |
| LLM-M4 | 재생성 시 `quick_score` 비교 후 교체 여부 결정 | 1h |
| LLM-M5 | 감정 코드 7개 설명 추가 (NEUTRAL/HAPPY/SHY/SAD/ANGRY/SURPRISED/LOVE) | 1h |
| LLM-M6 | 위기 허용 목록이 Tier1 우회하지 못하도록 허용목록 우선순위 재설계 (L-1) | 1.5h |
| LLM-M7 | 출력 객체 수(1~5개) 상황별 가이드 프롬프트 추가 | 0.5h |
| LLM-M8 | 세대 부적합 표현 ("오마이갓" 등) 검토 및 수정 | 0.5h |

#### Phase 4 — 백로그

| 이슈 ID | 내용 |
|--------|------|
| LLM-L1 | 비용 추적에서 캐시 토큰 분리 집계 |
| LLM-L2 | `quick_score`를 sync 함수로 전환 (I/O 없음) |
| LLM-L3 | 중복 memory_context 조회 제거 |
| LLM-L4 | 지연 임포트 남용 정리 |

**다른 에이전트와의 의존성**

- LLM-C1 (메모리 추출 비동기) → backend-dev BD-H7 (PostgreSQL async 스키마)과 순서 조율 필요
- LLM-H1 (Prefix Caching) → 단독 작업 가능, 완료 후 data-analyst에 비용 측정 요청
- LLM-H5 (mood_checkin 방어) → backend-dev BD-C5와 같은 파일(main.py) 수정 — 충돌 주의
- LLM-M2 (MBTI별 호감도 행동) → ux-designer와 캐릭터 설계 방향 합의 후 진행

**Definition of Done**

- [ ] 메모리 추출 10턴 시점에서 사용자 응답 지연 0초 (백그라운드 처리 확인)
- [ ] Prefix Caching 적용 후 서버 로그에서 캐시 히트 증가 확인
- [ ] 복잡도 라우팅 점수제: 일상 메시지 70% 이상 mini 모델 사용 (data-analyst 측정)
- [ ] 프롬프트 인젝션 테스트 케이스 5개 통과
- [ ] MBTI별 few-shot 예시 각 그룹 3개 이상 검수 완료

---

### 3.4 ux-designer

**담당 범위**: UI/UX 설계, 화면 레이아웃, 감정 설계, 접근성, 유대감 강화

#### Phase 1 — Critical (1-2일)

| 이슈 ID | 내용 | 예상 공수 | 참조 |
|--------|------|---------|------|
| UX-C1 | 온보딩 재진입 방지 — `isOnboardingDone` 체크 후 HomeScreen 분기 | 1h | C-6 |
| UX-C2 | ChatScreen 로딩 UI 중복 — `MessageSkeleton` 제거, `TypingBubble` 단일화 | 0.5h | D-C2 |
| UX-C3 | HomeScreen 배너 과밀 — `ImageGeneratorBannerCard` FAB으로 이동, `GalleryBanner` 칩 축소 | 1.5h | D-C3 |
| UX-C4 | CharacterProfileScreen 삭제 버튼 중복 — TopAppBar 아이콘 제거 | 0.5h | D-C4 |
| UX-C5 | SettingsScreen Snackbar 직접 렌더 → `SnackbarHostState` 패턴으로 교체 | 1h | D-C5 |
| UX-C6 | ChatScreen 애니메이션 영역 140dp → 120dp, CollapsingToolbar 패턴 설계 | 2h | D-C1 |

#### Phase 2 — High (3-5일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| UX-H1 | 한국어 감성 폰트 적용 — Noto Sans KR (본문) + Gaegu (캐릭터 텍스트) 선정 및 Typography 완성 | 2h |
| UX-H2 | 피드백 아이콘(👍👎) 마지막 AI 메시지에만 표시 또는 롱탭 메뉴로 이동 | 1h |
| UX-H3 | 레벨다운 AlertDialog → 상단 슬라이드 토스트 ("관계가 조금 멀어졌어요...") | 1h |
| UX-H4 | Settings 진입점 단일화 — TopBar 아이콘 제거, BottomNav로 통일 | 0.5h |
| UX-H5 | CharacterProfileScreen 버튼 배치 재구성 — "대화하기" 최상단, "삭제" 더보기로 이동 | 1h |
| UX-H6 | VoiceCall 라이트모드 배경 분기 — `isSystemInDarkTheme()` 적용 | 0.5h |
| UX-H7 | MBTI 그리드 4열 복원 + 디자인 스펙 확정 (frontend-dev FE-H6 연동) | 0.5h |
| UX-H8 | Gallery NavHost `launchSingleTop = true` + `saveState/restoreState` | 0.5h |
| UX-H9 | 접근성: `"\uD83D\uDD12"` 이모지 Text → `Icon(contentDescription)` 교체 (A-1) | 0.5h |
| UX-H10 | 접근성: `CharacterFace` contentDescription 추가 (A-2) | 0.5h |
| UX-H11 | 접근성: 일기 펼치기/접기 터치 타겟 `size(48.dp)` 보장 (A-3) | 0.5h |

#### Phase 3 — 경쟁력 강화 (1-2주)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| UX-M1 | 레벨업 셀레브레이션 강화 — 풀스크린 파티클 + 캐릭터 특별 메시지 + "새 감정 해금!" 토스트 설계 | 3h |
| UX-M2 | MBTI별 "생각 중" 상태 차별화 4가지 애니메이션 설계 (INTJ/ENFP/ISFJ/ESTP) | 3h |
| UX-M3 | 음성 통화 3상태 비주얼라이저 설계 (듣는 중/생각 중/말하는 중 파동 시각화) | 2h |
| UX-M4 | 온보딩 MBTI 선택 시 캐릭터 반응 메시지 미리보기 | 2h |
| UX-M5 | Lv.1 "낯선 사이" 태그 표시 (I-9) | 0.5h |
| UX-M6 | 홈 화면 호감도 수치 → 관계적 카피 대체 ("아직 대화가 없어요. 먼저 인사해 보세요!") | 1h |
| UX-M7 | 일기 생성 중 `CircularProgressIndicator` → 펜 움직이는 Lottie 교체 (I-16) | 1.5h |
| UX-M8 | 채팅 첫 대화 유도 — 캐릭터별 대화 스타터 칩 제안 (I-8) | 2h |
| UX-M9 | 호감도 바 변화 시 펄스 애니메이션 + 수치 팝업 (I-7) | 1.5h |
| UX-M10 | FinetuneCard "GPT 파인튜닝" → "이 캐릭터를 더 나답게" 카피 래핑 (I-12) | 0.5h |
| UX-M11 | WCAG 대비: SoftYellow/TextDark 3.8:1 → 4.5:1 이상으로 조정 (I-3) | 1h |

#### Phase 4 — 차별화 (2-4주)

| 이슈 ID | 내용 |
|--------|------|
| UX-E1 | 캐릭터 프로필 "관계 여정" 5단계 아이콘 경로 시각화 |
| UX-E2 | 일기 → "추억 타임라인" 감정 캘린더 뷰 |
| UX-E3 | 홈 빈 상태 랜덤 캐릭터 인사 메시지 ("INFP 유나가 당신을 기다리고 있어요") |
| UX-E4 | 온보딩 완료 후 웰컴 애니메이션 ("준비됐어요! 첫 친구를 만나볼까요?") |
| UX-E5 | 앱 로고 SVG 심볼 강화 |
| UX-E6 | 호감도 색상만 구분 → 색각이상 사용자 대비 텍스트 레이블 병행 (A-5) |

**다른 에이전트와의 의존성**

- UX-C6 (ChatScreen CollapsingToolbar) → frontend-dev 구현 의뢰, 설계 스펙 선행 제공
- UX-H1 (감성 폰트) → frontend-dev에 폰트 파일 + Typography 스펙 전달
- UX-M1 (레벨업 셀레브레이션) → llm-expert와 "레벨업 시 특별 캐릭터 메시지" 프롬프트 합의
- UX-M2 (MBTI별 생각 중) → llm-expert의 캐릭터 정의 데이터 참조
- UX-M8 (대화 스타터 칩) → llm-expert에 MBTI별 첫 대화 예시 텍스트 요청

**Definition of Done**

- [ ] Critical 6건 Android 빌드에서 동작 확인
- [ ] 접근성 A-1/A-2/A-3 항목 TalkBack 스크린리더 통과
- [ ] Typography 완성본 전체 화면 적용 후 디자인 검수 완료
- [ ] 레벨업 셀레브레이션 사용자 테스트 1회 이상 수행

---

### 3.5 data-analyst

**담당 범위**: 이슈 개선 효과 측정 설계, 이벤트 데이터 품질, A/B 테스트, 리텐션 분석

#### Phase 1 — 즉시 (1-2일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| DA-C1 | `llm_usage` 이벤트 `room_id=""` 기록 문제 — 방별 LLM 비용 집계 불가 현황 파악, 수정 요청 명세 작성 | 1h |
| DA-C2 | room_id 포맷 변경으로 기존 메트릭 데이터 조회 불가 범위 산정 | 2h |

#### Phase 2 — 이번 스프린트 (3-5일)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| DA-H1 | LLM-H1 (Prefix Caching) 적용 후 비용 절감 효과 측정 쿼리 작성 | 1.5h |
| DA-H2 | LLM-H2 (복잡도 라우팅 점수제) 적용 후 mini/full 모델 분배 비율 A/B 측정 설계 | 2h |
| DA-H3 | 메모리 추출 백그라운드 전환 후 10턴 응답 지연 개선 효과 측정 | 1h |
| DA-H4 | 호감도 시스템 건강도 대시보드 설계 — 감쇠율/복귀율/레벨업 빈도 | 2h |

#### Phase 3 — 다음 스프린트 (1-2주)

| 이슈 ID | 내용 | 예상 공수 |
|--------|------|---------|
| DA-M1 | UX 개선 항목 효과 측정 A/B 테스트 설계 — 우선 3개 선정 (레벨업 셀레브레이션, 대화 스타터 칩, 호감도 카피) | 3h |
| DA-M2 | Day 1/7/30 리텐션 코호트 분석 — 현재 기준값 측정 | 2h |
| DA-M3 | 채팅 세션 길이 분포 분석 (10턴 이전 이탈 사용자 파악) | 2h |
| DA-M4 | MBTI 유형별 호감도 성장 속도 차이 분석 | 2h |
| DA-M5 | quality/dashboard 데이터 신뢰도 검증 (MED-S6 수정 후 재검증) | 1h |

**다른 에이전트와의 의존성**

- DA-C1 → backend-dev BD-L6 수정 이후 집계 재개
- DA-H1/H2 → llm-expert LLM-H1/H2 적용 완료 후 측정 시작
- DA-M1 → ux-designer UX-M1/M8 구현 완료 후 A/B 설계 확정

**Definition of Done**

- [ ] `llm_usage` room_id 기록 정상화 확인
- [ ] Prefix Caching 적용 전후 비용 비교 리포트
- [ ] Day 1/7/30 리텐션 기준값 측정 완료 (이후 개선 작업의 비교 기준)
- [ ] A/B 테스트 설계서 3건 작성 완료

---

## 4. 스프린트 계획

### Phase 1 — 긴급 대응 (Day 1-2)

**목표**: 보안 취약점 차단, 서비스 안정성 확보

| 에이전트 | 작업 | 이슈 ID |
|---------|------|--------|
| backend-dev | FCM 소유권 검증, IDOR 패치, LIKE 이스케이프, SQL 수정, API Key 재발급, /docs 비활성화 | BD-C1~C7 |
| frontend-dev | FCM 토큰 로그 마스킹, AuthInterceptor Mutex, OfflineMessageQueue withLock, 로그아웃 DB 삭제, 백업 규칙 | FE-C1~C5 |
| llm-expert | 메모리 추출 백그라운드, 호감도 태스크 예외 처리 | LLM-C1~C2 |
| ux-designer | 온보딩 재진입 방지, 로딩 UI 중복 제거, 배너 과밀 해소, 삭제 버튼 중복, Snackbar 수정, 애니메이션 영역 축소 | UX-C1~C6 |
| data-analyst | llm_usage room_id 현황 파악, room_id 변경 영향 범위 산정 | DA-C1~C2 |

**병렬 실행 가능**: backend-dev Phase 1 전체 + frontend-dev Phase 1 전체 + llm-expert Phase 1 전체 (파일 충돌 없음)
**주의**: UX-C6 (ChatScreen 레이아웃) 작업 시 frontend-dev 동시 수정 주의

---

### Phase 2 — 이번 스프린트 (Day 3-7)

**목표**: 기능 정확성 복구, LLM 비용 최적화, UX 품질 개선

| 에이전트 | 핵심 작업 |
|---------|---------|
| backend-dev | 비동기 전환 4건, finetune 보호, rate limit 추가, PostgreSQL 폴백 수정, room_id 마이그레이션 스크립트 |
| frontend-dev | room_id/MbtiGroup Room 마이그레이션, Compose 버그 6건, BASE_URL 외부화 |
| llm-expert | Prefix Caching 분리, 복잡도 라우팅 점수제, thinking 필드 활성화, Prompt Injection 방어, Few-shot 재구성 |
| ux-designer | 감성 폰트 적용, 피드백 아이콘 정리, 레벨다운 토스트, 버튼 배치 재구성, 접근성 3건 |
| data-analyst | LLM 비용/모델 분배 측정, 호감도 대시보드 설계 |

**BD-H10 + FE-H1 동시 착수 필수**: room_id 마이그레이션은 서버-Android 양쪽 동시 배포가 필요하므로 착수 전 배포 순서 합의 필요.

---

### Phase 3 — 다음 스프린트 (Week 2-3)

**목표**: 캐릭터 깊이 강화, 경쟁력 있는 UX 기능 출시

| 에이전트 | 핵심 작업 |
|---------|---------|
| backend-dev | rate limit uid 기반, 입력 검증, CORS 정리, 트랜잭션, 키 충돌 수정 |
| frontend-dev | DataStore 암호화, SQLCipher, 인증서 피닝, ProGuard 최소화 |
| llm-expert | 안전 가드레일, MBTI별 호감도 행동 오버라이드, 야간 일기 mini 전환, 재생성 품질 비교 |
| ux-designer | 레벨업 셀레브레이션 강화, MBTI별 생각 중 애니메이션, 음성 통화 비주얼라이저, 대화 스타터 칩 |
| data-analyst | Day 1/7/30 리텐션 기준값, 채팅 세션 분석, A/B 테스트 설계 3건 |

---

### Phase 4 — 백로그 (Week 4+)

| 범주 | 항목 |
|------|------|
| 아키텍처 개선 | main.py APIRouter 도메인 분리, N+1 쿼리 최적화 |
| 차별화 UX | 관계 여정 시각화, 추억 타임라인, 홈 빈 상태 감성 강화 |
| 코드 품질 | 지연 임포트 정리, 중복 검증 제거, 비용 추적 개선 |
| 접근성 | 색각이상 레이블 병행, 피드백 아이콘 터치 타겟 |

---

## 5. 의존성 맵

### 5.1 선행 조건 관계

```
[BD-C6] OpenAI API 키 재발급
    → 즉시 실행, 다른 작업의 선행 조건 아님

[BD-H10] room_id 마이그레이션 스크립트 (서버)
    → [FE-H1] room_id Room Migration v8 (Android)
    → 두 작업 완료 후 동시 배포

[FE-H2] MbtiGroup enum Migration
    → [UX-H7] MBTI 그리드 4열 디자인 확정 (선행)

[LLM-H7] Few-shot 8그룹 세분화
    → [LLM-M2] MBTI별 호감도 행동 오버라이드
    → (선행 데이터로 활용)

[UX-H1] 감성 폰트 선정 + Typography 스펙
    → [FE] 폰트 적용 구현

[UX-M1] 레벨업 셀레브레이션 설계
    → [LLM-expert] 레벨업 시 캐릭터 특별 메시지 프롬프트
    → [frontend-dev] 애니메이션 구현

[LLM-H1] Prefix Caching 적용
    → [DA-H1] 비용 절감 효과 측정 (후행)

[LLM-H2] 복잡도 라우팅 점수제
    → [DA-H2] A/B 측정 (후행)
```

### 5.2 병렬 실행 가능 그룹

**그룹 A — 완전 독립 (동시 실행 가능)**

- backend-dev Phase 1 보안 패치 (서버 파일)
- frontend-dev Phase 1 Android 보안 패치 (Android 파일)
- llm-expert LLM-C1/C2 (chat_service.py 비동기 전환)
- data-analyst DA-C1/C2 (현황 파악, 파일 수정 없음)

**그룹 B — 조율 필요 (같은 파일 수정)**

- BD-C2 + BD-H5 (main.py 인증 관련) → backend-dev 내부 순서 조율
- LLM-H5 (mood_checkin 방어, main.py) → BD-C5 (session_start 수정, main.py) → 같은 파일, PR 분리 권장
- UX-C6 (ChatScreen 레이아웃 설계) + FE-H3 (compatibility!! 수정, CharacterProfileScreen) → 다른 파일, 병렬 가능

**그룹 C — 순차 필수**

1. BD-H10 완료 → FE-H1 착수 (room_id 마이그레이션)
2. UX-H7 완료 → FE-H6 착수 (MBTI 그리드 레이아웃 확정 후 구현)
3. UX-H1 완료 → frontend-dev 폰트 적용 (스펙 확정 후 구현)
4. UX-M1 완료 → LLM 메시지 작성 + FE 애니메이션 구현

---

## 6. 리스크 관리

### 6.1 작업 간 충돌 가능성

| 리스크 | 영향 | 대응 |
|--------|------|------|
| BD-H10 + FE-H1 배포 순서 불일치 | room_id 포맷 불일치로 기존 사용자 데이터 조회 실패 | 서버 먼저 배포 (구버전 room_id 읽기 호환 유지 1주), Android 업데이트 후 구버전 폐기 |
| main.py 동시 수정 (BD-C2, BD-C5, LLM-H5) | Git 충돌 | PR을 도메인별로 분리 발행, 리뷰 후 순차 머지 |
| FE-H2 MbtiGroup Migration 누락 배포 | 기존 사용자 앱 크래시 | 스테이징 환경에서 구버전 DB 마이그레이션 시뮬레이션 필수 |
| LLM-H1 Prefix Caching 분리 후 프롬프트 동작 변경 | 캐릭터 반응 품질 저하 | 10개 대표 시나리오 LLM 응답 수동 검수 후 배포 |
| HIGH-A2 SQLCipher 적용 | 기존 Room DB 데이터 접근 불가 | 마이그레이션 전 백업 + `SupportFactory` 전환 테스트 |

### 6.2 회귀 테스트 필수 항목

Phase 1/2 완료 후 아래 시나리오 전수 확인 필요.

**보안 패치 회귀**
- [ ] 정상 인증 사용자의 delete_conversation 동작 확인
- [ ] FCM 알림 정상 수신 (소유권 검증 이후)
- [ ] get_memories API 정상 동작 (LIKE 이스케이프 이후)

**데이터 마이그레이션 회귀**
- [ ] room_id 포맷 변경 후 기존 대화 기록 조회 가능
- [ ] MbtiGroup enum 변경 후 Room DB 역직렬화 정상
- [ ] 호감도 데이터 room_id 기반 집계 정상

**LLM 파이프라인 회귀**
- [ ] 메모리 추출 백그라운드 전환 후 10턴 응답 정상
- [ ] 호감도 분석 실패 시 기본값 0 처리 (채팅 응답은 정상 전달)
- [ ] Prefix Caching 분리 후 캐릭터 말투/감정 품질 유지

**Android 안정성 회귀**
- [ ] OfflineMessageQueue 오프라인 → 온라인 전환 시 메시지 전송 정상
- [ ] AuthInterceptor Mutex 적용 후 동시 요청 처리 정상
- [ ] 로그아웃 → 재로그인 후 CharacterProfileScreen 크래시 없음

### 6.3 측정 기준 없는 작업 금지 원칙

Medium 이상 모든 작업은 착수 전 data-analyst와 측정 방법 합의 필수. "개선했다"는 주관적 판단이 아니라 "Day 7 리텐션 X% → Y%", "mini 모델 사용 비율 X% → Y%" 등 수치로 확인 가능해야 한다.

---

## 7. PM 의사결정 사항

### 이번 스프린트에서 하지 않을 것

다음 항목은 이번 사이클에서 명시적으로 제외한다. 스코프 크립 방지.

1. **크리에이터 이코노미 / UGC 캐릭터** — 경쟁 앱 벤치마크에서 언급됐으나 현재 "16종 고정 깊이"가 차별점. 검증 없이 착수 금지.
2. **Live2D / 3D 캐릭터 전환** — Kindroid 벤치마크 언급. 현재 AGSL + LiveCharacter 레이어 방식 유지, 3D 전환은 별도 기술 검증 스프린트 필요.
3. **iOS 포팅** — 현재 Android 단독 안정화 우선.
4. **다국어 지원** — 한국어 품질 완성 후 검토.
5. **음성 파인튜닝 / 커스텀 TTS** — Phase 4 이후 검토.

### 핵심 집중 지표 (이번 사이클)

- **Day 7 리텐션**: 현재 기준값 측정 → 개선 목표 +5%p
- **LLM 비용**: Prefix Caching + 라우팅 개선으로 30% 절감 목표
- **10턴 응답 지연**: 메모리 추출 백그라운드 전환 후 0초 목표
- **Critical 보안 이슈**: Phase 1 종료 시점에 0건

---

*작성: PM (2026-04-13)*  
*기반 문서: code-review-260413.md / 260413_security_review.md / 260413_디자인리뷰.md / 260413_server_review.md*
