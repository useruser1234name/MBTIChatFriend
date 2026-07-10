# MBTIChatFriend 개선 계획서

- **문서 버전**: 2026-06-13
- **작성 방식**: 6라운드 멀티에이전트 회의(전문가6 → 자유토론 → 비판자3 → 메타비판2 → 종합 → 독립재검증) + 계획수립 회의(PM·backend·frontend)
- **검증 상태**: 결론서 load-bearing 주장 11개 코드 재검증 거짓 0건 / 2차 주장 18개 추가 재검증(Android·서버/LLM) 거짓 0건 / 서버 테스트 **115 passed GREEN**
- **제약**: 서버 테스트 115 GREEN 유지 · LLM은 gpt-4.1/4.1-mini만(gpt-4o 금지) · Hilt DI · Room 순차 마이그레이션

> 이 문서는 회의록 영속화 권고에 따라 작성됨. 모든 항목은 파일:라인으로 코드 확인된 사실에 근거하며, 추정 수치(리텐션 %, 비용 절감률)는 KPI 약속에서 제외됨.

---

## 0. Executive Summary

- **현 상태**: 코어 채팅·호감도 파이프라인은 동작하나 **리텐션 인프라(스케줄러 4잡)가 ImportError로 즉사**, **데이터 위생(키 평문 저장·토큰 로깅)·출시 게이트(백업 차단·계정 삭제) 미충족**, **핵심 코드(스케줄러/SSE/위기감지/Android) 무테스트 + CI 없음**.
- **가장 중요한 단 하나의 결정**: ★ **"이번 분기 스토어 출시를 시도하는가? (Yes/No)"** — 이 노드가 P0 순서 전체를 가른다.
- **분기와 무관하게 오늘 착수**: OpenAI 키 평문 저장 제거 · FCM 토큰 로깅 제거 · chat_turn user_id 한 줄 수정.

---

## 1. 분기 의사결정 가이드

### 핵심 질문: "이번 분기 스토어 출시를 시도하는가?"

답변 전 체크리스트(모름/불확실 3개 이상이면 스프린트0 먼저):

```
[ ] 현재 사이드로딩 사용자 수를 Firebase/서버 로그로 확인했는가?
[ ] Play Console 개발자 계정 + 정책 검토를 완료했는가?
[ ] 계정 삭제 API(cascade) 공수를 산정했는가?  (본 문서 S-6 = 6h 산정 완료)
[ ] Android BillingClient + Console + RTDN 공수를 산정했는가?  (미산정 — 스프린트0 과제)
[ ] 미성년 이용자 보호(연령·콘텐츠 등급)를 검토했는가?
[ ] 개인정보처리방침/이용약관이 앱 내 또는 URL로 존재하는가?
```

### 분기별 P0 순서

- **경로 A — 출시 Yes**: 위생(P0) → 출시게이트(allowBackup·계정삭제·결제) → P1(user_id·스케줄러·측정·rate limit·미러링) → P2 조건부
- **경로 B — 출시 No(개발/측정)**: 위생(P0) → P1(측정 인프라 선행) → 측정 2주 후 P2 결정 → 출시게이트는 다음 분기

### ✅ 권장 디폴트: 경로 B

근거: 출시 게이트(계정삭제 cascade·결제 RTDN·미성년 보호)에 **공수 미검증·정책 거절 리스크**가 묶여 있다. 측정 인프라(user_id·cached_tokens)가 없으면 이후 어떤 개선도 효과 검증이 불가능하다. 측정을 먼저 확보하고, 출시 공수가 검증된 뒤 다음 스프린트에 출시를 시도하는 것이 리스크가 낮다. **단 "사용자 0명"은 미증명**이므로 스프린트0의 사실 확인이 경로를 최종 확정한다.

---

## 2. 스프린트 구성

### 스프린트 0 — 사실확인 + 오늘의 3개 (1~2일)

체크리스트를 채우고 즉시 위생 작업을 끝낸다. 이 결과가 경로 A/B를 확정한다.

| 작업 | 담당 | 공수 | 비고 |
|---|---|---|---|
| 실사용자 수 확인 | PM | XS | Firebase/서버 로그 조회 |
| 출시 Yes/No 결정 + 1줄 기록 | 의사결정자 | — | 체크리스트 기반 |
| OpenAI 키 평문 저장 제거 (A-2) | Frontend | 1h | UserPreferences.kt 죽은 저장소 |
| FCM 토큰 로깅 제거 (A-1) | Frontend | 0.5h | FcmTokenManager.kt:19 |
| chat_turn user_id 수정 (S-2) | Backend | 1h | chat.py:313 |
| BillingClient/Console/RTDN 공수 산정 | Frontend+Backend | — | 경로 A 판단용 |

**DoD**: 테스트 115 GREEN 유지 · FCM 토큰 grep 0건 · chat_turn user_id 기록 확인 · "출시 Yes/No, 이유:___" 문장 작성.

### 스프린트 1 — 측정 인프라 + 핵심 안정화 (1~2주)

| 작업 | 담당 | 공수 | 분기조건 |
|---|---|---|---|
| 스케줄러 4잡 복구 (S-1) | Backend | M(4h) | 무조건 |
| cached_tokens 측정 (S-3) | Backend | S(2h) | 무조건 |
| rate limit 3라우터 (S-4) | Backend | S(1h) | 무조건 |
| /health/circuit-status 인증 (S-5) | Backend | XS(0.5h) | 무조건 |
| 호감도 서버 미러링 | Backend | S | 무조건 |
| 무테스트 영역 테스트 + CI (S-10) | Backend | M(4h) | 무조건 |
| allowBackup=false + 2개 XML (A-3) | Frontend | XS(2h) | 경로 A |
| 계정 삭제 API (S-6) + UI (A-8) | Backend+Frontend | L(6h)+M(3h) | 경로 A |

**DoD**: 테스트 GREEN(신규 포함) · metric_events.user_id NULL 0% · cached_tokens 기록 시작 · 스케줄러 4잡 FCM 발송 도달 + 잡당 통합테스트 · (경로A) adb backup에 DB 미포함.

### 스프린트 2 — 데이터 기반 P2 + (선택) 출시게이트 완료 (2~3주)

P2는 **측정 데이터/크래시 리포트 조건부** 실행(주관 판단 금지):

| 작업 | 실행 조건 | 공수 |
|---|---|---|
| prefix caching 재배치 (S 측정후) | cached_tokens 실측 cache hit < 기대 | M |
| SSE heartbeat(S-8) + 전용 OkHttpClient(A-5) | TTFB p95 > 3초 | 1h+2h |
| 레벨업 MBTI 대사 (A-9) | 레벨업 이벤트 발생률 측정 후 | 2h |
| content_filter dead code 제거 (S-7) | **테스트 선작성 후에만** | 3h |
| ChatViewModel MVI (A-4) | 크래시/ANR 리포트 존재 시 | 4h |
| 홈 배너 리팩터링 (A-7) | UX 불만 피드백 | 6h |
| indexOf → itemsIndexed (A-6) | 무조건(저비용) | 0.5h |
| letter.py 실제 LLM 전환 (S-9) | 무조건(주석 위반 즉시) | 3h |

---

## 3. 서버 작업 상세 (Backend)

> 출처: backend-dev 계획 회의. 각 항목 파일:라인·DoD·회귀위험 포함.

### S-1. 스케줄러 4잡 복구 [P1, 4h]
**버그A**: `scheduler.py:114,181,249,294`의 `from app.postgres_async import _pool` — 모듈 레벨 `_pool` 심볼 부재 → **ImportError 즉사**.
**버그B**: `async with _pool.acquire()` — psycopg3 pool은 `.connection()` 사용(asyncpg `.acquire()` 아님). 단 `AsyncDatabase.fetch()/execute()` 래퍼가 이미 있어 raw pool 접근 불필요.
**수리**: 4개 함수(d3:112-176, d5:179-240, weekly:243-288, gratitude:291-320)를 정상 패턴(`flush_empathy_notifications`:17-22, `send_night_diary_push`:76-86)과 동일하게 `get_async_db()` + `.available` 체크 + `await db.fetch(...)`로 교체. 플레이스홀더 `$1`은 `_to_psycopg()`가 자동 변환하므로 유지.
**DoD(4단)**: ①`_pool` import 0건 ②`_pool.acquire()` 0건 ③`get_async_db().available` 패턴 ④잡당 통합테스트(unavailable→early return / fetch mock→FCM 호출).
**회귀위험**: 낮음(정상 2개 함수 불변).

### S-2. chat_turn user_id 누락 수정 [P1, 1h] — 오늘의 3개
`routers/chat.py:313` `record_event("chat_turn", ...)`에 user_id 미전달 → `metric_events.user_id` NULL → `scheduler.py:262` weekly가 `WHERE user_id IS NOT NULL`이라 발송 0명. `_uid`는 330행(호출부 뒤)에서 추출됨. **수리**: `_uid` 추출을 313행 위로 올리고 `user_id=_uid` 전달. `metrics_service.py:13` 기본값 `""`이라 타 경로 무영향. **회귀위험**: 매우 낮음.

### S-3. cached_tokens 측정 [P1, 2h]
`api_usage`(postgres.py:274-285)에 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS cached_tokens INTEGER NOT NULL DEFAULT 0`. `record_api_usage`(postgres_async.py:179)·`_record_usage`(chat_service.py:853-861,920-940)에 `cached_tokens` 파라미터 추가. OpenAI 응답 `usage.prompt_tokens_details.cached_tokens` 읽기. **회귀위험**: 낮음(IF NOT EXISTS + 기본값 0).

### S-4. rate limit 3라우터 [P1, 1h]
`community.py`/`billing.py`/`fcm.py`에 `@limiter.limit` 0건. 각 상단 `limiter = Limiter(key_func=get_remote_address)` + POST에 데코레이터(community 게시/공감/댓글 20/min, billing verify 10/min·rtdn 30/min, fcm register 10/min·send 30/min) + `request: Request` 파라미터. **회귀위험**: 낮음.

### S-5. /health/circuit-status 인증 [P1, 0.5h]
`health.py:15-35` 무인증 → circuit breaker 상태 노출. `Depends(require_auth_always)` 추가(`/health`는 LB용이라 유지). 모니터링 호출처 사전 확인. **회귀위험**: 낮음(REQUIRE_AUTH=false면 개발 우회).

### S-6. 계정 완전삭제 엔드포인트 [P0 출시게이트, 6h]
현재 `data.py:79`는 대화 단위 삭제만. **삭제 범위**: PG 20+ 테이블(user_id 직접참조 + `room_id LIKE '{uid}:%'` 패턴) + ChromaDB(room_id→character_id 조회 후 `delete_character`) + Firebase Auth(`delete_user`). **순서**: PG(community_posts/comments는 소프트삭제, users 마지막) → ChromaDB → Firebase(재시도 불가라 최후) → `deletion_log` 기록. `postgres_async.delete_account(uid)` best-effort + `DELETE /api/v1/account`(require_auth_always). **회귀위험**: 중간(신규 엔드포인트).

### S-7. content_filter dead code 정리 [P2, 3h, 테스트 선작성 후]
`get_safety_system_prompt` 중복(321·487, 운영은 487) → 321 삭제(`test_prompt_contains_guidelines`가 "1393" assert하므로 487 유지로 GREEN). crisis 3버전(detect_crisis:153/check_crisis:180/detect_crisis_v2:221, 운영 v2). **check_crisis는 이번 스프린트 삭제 금지**(test_content_filter.py가 직접 import) — deprecated 주석만. 삭제 전 grep으로 import 경로 확인. **회귀위험**: 낮음.

### S-8. SSE heartbeat [P2, 1h]
`chat.py:638` `EventSourceResponse(event_generator())`에 `ping` 없음 + `event_generator`(612-623)가 완성 replies 일괄 emit → TTFB=LLM 전체 응답시간. `ping=15` 추가(15초 keepalive). 진짜 토큰 스트리밍(`stream=True`)은 별도 스프린트. Android가 comment frame(`:`) 무시하는지 확인. **회귀위험**: 낮음.

### S-9. letter.py 실제 LLM 전환 [3h]
`letter.py:33-47` 100% Mock + `:36` docstring "GPT-4o"(규칙 위반). ①docstring `gpt-4.1`로 즉시 수정 ②top_topics 기반 `gpt-4.1` 생성(월1회 저빈도·고품질, 중복방지) ③`require_auth_always` 추가. **회귀위험**: 낮음.

### S-10. 무테스트 영역 테스트 + CI [기반, 4h]
`test_scheduler.py` 신규(각 잡 unavailable/happy path), `detect_crisis_v2` 테스트 5케이스 이상(Tier1/관용표현 false positive/맥락 Tier2), `.github/workflows/ci.yml`(push/PR시 pytest). **회귀위험**: 없음.

---

## 4. Android 작업 상세 (Frontend)

> 출처: frontend-dev 계획 회의. P0 위생 3건(A-1·A-2·A-3)은 총 3.5h, 독립적이라 하루 내 완결.

### A-1. FCM 토큰 로깅 제거 [P0 위생, 0.5h] — 오늘의 3개
`FcmTokenManager.kt:19` `Log.d(TAG, "FCM token: $token")` 삭제. 등록 로직 불변. **DoD**: `grep "FCM token:" android/` 0건. **회귀위험**: 없음.

### A-2. OpenAI 키 평문 저장 제거 [P0 위생, 1h] — 오늘의 3개
`UserPreferences.kt:37`(키 정의)·175-183(Flow+`updateOpenAiApiKey()`) 삭제 — 호출처 없는 죽은 저장소. **DoD**: `grep "openai_api_key\|openAiApiKey" android/` 0건 + 빌드 성공. **회귀위험**: 없음.

### A-3. allowBackup + 백업 룰 [P0 출시게이트, 2h]
`AndroidManifest.xml:14` allowBackup=true + `backup_rules.xml`·`data_extraction_rules.xml`(compileSdk 35라 둘 다 실효) 규칙 전부 주석. **수리**: 두 XML에 `mbti_chat_db`(+shm/wal)·`user_prefs.preferences_pb` exclude(cloud-backup + device-transfer 양쪽). allowBackup=true 유지하되 민감 데이터 exclude(비민감 설정은 기기이전 보존). **DoD**: `adb backup` 아카이브에 DB 미포함. **회귀위험**: 중간(sharedpref vs file 경로 — 실제 백업 아카이브 확인 필수).

### A-4. ChatViewModel 이중 상태 MVI 일원화 [P1, 4h]
`_uiState`(126)와 별도로 isTyping(87)/currentEmotion(90)/errorMessage(93)/levelUpEvent(96)/levelDownEvent(99) mutableStateOf 병렬. isTyping 변경이 syncUiState()(134) 미트리거 → 불일치. **수리**: ChatUiState.Success에 필드 흡수 + 변경지점 6곳(340·406·418·435·496·514)에 syncUiState() 삽입 + AffinityManager collect(199-204)에 추가 + ChatScreen 점진 마이그레이션. A-9와 묶기 권장(ChatUiState 1회 수정). **회귀위험**: 높음(grep `isTyping = ` 전수 후 처리).

### A-5. SSE 전용 OkHttpClient [P1/P2, 2h]
`SseClient.kt:37`이 AppModule(:96) 단일 클라이언트 공유, readTimeout 30s(:108). `@Named("sse")` 분리 + `readTimeout(0)`. `provideRetrofit` 파라미터에 `@Named("default")` 명시 필수(ambiguous binding 방지). 서버 heartbeat(S-8)와 함께 효과. **회귀위험**: 중간.

### A-6. indexOf → itemsIndexed [P2, 0.5h]
`ChatScreen.kt:343-344` items 루프 내 `messages.indexOf(msg)` O(N²)(359행 shareTargetIndex만 사용). `itemsIndexed(messages, key={_,msg->msg.id})`로 교체. **회귀위험**: 낮음.

### A-7. HomeUiState Boolean 17개 → BannerItem 리스트 [P2, 6h]
`HomeUiState.kt:18-51` Boolean 17개, `HomeViewModel.syncHomeUiState()`(62-112) 16함수 순차호출. `enum BannerType` + `data class BannerItem` + `activeBanners: List<BannerItem>` + `buildList{}`. 신규 배너=enum 1줄+조건 1줄. 카루셀 UI와 묶기. **회귀위험**: 중간(점진 마이그레이션).

### A-8. 계정 삭제 UI + 서버 연동 [P0 출시게이트, 3h]
`SettingsScreen.kt:475`는 로그아웃만. **수리**: SettingsViewModel `deleteAccount()`(S-6 API 호출 + signOut + clearAll + Room deleteAll) + ChatApi `@DELETE("api/v1/account")` + 2단계 확인 다이얼로그. S-6 스펙 확정 후 착수. **회귀위험**: 낮음.

### A-9. 레벨업 전용 대사/연출 [S, 2h]
파이프라인 완성(AffinityManager._levelUpEvent:24/before<after:38, ChatScreen:393-440 AlertDialog+LottieOneShot `levelup.json` 실재). `:430` 고정문구 → MBTI×레벨 대사맵. A-4의 ChatUiState에 `levelUpCharacterLine` 추가해 함께. **회귀위험**: 없음(텍스트 교체).

### A-10. Android 단위 테스트 도입 [기반, 6-8h]
`ExampleUnitTest` 스켈레톤뿐, CI 없음. AffinityManager 레벨 경계값(turbine/mockk), HomeViewModel 배너 날짜조건, ContentFilter 차단 테스트 + `.github/workflows/android-unit-test.yml`. A-4 완료 후 권장. **회귀위험**: 없음.

---

## 5. 성공지표(KPI) 프레임

**측정 인프라 없는 수치 목표 금지.** 스프린트0에 user_id, 스프린트1에 cached_tokens 기록 시작 → 그 이전 "리텐션 X%"류는 근거 없는 약속이라 본 문서에서 제외.

**측정 인프라 완성 + 2주 경과 시 베이스라인 확정 후 추적**: DAU(metric_events.user_id) · 7일 리텐션 · 세션당 턴수 · 레벨업 도달률 · prefix cache hit율(cached_tokens/prompt_tokens) · LLM 비용/DAU · 스케줄러 알림 도달률.

**현재 측정 불가(약속 금지)**: "리텐션 25% 향상"(베이스라인 없음) · "prefix caching 30-50% 절감"(실측 5-15% 가능성, 측정 먼저) · "결제 전환율"(BillingClient 미구현).

---

## 6. 리스크 레지스터

| # | 리스크 | 분류 | 대응 |
|---|---|---|---|
| R1 | 실사용자 수 미확인("0명"일 수도, 사이드로딩 사용자 있을 수도) | 미검증 가정 | 스프린트0에서 Firebase+서버로그 확인 후 경로 재조정. **실사용자 있으면 위생 P0는 진행 중인 사고가 됨** |
| R2 | 결제 공수 과소평가("반나절" 미검증) | 미검증 가정 | 스프린트0에서 BillingClient+Console+RTDN 각각 산정 후 합산 |
| R3 | prefix caching 효과 과대 기대(5-15% 실측) | 미검증 가정 | cached_tokens 2주 측정 후 실측값으로 결정, 30-50% 목표 설정 금지 |
| R4 | FCM 토큰 노출(Android 전체 토큰 + 서버 user_id 일부) | 보안 | A-1 + 서버 firebase_service 로그 점검 |
| R5 | OpenAI 키 접근통제(서버 .env는 환경변수지만 비밀관리자 미연동) | 보안(P1 권고) | .env 접근권한 문서화 + Secrets Manager 연동 검토 |
| R6 | allowBackup=true로 출시 시 DB/prefs 클라우드 백업 | 보안/정책 | 경로A 스프린트1에서 A-3 필수 |
| R7 | 스케줄러 미동작 → 재방문 훅 부재 | 제품 | S-1 P1, 지연 불가 |
| R8 | 테스트 공백(scheduler/SSE/v2/Android 0건) | 품질 | dead code 삭제 전 테스트 선작성, 수정 대상에 테스트 1건+ |
| R9 | CI 없음(로컬 테스트만) | 품질/프로세스 | S-10에서 GitHub Actions 최소 워크플로 |
| R10 | 미성년 보호 미검토 | 법/정책 | 경로A에서 콘텐츠 등급 신청+정책 검토 |
| R11 | 호감도 클라 단독관리(models.py:196, 서버 권위 없음) | 데이터무결성 | 호감도 서버 미러링(스프린트1) → 재설치 리셋·조작 방지 |

---

## 7. 다음 회의 고정의제 (감산 원칙)

1. **출시 Yes/No 최종 결정** — 체크리스트 채운 뒤 1줄 기록
2. **결제 구현 공수 확정** — "반나절" 가정 폐기, 실수치 제출
3. **계정 삭제 cascade 범위 확정** — S-6 테이블 목록 + Firebase + Storage
4. content_filter dead code: 테스트 선작성 없이 일정 잡지 않음
5. few-shot 16종 확장: 측정 데이터 없으면 의제 불허(보류 유지)
6. prefix caching 재배치: cached_tokens 2주 데이터 없으면 의제 불허
7. (매 회의) 테스트 passed 수 확인 — 115 미만이면 스프린트 완료 불가

---

## 8. 거버넌스 / 프로세스 개선

- **회의록 영속화**: 본 문서가 그 첫 적용. 회의마다 "핵심 결정노드 + 미검증 가정 목록"을 기록하고, 가정이 검증/반증되면 상태 변경(삭제 아님).
- **원칙**: 측정 인프라 없는 지표 약속 금지 · 테스트 선작성 없는 dead code 제거 금지 · 공수 미산정 기능의 스프린트 배정 금지 · 모든 P2 착수 조건은 "데이터 or 크래시 리포트"(주관 판단 금지).
- **재검증으로 하향된 과장(기록 보존)**: prefix caching "30-50%"→5-15% · "평문=위법"→P1 권고 · "결제 반나절"→미검증 · "배포 전무"→Docker 잔존 · "사용자 0명"→미증명 · few-shot 16종→보류.

---

## 부록: 핵심 파일·라인 인덱스

| 영역 | 파일:라인 | 내용 |
|---|---|---|
| 스케줄러 | `server/app/scheduler.py:114,181,249,294` | `_pool` import(즉사) |
| 스케줄러 정상패턴 | `server/app/scheduler.py:17-22,76-86` | get_async_db().fetch |
| user_id 누락 | `server/app/routers/chat.py:313` | record_event |
| weekly 쿼리 | `server/app/scheduler.py:262` | WHERE user_id IS NOT NULL |
| api_usage | `server/app/postgres.py:274-285` | cached_tokens 컬럼 추가 대상 |
| rate limit 누락 | `community.py / billing.py / fcm.py` | @limiter 0건 |
| circuit-status | `server/app/routers/health.py:15-35` | 무인증 |
| 계정삭제 부재 | `server/app/routers/data.py:79` | 대화단위만 |
| content_filter 중복 | `server/app/content_filter.py:321,487` | get_safety_system_prompt |
| crisis 3버전 | `content_filter.py:153,180,221` | detect_crisis/check_crisis/v2 |
| letter mock | `server/app/routers/letter.py:33-47,36` | Mock + GPT-4o 주석 |
| SSE | `server/app/routers/chat.py:612-623,638` | 일괄 emit, ping 없음 |
| 호감도 클라 | `server/app/models.py:196` | current_affinity_score 클라 신뢰 |
| FCM 로깅 | `FcmTokenManager.kt:19` | 토큰 평문 |
| OpenAI 키 | `UserPreferences.kt:37,175-183` | 죽은 평문 저장소 |
| 백업 | `AndroidManifest.xml:14,15` + 2 XML | allowBackup + 빈 규칙 |
| ChatVM 이중상태 | `ChatViewModel.kt:87,90,93,96,99,126,134` | mutableStateOf 병렬 |
| SSE 클라 | `SseClient.kt:37`, `AppModule.kt:96,108` | 공유 OkHttpClient 30s |
| indexOf | `ChatScreen.kt:343-344` | O(N²) |
| 배너 | `HomeUiState.kt:18-51`, `HomeViewModel.kt:62-112` | Boolean 17개 |
| 레벨업 | `AffinityManager.kt:24,38`, `ChatScreen.kt:393-440` | 파이프라인 완성 |
