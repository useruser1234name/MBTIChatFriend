# MBTIChatFriend 개선 계획서 — 서버 성능 · UI/UX · 디자인 · 살아있는 캐릭터 (2026-07-08)

> **실행자 전제**: 이 문서와 코드 외에 컨텍스트 없음. 줄 번호는 2026-07-08 작업 트리 기준 — 실행 시 반드시 심볼 이름으로 재확인. **이 계획은 리팩토링 계획서(`docs/REFACTORING_PLAN_2026-07-07.md`)와 별개의 브랜치·별개의 성격(동작 변경 포함)**이다. 아래 "선행 조건" 참조.

---

## 0. 선행 조건 및 리팩토링 계획과의 관계

1. **필수 선행**: `REFACTORING_PLAN_2026-07-07.md`의 항목 0-1(미커밋 스프린트 보존 커밋)과 0-2(기준선 기록)가 완료돼 있어야 한다. `git log`로 확인 — 안 돼 있으면 그것부터 수행.
2. **권장 순서**: 리팩토링 계획 전체 완료 → 본 계획. 두 계획이 같은 파일(`chat_service.py`, `routers/chat.py`, `ChatScreen.kt`)을 수정하므로 병행하면 충돌한다. 리팩토링을 건너뛰고 본 계획을 먼저 실행하는 것도 가능하나, 그 경우 두 계획의 줄 번호가 서로 어긋나게 됨을 보고할 것.
3. **브랜치**: `improve/2026-07-perf-ux-character` (0-1 커밋 이후 분기).
4. **기준선**(2026-07-08 실측): 서버 `cd server && python -m pytest tests/ -q` → **177 passed, 2 skipped**(리팩토링 0-3 수행 후라면 그 시점의 N₀). Android `cd android && .\gradlew.bat compileDebugKotlin` → BUILD SUCCESSFUL.
5. **본 계획은 동작 변경을 포함한다** (리팩토링과 다름). 따라서 각 항목의 완료 기준에 "새 테스트" 또는 "수동 QA 체크"가 명시돼 있고, 기존 테스트가 의도적으로 갱신되는 경우 항목에 명기했다. 명기되지 않은 기존 테스트가 깨지면 중단·보고.
6. **프롬프트 골든 테스트 주의**: 리팩토링 0-3(b)의 `test_prompts_golden.py`가 존재하는 상태에서 C4(시간대 인지)를 실행하면 골든이 깨진다 — C4 완료 기준에 골든 갱신이 포함돼 있다(유일한 허용).

---

## 1. 현재 이해 (조사 결과 요약)

### 1-A. 서버 성능 (조사: 스트림 1턴 크리티컬 패스 추적)

첫 토큰(TTFT) 전에 **직렬로** 실행되는 것: 콘텐츠 필터 → `_gate_user`(DB 2-3회) → `_prepare_chat_turn`의 `bump_turn_and_get_state`(**동기 DB, 루프 블로킹**) → `build_memory_context`(병렬 작업 시작 전에 단독 직렬 대기, `chat_service.py:1131`) → RAG(OpenAI 임베딩 왕복 + Chroma 2쿼리, `chat_service.py:1190`에서 대기) → 프롬프트 조립 → 메인 LLM 호출.

핵심 사실:
- **동기 DB 레이어(`postgres.py`)는 풀이 없다** — `get_conn()`이 호출마다 psycopg 신규 접속+해제(`postgres.py:170-178`). 이 동기 호출이 async 컨텍스트에서 **to_thread 없이** 매 턴 ~7회 실행되어 이벤트 루프를 블로킹: `bump_turn_and_get_state`(`routers/chat.py:125`), `record_event(chat_turn)`(`chat.py:266`), `get_plan`(`subscription.py:110`, `_gate_user` 경유 매 턴), `check_diversity`(`quality_service.py:281`), `record_event(quality_score)`(`quality_service.py:89`), AB `record_result`×2(`ab_test.py:261`), `mark_callback_used`/`get_story_state`(`story_state_store.py`).
- **async 풀은 min=2/max=10 하드코딩**(`postgres_async.py:64-68`)으로 `config.py:35-36`의 `DB_POOL_MIN_SIZE=5/MAX=20`을 무시. 스케줄러 잡 6종이 같은 풀을 공유.
- **인덱스 없는 스캔 매 턴 2회**: `api_usage WHERE room_id LIKE '{uid}:%'`(`postgres_async.py:229`, `subscription.py:166`) — `api_usage`에 `room_id` 인덱스 없음(있는 것: `created_at`, `model_id`, `postgres.py:292,296`). `check_diversity`의 `metric_events (event_type, room_id, created_at)` 복합 인덱스도 없음.
- **LLM 호출 수/턴**: 크리티컬 1(메인) + 병렬 1(호감도, gpt-4.1-mini) + 백그라운드 1(품질) + 10턴마다 +3(요약/팩트/에피소드). 스트림 경로는 품질 게이트 재생성 없음(텔레메트리만).
- **스트림 경로의 구멍**: ① `api_usage` 미기록(`_record_usage`는 `generate_reply`에만, `chat_service.py:1018`) → 예산/한도 게이트가 SSE 턴을 과소계상, 비용 대시보드 왜곡. ② 메인 LLM 호출이 서킷브레이커 미보호(`chat_service.py:1244`; generate_reply는 `:894`에서 보호).
- **계측 공백**: TTFT/단계별 타이밍 지표 전무. 레이턴시는 A/B 변형 활성 시에만 기록(`chat_service.py:1321`). **측정 없이는 튜닝 검증 불가 → P1이 최우선.**
- **프리픽스 캐싱 설계는 건전**(검증됨): 정적 블록(`prompts.py:1124-1166`)에 날짜/랜덤 없음, few-shot 결정적(`prompts.py:813-815`), 동적 섹션은 전부 뒤(`:1168-1169`). → **동적 정보는 반드시 이 꼬리에만 추가해야 함(C4 주의)**.
- 서버는 인위적 sleep 없음 — 버블 `delay`는 클라이언트가 소비(`ChatViewModel.kt:414`).

### 1-B. UI/UX·디자인 (Android)

- **디자인 토큰**: 색상 50종은 양호(감정 버블은 라이트/다크 쌍으로 모범적). 그러나 **spacing/shape/elevation/motion 토큰 전무** — `RoundedCornerShape` 107곳 제각각(버블 20/입력창 24/칩 20/재전송 12/온보딩 16), dp 리터럴 전면, `tween(300)` ~30회 복붙. `MaterialTheme`에 shapes 미배선(`Theme.kt:74-78`).
- **원색 리터럴 168곳/25파일** — 최다: 홈 시즌 배너 카드 ~15종(전부 라이트 전용), `ChatScreen.kt:557-566` 캐릭터 무대 그라데이션(다크모드에서 밝은 핑크로 깨짐), `GratitudeCardSection.kt:45-47`.
- **채팅 UX**: 오프라인 큐/재전송/타이핑 인디케이터는 강함. 결함: ① 자동 스크롤이 사용자가 위로 스크롤 중이어도 강제(`ChatScreen.kt:143-147`), ② 피드백 썸 터치타겟 28dp(`:841,861`, 최소 48dp 미달), ③ 롱프레스가 공유만(복사 없음), ④ `emotionEmoji`가 ASCII 텍스트(`^^`, `T_T`, `:1061-1072`).
- **로딩 상태**: 스켈레톤/쉬머 0건 — Home/Diary/Community/Gallery 전부 맨 스피너.
- **온보딩**: 강제 로그인 → 6화면 직렬, **스킵 전무**(`onSkipToTest`는 no-op 스텁, `AppNavHost.kt:157`). 코드 주석이 이미 "MBTI 단계 38%→15% 이탈"을 명시(`StarterSelectionScreen.kt:32`).
- **IA**: 바텀탭 4개(홈 탭 라벨이 "채팅"으로 오기, `Routes.kt:66-69`). 다이어리(2-3탭 깊이)·보이스콜(2탭, 홈 진입점 없음)이 핵심 정서 기능인데 매몰.
- **접근성**: `TextLight 0xFF9E9EAE` 저대비, 타임스탬프 alpha 0.6, 스트리밍 영역 liveRegion 없음.

### 1-C. 살아있는 캐릭터 (현황: WIRED/PARTIAL/ABSENT)

| 차원 | 상태 | 핵심 증거 |
|---|---|---|
| 감정→시각 (Canvas+Lottie) | **WIRED** | 10감정 눈/입/눈썹 프로시저럴 + 감정별 Lottie 배경 |
| 감정→시각 (DALL-E 이미지) | **죽은 파이프라인** | `startExpressionSetGeneration`(`ChatViewModel.kt:614`) **호출자 0건** → `expressionUrls` 항상 null → 15표정·깜빡임·립싱크 전부 미도달(`ImageCharacterFace.kt:38-46`) |
| 유휴 앰비언트 | WIRED(범용) | 호흡/부유/틸트/AGSL 헤어/터치반동(`LiveCharacter.kt:69-126`) — 단 전 캐릭터 동일, 개성 없음 |
| 립싱크 | **ABSENT(라이브 경로)** | Canvas 얼굴이 `isTalking` 미수신(`CharacterFaceCanvas.kt:81`); 립싱크는 죽은 이미지 경로에만 존재 |
| 선제 대화 | **PARTIAL** | 스케줄러 D3/D5/주간/야간일기 전부 **FCM 푸시만** — 채팅 스레드에 버블 삽입 없음. 인사는 빈 방 1회, 감정 하드코딩 NEUTRAL(`ChatViewModel.kt:603`) |
| 음성 | PARTIAL | TTS는 보이스콜 전용, speech_style 기반 pitch(감정 무반영, `VoiceCallViewModel.kt:93-101`), 채팅 미배선 |
| 기억/연속성 | **WIRED** | 요약/팩트/에피소드 + 스토리 콜백(`story_state_store.py:146`, 6턴 간격 미해결 훅 재언급) + 취향 미러링 |
| 타이핑 리듬 | WIRED | 서버 delay 계산 → 클라 소비 |
| mood | **죽은 파라미터** | 배관 완비(`chat_service.py:658-660,718`)나 라우터가 전달 안 함(`chat.py:366`) |
| 시간대 인지 | ABSENT | 야간일기 창(22-05시) 외에 프롬프트에 시간 정보 없음 — "좋은 아침" 불가 |
| Lottie 매핑 버그 | 확인됨 | `worried.json` 파일이 있는데 WORRIED가 `sad.json`으로 폴백, TOUCHED→`love.json`(`EmotionLottieBackground.kt:54-65`) |

---

## 2. 안전망 (항목 0)

**I-0. 브랜치 생성 + 기준선 재확인 — 1커밋 아님(작업 없음)**
```bash
git checkout -b improve/2026-07-perf-ux-character   # 보존 커밋(리팩토링 0-1) 이후 시점에서
cd server && python -m pytest tests/ -q             # 기준선 기록 (N₀)
cd ..\android && .\gradlew.bat compileDebugKotlin   # BUILD SUCCESSFUL
```
- 서버 라이브 스모크(성능 항목 검증에 필요): `docker-compose up -d`(PostgreSQL) 후 `cd server && uvicorn app.main:app --port 8090` 기동 성공 확인. `.env`에 `OPENAI_API_KEY` 없으면 mock 폴백으로 동작함(LLM 실호출 검증은 키 필요 — 없으면 해당 검증은 "키 부재로 생략"이라 보고).

공통 규칙: 1항목 = 1커밋, 커밋 메시지 `perf|feat|fix(<영역>): <항목ID> <요약>`. 실패 시 revert 후 보고.

---

## 3. 작업 항목 (실행 순서)

### Phase P — 서버 성능 (측정 먼저, 그다음 병목 제거)

**P1. TTFT·단계별 레이턴시 계측 추가 (최우선 — 측정 없이 튜닝 금지)**
- 문제: 첫 토큰까지의 시간(TTFT)과 단계별(게이트/메모리/RAG/프롬프트/LLM) 소요가 어디에도 기록되지 않음. 레이턴시는 A/B 활성 시에만 기록(`chat_service.py:1321`).
- 방법: `stream_reply`(`chat_service.py:1075~`)와 `generate_reply`에 `time.perf_counter()` 기반 단계 타이머를 추가 — 최소 4구간: `t_gate`(라우터에서 측정해 파라미터로 전달하거나 생략 가능), `t_memory`(build_memory_context), `t_rag`(rag_task 대기), `t_first_token`(LLM 호출~첫 청크). 스트림 종료 시 기존 `record_event` 채널로 `event_type="turn_latency"` 1건 기록(payload: 위 구간 ms + model + room_id). 로그(`logger.info`)에도 1줄 출력.
- 완료 기준: pytest N₀ 유지 + 신규 테스트 1개(`tests/test_turn_latency_event.py`: stream_reply를 test_stream_reply.py의 patch_deps 방식으로 목킹 실행 → record_event가 turn_latency로 호출되고 4구간 키가 존재함을 단언) + 로컬 uvicorn 기동 후 web_chat 또는 mock 채팅 1턴에서 로그 1줄 확인.
- 위험: 낮음(계측만). | 종속: I-0.

**P2. 핫패스 동기 DB 호출 제거 (이벤트 루프 블로킹 해소)**
- 문제: §1-A의 매 턴 동기 호출들이 커넥션 신규 생성 비용+루프 블로킹을 유발.
- 방법: `metrics_service.py`에 `record_event_async(...)`를 추가(기존 `record_event`와 동일 스키마, `postgres_async.get_async_db()` 사용, `$1` 플레이스홀더). 다음 async 컨텍스트 호출부를 교체:
  - `routers/chat.py:266`(chat_turn), `:458`, `:561` → `await record_event_async(...)`
  - `chat_service.py:933`, `:1278`(quality_gate_triggered) → async 버전
  - `quality_service.py:89`(quality_score) → async 버전
  - `quality_service.py:281`의 `check_diversity` → `fetchall`을 `asyncio.to_thread`로 감싸는 `check_diversity_async` 신설, `chat_service.py:1432` 호출부 교체 (기존 동기 `check_diversity`는 라우터 `quality.py`가 쓰므로 유지)
  - `subscription.py:110`의 `get_plan` 동기 fetchone → async 경로 추가(`get_plan_async`), `check_message_limit`(`:146`) 내부에서 그것을 사용
  - `story_state_store.py`의 `bump_turn_and_get_state`/`get_story_state`/`mark_callback_used` 호출부(`routers/chat.py:125,159,204`)는 함수 시그니처를 바꾸지 말고 **호출부를 `asyncio.to_thread(...)`로 감싼다**(테스트 `test_chat_turn_events_user_id.py`가 이 이름들을 monkeypatch하므로 이름/모듈 바인딩 유지 — to_thread 래핑이 patch와 호환되는지 해당 테스트 3개로 확인).
  - `ab_test.py:261` `record_result` 호출부(`chat_service.py:1393,1401`) → `asyncio.to_thread` 래핑.
- 완료 기준: pytest N₀ 유지(특히 `test_chat_turn_events_user_id.py`, `test_stream_reply.py`, `test_feedback_user_id.py`) + `grep -n "record_event(" server/app/routers/chat.py server/app/chat_service.py`에서 async 컨텍스트 내 동기 직호출 0건.
- 위험: 중간(이벤트 기록 누락 시 계측 왜곡). 실패 시 해당 호출부만 원복. | 종속: P1(turn_latency 이벤트도 async 버전 사용으로 정리).

**P3. `_gate_user` 병렬화 + 구독 플랜 캐시**
- 문제: `check_daily_budget`과 `check_message_limit`이 직렬(`chat.py:391-419`), 플랜 조회가 매 턴 DB 히트(`subscription.py:98-110`).
- 방법: ① 두 검사를 `asyncio.gather`로 동시 실행. ② `SubscriptionManager`에 uid→(plan, expires) 인메모리 TTL 캐시(60초, dict + monotonic 타임스탬프, 최대 1000엔트리 초과 시 전체 clear)를 추가하고 `get_plan_async`가 사용. 구독 변경 라우터(`routers/subscription.py`, `billing.py`)의 쓰기 성공 지점에서 해당 uid 캐시 무효화 1줄 추가.
- 완료 기준: pytest N₀ + 신규 테스트 1개(캐시 히트/무효화: fetch 호출 횟수를 카운팅 목으로 단언).
- 위험: 중간(결제 직후 60초 내 플랜 반영 지연 — 무효화 훅이 커버; 무효화 누락 경로 발견 시 보고). | 종속: P2.

**P4. async 풀 크기를 config 값으로**
- 문제: `AsyncDatabase.initialize`가 min=2/max=10 하드코딩(`postgres_async.py:64-68`), `config.py:35-36`(5/20) 무시.
- 방법: `from .config import DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE`로 교체. 리드 풀(`:426-430`)은 현행 유지.
- 완료 기준: pytest N₀ + uvicorn 기동 성공. | 위험: 낮음(로컬/운영 PG max_connections 확인 — 20+5+동기잔여가 상한 이내인지 확인 후 적용; 불확실하면 보고). | 종속: I-0.

**P5. 핫패스 인덱스 2종 추가**
- 문제: `api_usage.room_id` LIKE 프리픽스 스캔 매 턴 2회, `metric_events` 다양성 조회 복합 인덱스 부재.
- 방법: `postgres.py`의 `init_postgres_schema` DDL 리스트(190-626 부근, `api_usage`/`metric_events` 인덱스들 옆)에 추가:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_api_usage_room_id ON api_usage (room_id text_pattern_ops);
  CREATE INDEX IF NOT EXISTS idx_metric_events_type_room_created ON metric_events (event_type, room_id, created_at DESC);
  ```
  (`text_pattern_ops`는 LIKE 'x%' 최적화용 — 컬럼이 VARCHAR면 `varchar_pattern_ops`로. DDL 실행 오류 시 ops 지정자 없이 재시도하고 그 사실을 보고.)
- 완료 기준: docker-compose PG에서 uvicorn 기동(스키마 init) 성공 + `psql`로 `\d api_usage`에 인덱스 존재 확인(도커: `docker-compose exec db psql -U <user> -d <db> -c "\d api_usage"` — 접속정보는 docker-compose.yml에서 확인).
- 위험: 낮음(IF NOT EXISTS, 운영 반영 시 테이블 크면 CREATE INDEX CONCURRENTLY 권장 — 계획서에 보고만). | 종속: I-0.

**P6. TTFT 경로 병렬화: 메모리 컨텍스트와 RAG 동시 시작**
- 문제: `build_memory_context`(`chat_service.py:1131`)가 단독 직렬 → 그 후에야 RAG task 생성(`:1160`) → RAG 대기(`:1190`). 메모리와 RAG는 상호 의존 없음(호감도 task만 메모리 결과에 의존).
- 방법: `stream_reply`(와 `generate_reply` 동일 지점)에서 ① RAG `to_thread` task를 **함수 진입 직후**(히스토리 트림 다음)에 먼저 생성, ② `build_memory_context`를 task로 만들어 RAG와 동시 진행, ③ 호감도 task는 기존대로 메모리 컨텍스트 완료 후 생성(의존성 유지), ④ 프롬프트 조립 직전에 두 task를 await. 예외 시 기존과 동일한 폴백(빈 컨텍스트/빈 RAG) 유지.
- 완료 기준: pytest N₀(특히 `test_stream_reply.py` 9개, `test_memory_extraction.py`) + P1 계측으로 t_memory와 t_rag가 겹치는지 로그 확인(합계 < 직렬 합).
- 위험: 중간~높음(태스크 수명/예외 처리 — 함수 예외 시 생성한 task cancel 누락 주의, 기존 예외 정리 블록에 추가). | 종속: P1, P2. **리팩토링 S11~S14가 완료된 뒤라면 헬퍼 구조 위에서 작업(더 쉬움).**

**P7. 스트림 경로 정합: `api_usage` 기록 + 서킷브레이커**
- 문제: ① 스트림 턴이 `api_usage` 미기록 → `_gate_user` 예산/한도가 SSE를 과소계상(사실상 무제한), 비용 통계 왜곡. ② 스트림 메인 LLM 호출(`chat_service.py:1244`)이 서킷브레이커 미보호.
- 방법: ① `stream_options.include_usage`(이미 요청 중, `:1239`)의 마지막 청크에서 usage를 캡처해 스트림 종료 시 `create_tracked_task(_record_usage(...))` 호출(generate_reply의 `:1018`과 동일 패턴, endpoint="stream"). ② `client.chat.completions.create(...)` await를 `get_openai_circuit().call(...)`로 래핑(generate_reply `:894`와 동일 — 스트림 객체 반환이므로 create 호출 자체만 래핑).
- 완료 기준: pytest N₀ + `test_stream_reply.py`에 usage 기록 단언 테스트 1개 추가(patch_deps의 가짜 스트림에 usage 청크 포함시켜 `_record_usage` 호출 확인).
- 위험: 중간. **주의**: 이 변경으로 SSE 사용자도 일일 예산/한도에 걸리기 시작함 — **의도된 동작 변경**이며 사용자(소유자)에게 롤아웃 시점 보고 필요. | 종속: P2.

**P8. `_persist_chat_data` 3회 왕복 → 단일 트랜잭션/배치**
- 문제: users upsert + 메시지 INSERT 2건이 각각 풀 획득(`chat.py:303-341`).
- 방법: `postgres_async.AsyncDatabase`에 이미 있는 커넥션 획득 패턴을 사용해 한 커넥션에서 3문장 실행(간단한 `execute_many` 또는 acquire 후 순차 실행). 실패 시 문장별 독립 로깅 유지(현재 각 INSERT가 개별 try/except — 그 견고성 보존: 트랜잭션으로 묶지 말고 **한 커넥션 재사용**만 해도 충분).
- 완료 기준: pytest N₀. | 위험: 낮음~중간. | 종속: P2.

### Phase C — 살아있는 캐릭터 (효과 큰 순서, 빠른 배선부터)

**C1. Lottie 감정 매핑 수정 (5분짜리 확실한 개선)**
- 문제: `worried.json`이 assets에 존재하는데 WORRIED가 `sad.json`으로 폴백, TOUCHED는 `love.json` 재사용(`EmotionLottieBackground.kt:54-65`).
- 방법: 매핑에서 WORRIED→`worried.json`으로 수정. TOUCHED는 전용 파일이 없으므로 `love.json` 유지(변경 없음 — 확인만).
- 완료 기준: compileDebugKotlin OK + 수동 QA: 채팅에서 WORRIED 감정 응답 시 배경이 sad와 다른지 확인(서버 mock으로 유발 가능).
- 위험: 없음. | 종속: I-0.

**C2. 첫인사에 감정 부여 (첫인상 무표정 해소)**
- 문제: `send_greeting`(`routers/chat.py:798`) 응답에 감정 없음 → 클라가 NEUTRAL 하드코딩(`ChatViewModel.kt:603`).
- 방법(서버): greeting 응답 JSON에 `emotion` 필드 **추가**(additive — 기존 클라 호환). 값은 MBTI 고정 매핑: ENFP/ESFP/ESTP/ENTP→PLAYFUL, ENFJ/ESFJ/ENTJ/ESTJ→HAPPY, INFP/ISFP/INFJ/ISFJ→SHY, INTJ/INTP/ISTJ/ISTP→NEUTRAL.
  방법(클라): `GreetingResponse`(ChatApi DTO)에 `emotion: String?` 추가, `sendInitialGreeting`(`ChatViewModel.kt:593-606`)에서 `runCatching { CharacterEmotion.valueOf(it) }.getOrDefault(NEUTRAL)`로 반영(저장 메시지와 `currentEmotion` 모두).
- 완료 기준: 서버 pytest N₀ + 신규 테스트 1개(greeting 응답에 emotion 포함, MBTI 2종 값 검증) + compileDebugKotlin OK + 수동 QA: 새 캐릭터 생성 직후 채팅 진입 시 캐릭터 표정이 MBTI에 맞게 뜨는지.
- 위험: 낮음(additive 필드). | 종속: I-0.

**C3. Canvas 얼굴 립싱크 (isTalking → 입 모양)**
- 문제: 라이브 경로(프로시저럴 얼굴)가 `isTalking`을 받지 않아 응답 생성 중에도 입이 감정 고정(`CharacterFaceCanvas.kt:81`). 립싱크 코드는 죽은 이미지 경로에만 존재(`ImageCharacterFace.kt:75-85`).
- 방법: `CharacterFace`/`drawCharacterFace`에 `isTalking: Boolean = false` 파라미터 추가(기본값으로 기존 호출부 호환). `ImageCharacterFace`와 동일한 120ms 주기로 mouthPhase(0/1/2)를 순환하는 `rememberInfiniteTransition` 또는 LaunchedEffect 타이머를 두고, isTalking일 때 감정 입 대신 open/half/closed 3프레임을 그리는 `drawTalkingMouth`를 추가(기존 `drawMouth`(:686) 옆, 감정별 입 색/스타일 유지). isTalking 종료 시 감정 입으로 복귀. `ChatScreen.kt`의 `CharacterAnimationArea`(:582-588)에서 `viewModel.isTalking` 전달.
- 완료 기준: compileDebugKotlin OK + 수동 QA: 메시지 전송 → 응답 생성 동안 입이 움직이고, 완료 후 감정 표정으로 복귀.
- 위험: 중간(Canvas 그리기 — 시각 확인 필수). | 종속: I-0.

**C4. 시간대 인지 프롬프트 (프리픽스 캐시 안전 위치에)**
- 문제: 캐릭터가 현재 시간을 모름 — "좋은 아침" 불가(`prompts.py`에 시간 블록 없음).
- 방법: `ChatRequest`에 이미 있는 `client_local_hour`(야간 창 판정에 사용 중, `chat.py:94-97`)를 활용. `build_system_prompt`에 `time_context: str = ""` 파라미터를 추가하고 **동적 꼬리(`prompts.py:1168-1169`의 summary/memory 옆)**에만 삽입 — 정적 프리픽스(:1124-1166)에 넣으면 캐시 파괴이므로 절대 금지. 라우터에서 hour→구간 매핑(05-10 아침 / 11-16 낮 / 17-21 저녁 / 22-04 밤) 문자열 생성 후 전달, hour가 None이면 빈 문자열(현행 동일). 내용 예: `"[현재 시간대: 아침이다. 자연스럽게 반영하되 매번 언급하지는 마라.]"`.
- 완료 기준: pytest에서 **의도된 실패/갱신**: `test_prompts_golden.py`(존재 시) 골든 3종 재생성 + 신규 테스트 1개(hour=8 → 프롬프트에 "아침" 포함, hour=None → 시간 블록 없음, 그리고 **시간 블록이 정적 프리픽스 뒤에 위치**함을 인덱스 비교로 단언). 그 외 테스트 N₀ 유지.
- 위험: 중간(프리픽스 캐시 — 위치 단언 테스트가 방어). | 종속: I-0. 리팩토링 0-3(b) 이후라면 골든 갱신 필수 명기.

**C5. DALL-E 표정 세트 파이프라인 부활 (죽은 기능 배선)**
- 문제: 서버 15표정 생성(`image_service.py:179`)과 클라 소비(`ImageCharacterFace`의 깜빡임/립싱크/감정 이미지 스왑)가 완비돼 있으나 **트리거 `startExpressionSetGeneration`(`ChatViewModel.kt:614`) 호출자 0건** → 전부 미도달.
- 방법: ① `ImageGeneratorSheet.kt`(:154 부근)에서 `img:` 캐릭터 생성 성공 직후 표정 세트 생성을 시작하도록 배선(캐릭터 저장 완료 콜백에서 `ExpressionManager` 경유 taskId 저장 → 기존 폴링(`ExpressionManager.kt:96-126`)이 이어받음). ② 채팅 진입 시 `loadExistingExpressionSet`이 taskId 저장분을 로드하는 기존 경로(`:48-59`) 동작 확인. ③ **비용 가드**: 표정 세트는 DALL-E 15장 = 캐릭터당 유의미한 비용 — 자동 생성이 아니라 ImageGeneratorSheet에 "표정 세트 만들기(선택)" 명시 버튼으로 넣고, 서버측 기존 레이트 리밋/구독 게이트가 이 엔드포인트에 걸려 있는지 확인(`routers/image.py`) — 게이트 없으면 **구현하지 말고 보고**(비용 사고 방지).
- 완료 기준: compileDebugKotlin OK + 수동 QA(OPENAI 키 있는 환경): img 캐릭터 생성 → 버튼 → 폴링 완료 후 채팅에서 감정별 이미지 전환+깜빡임+립싱크 확인. 키 없으면 "생성 요청→taskId 저장→폴링 시작"까지를 목/로그로 확인하고 잔여는 보고.
- 위험: 중간~높음(비용·비동기 폴링). | 종속: C3(립싱크 UX 일관성), I-0.

**C6. 선제 메시지를 채팅 스레드에 삽입 (푸시 → 대화)**
- 문제: D3/D5 등 그리움 메시지가 시스템 알림으로만 옴 — 캐릭터가 "먼저 말 건" 경험이 대화방에 남지 않음.
- 방법: ① **선행 조사**: 서버 스케줄러가 보내는 FCM payload(`firebase_service.send_notification_with_record`)와 클라 `ChatFirebaseMessagingService.onMessageReceived`(`:35`)의 `notification_type` 라우팅, 그리고 서버 room_id ↔ 클라 로컬 roomId 매핑 규칙을 확인해 문서화(형식이 안 맞으면 중단·보고). ② 서버: D3/D5 잡의 FCM에 data 필드 추가 — `room_id`, `character_id`, `message`(이미 생성 중인 그리움 문구), `emotion`(D5는 MBTI 매핑 재사용). ③ 클라: `onMessageReceived`에서 해당 타입이면 알림 표시에 **더해** `MessageDao`로 캐릭터 발화 MessageEntity를 로컬 방에 INSERT(기존 스키마 사용 — **Room 마이그레이션 금지**, 필드 부족하면 중단·보고). 중복 방지: data에 `push_id`를 넣고 동일 push_id 기수신 시 skip(SharedPreferences 최근 50개).
- 완료 기준: 서버 pytest N₀(스케줄러 테스트 `test_scheduler_jobs.py` 12개 — data 필드 추가로 깨지면 해당 테스트의 기대 payload만 갱신 허용·명기) + compileDebugKotlin OK + 수동 QA: FCM 테스트 메시지(Firebase console 또는 로컬 스텁)로 채팅방에 버블 삽입 확인.
- 위험: 높음(푸시 계약·중복·매핑). ①에서 매핑 불일치 발견 시 즉시 중단·보고가 안전선. | 종속: C2(emotion 매핑 재사용), P계열과 무관.

**C7. MBTI별 유휴 개성 파라미터**
- 문제: 호흡/부유/틸트가 전 캐릭터 동일(`LiveCharacter.kt:69-99`) — E/I·에너지 차이가 없음.
- 방법: `LiveCharacter`에 `motionProfile` 파라미터(data class: breathScale, floatAmpDp, tiltDeg, speedFactor) 추가, 기본값 = 현행 수치(기존 동작 보존). MBTI→프로파일 매핑 함수 1개(E군: 진폭·속도 +20%, I군: -15%, 판단형 J: 틸트 -30% 등 — 매핑 테이블을 코드에 상수로) 를 `ChatScreen`에서 캐릭터 MBTI로 적용.
- 완료 기준: compileDebugKotlin OK + 수동 QA: ENFP vs ISTJ 캐릭터 방을 오가며 움직임 차이 체감 확인.
- 위험: 낮음(기본값 보존). | 종속: I-0.

### Phase U — UI/UX·디자인 (토큰 먼저, 그 위에 화면 개선)

**U1. 디자인 토큰 3종 신설 + MaterialTheme shapes 배선**
- 문제: spacing/shape/elevation/motion 토큰 전무(§1-B), `MaterialTheme(...)`에 shapes 미전달(`Theme.kt:74-78`).
- 방법: `ui/theme/`에 추가 —
  - `Dimens.kt`: `object Spacing { val xs=4.dp; val sm=8.dp; val md=12.dp; val lg=16.dp; val xl=24.dp; val xxl=32.dp }`
  - `Shape.kt`: `val AppShapes = Shapes(extraSmall=RoundedCornerShape(4.dp), small=RoundedCornerShape(12.dp), medium=RoundedCornerShape(16.dp), large=RoundedCornerShape(20.dp), extraLarge=RoundedCornerShape(24.dp))` → `Theme.kt`의 `MaterialTheme(colorScheme, typography)`에 `shapes = AppShapes` 추가
  - `Motion.kt`: `object MotionDurations { const val Short=300; const val Medium=400 }`
  - 이 항목에서는 **토큰 정의와 배선만** — 기존 리터럴의 일괄 치환은 하지 않는다(치환은 U2 이후 각 항목이 손대는 파일에서만 점진 적용).
- 완료 기준: compileDebugKotlin OK(시각 변화 0 — Shapes 기본값을 쓰던 컴포넌트가 있으면 모양이 바뀔 수 있으므로, 배선 후 홈/채팅/설정 화면 수동 확인해 의도치 않은 변화 발견 시 해당 컴포넌트에 명시적 shape을 지정해 현상 유지).
- 위험: 낮음~중간(Shapes 배선 부작용 — 수동 확인으로 방어). | 종속: I-0.

**U2. 다크모드 파손 수정 (채팅 무대 + 감사 카드)**
- 문제: `ChatScreen.kt:557-566` 호감도 그라데이션이 라이트 파스텔 하드코딩(다크에서 밝은 핑크 워시), `GratitudeCardSection.kt:45-47` 라이트 전용.
- 방법: 감정 버블의 모범 패턴(라이트/다크 쌍 토큰 + isDark 분기, `Color.kt:46-65` 방식)을 그대로 따라 `Color.kt`에 다크 변형 토큰 추가(예: `AffinityBgLv1Dark = 0xFF2A2230` 계열 — 채도 낮춘 어두운 대응색, 정확한 값은 기존 `DarkSurface(:20-22)` 계열과 어울리게 선정) 후 두 지점에 `isSystemInDarkTheme()` 분기 적용. **홈 시즌 배너 ~15종의 일괄 수정은 백로그**(리팩토링 A7/배너 통합 이후가 효율적).
- 완료 기준: compileDebugKotlin OK + 수동 QA: 설정에서 다크모드 전환 → 채팅 화면 상단 무대와 홈 감사 카드가 어둡게 조화되는지 스크린샷 비교.
- 위험: 낮음. | 종속: U1.

**U3. 채팅 핵심 UX 3종 수정**
- 문제/방법:
  1. **자동 스크롤 강제**(`ChatScreen.kt:143-147`): `derivedStateOf`로 "사용자가 하단 근처(마지막-1 아이템 가시)" 여부를 계산해, 하단에 있을 때 또는 방금 내가 보낸 메시지일 때만 `animateScrollToItem`. 위로 스크롤 중이면 스킵(선택: "새 메시지 ↓" 스낵/칩 표시는 백로그).
  2. **피드백 썸 28dp**(`:841,861`): `IconButton` 터치 영역을 48.dp로(아이콘 시각 크기는 20~24dp 유지 — `Modifier.size(48.dp)` + 내부 `Icon(Modifier.size(22.dp))`). 재전송 필도 `heightIn(min=32.dp)`+패딩 확대.
  3. **롱프레스 메뉴에 복사 추가**: 현재 롱프레스=공유 다이얼로그 직행(`:655-658,799-802`). `DropdownMenu`로 "복사 / 공유" 2항목 메뉴로 변경, 복사는 `ClipboardManager`(LocalClipboardManager) 사용.
- 완료 기준: compileDebugKotlin OK + 수동 QA 3건(위로 스크롤 중 응답 수신 시 안 끌려감 / 썸 터치 쉬움 / 롱프레스→복사 동작).
- 위험: 중간(스크롤 로직 — 수동 QA 필수). | 종속: U1.

**U4. 스켈레톤 로딩 도입 (Home·Diary·Community)**
- 문제: 전 화면 맨 스피너(쉬머/스켈레톤 0건).
- 방법: 외부 라이브러리 **추가 금지** — `ui/components/SkeletonBox.kt` 자체 구현(둥근 사각 + `rememberInfiniteTransition` alpha 0.3↔0.7 펄스, U1 토큰 사용). Home 로딩(`HomeScreen.kt:104-110`)을 캐릭터 카드 3개 스켈레톤으로, Diary(`DiaryScreen.kt:243`)와 Community(`CommunityScreen.kt:102-106`)를 각각 카드형 스켈레톤 2-3개로 교체. Gallery는 백로그.
- 완료 기준: compileDebugKotlin OK + 수동 QA: 각 화면 진입 시 스피너 대신 스켈레톤(네트워크 지연 시뮬레이션: 비행기 모드 or 서버 미기동).
- 위험: 낮음. | 종속: U1.

**U5. 온보딩 스킵 경로 (민감 정보 선택화)**
- 문제: 강제 로그인 후 6화면 무스킵, 성별/나이 필수 — 코드 주석이 38%→15% 이탈 명시.
- 방법: **로그인/닉네임/MBTI 선택은 유지**(핵심 기능 필수), **성별·나이 2화면에 "건너뛰기" 텍스트 버튼 추가** — `OnboardingScaffold`(:110-113)에 optional `onSkip: (() -> Unit)?` 파라미터를 추가하고 null이면 미표시(다른 화면 무영향). 스킵 시 해당 값은 기존 "미설정" 표현으로 저장(OnboardingViewModel의 현재 기본값/nullable 처리 확인 — 서버 전송 스키마가 필수라면 기존 기본값 사용, 확인 후 결정. 서버 스키마 변경 금지). `onSkipToTest` no-op 스텁(`AppNavHost.kt:157`)은 이 항목과 무관 — 건드리지 않음.
- 완료 기준: compileDebugKotlin OK + 수동 QA: 신규 계정 온보딩에서 성별/나이 스킵 → 홈 도달 + 채팅 정상.
- 위험: 중간(온보딩 데이터 하위 스키마 — ViewModel 기본값 확인 선행). | 종속: I-0.

**U6. IA 소정비: 탭 라벨 + 다이어리/보이스콜 노출**
- 문제: 홈 탭 라벨 "채팅" 오기(`Routes.kt:66-69`), 다이어리 2-3탭·보이스콜 홈 진입점 없음.
- 방법: ① 홈 탭 라벨을 "홈"으로. ② `HomeScreen`의 `CharacterCard`에 아이콘 2개(일기·통화) 추가 또는 카드 롱프레스 메뉴 — **최소 변경으로 카드 우측에 작은 아이콘 버튼 2개**(다이어리는 기존 `Route.Diary` 네비게이션 재사용(`AppNavHost.kt:276-278` 참고), 보이스콜은 `Route.VoiceCall`). 터치타겟 48dp 준수(U3와 동일 패턴).
- 완료 기준: compileDebugKotlin OK + 수동 QA: 홈에서 1탭으로 일기/통화 진입.
- 위험: 낮음. | 종속: U3(터치타겟 패턴).

**U7. 감정 표현 모션 2종: 호감도 게이지 애니메이션 + 홈 리스트 등장**
- 문제: 호감도 증가가 무음(프로그레스 스냅, `ChatScreen.kt:271-280`), 홈 리스트 등장 모션 없음.
- 방법: ① `LinearProgressIndicator`의 progress를 `animateFloatAsState(tween(MotionDurations.Medium))`로 래핑 — 델타 발생 시 부드럽게 참. ② 홈 `LazyColumn` 캐릭터 아이템에 `AnimatedVisibility(fadeIn+slideInVertically)` 또는 `Modifier.animateItemPlacement()` 적용(최초 로드 시 순차 등장은 과하면 생략 — 배치 애니메이션만).
- 완료 기준: compileDebugKotlin OK + 수동 QA: 채팅에서 호감도 오르면 게이지가 스르륵 참.
- 위험: 낮음. | 종속: U1(Motion 토큰).

**U8. 접근성 필수 3종**
- 문제: 저대비 텍스트, 스트리밍 liveRegion 없음, 장식 아닌 아이콘 contentDescription 누락.
- 방법: ① `Color.kt:27`의 `TextLight`를 대비 4.5:1 이상으로 어둡게 조정(예: `0xFF6E6E80` — 실제 값은 배경 `CreamWhite` 대비 검증: https 도구 없이도 상대휘도 계산으로, 판단 어려우면 `0xFF6E6E80` 채택) — 타임스탬프 alpha 0.6은 0.75로. ② 채팅 메시지 리스트 컨테이너에 `Modifier.semantics { liveRegion = LiveRegionMode.Polite }`. ③ `ChatScreen.kt:916`(타이핑 아바타), `:259`(메뉴 아이콘) 등 상호작용 아이콘에 한국어 contentDescription 부여(장식용은 null 유지).
- 완료 기준: compileDebugKotlin OK + 수동 QA: 다크/라이트 모두에서 타임스탬프·힌트 가독 확인, TalkBack으로 새 응답 낭독 확인(에뮬레이터).
- 위험: 낮음(색 변화는 시각 확인). | 종속: U1.

**U9. `emotionEmoji` ASCII 텍스트 교체**
- 문제: `^^`, `//`, `<3`, `:P`, `T_T`(`ChatScreen.kt:1061-1072`)가 폴백 얼굴·탑바 서브타이틀에 노출 — 정서 앱에 걸맞지 않음.
- 방법: 10감정 → 유니코드 이모지 매핑으로 교체(NEUTRAL 🙂 HAPPY 😊 SHY 😳 SAD 😢 ANGRY 😠 SURPRISED 😲 LOVE 🥰 PLAYFUL 😜 WORRIED 😟 TOUCHED 🥹). 이모지 렌더링 실패 기기 고려해 폰트 폴백 확인(에뮬레이터 API 28에서 표시 확인 — 🥹는 API 낮으면 두부(□) 위험 → TOUCHED는 🥺로).
- 완료 기준: compileDebugKotlin OK + 수동 QA(API 28 에뮬레이터 포함).
- 위험: 낮음. | 종속: I-0.

### 실행 순서 전방 추적 검증 (제출 전 확인 완료)
I-0 → P1→P2→P3→P4→P5→P6→P7→P8 → C1→C2→C3→C4→C5→C6→C7 → U1→U2→U3→U4→U5→U6→U7→U8→U9
- P1(계측)이 P6(병렬화)의 효과 검증 수단을 먼저 제공 ✓
- P2(async record_event)가 P1의 turn_latency 기록 방식과 정합(P1에서 만든 기록도 P2에서 async로 전환) ✓
- C2의 MBTI→감정 매핑을 C6가 재사용 ✓ / C3(립싱크)이 C5(이미지 얼굴)와 UX 일관 ✓
- U1(토큰)이 U2/U3/U4/U7/U8의 기반 ✓ / U3의 48dp 패턴을 U6가 재사용 ✓
- C4는 골든 테스트 갱신을 완료 기준에 포함(유일 허용) ✓ / C6는 스케줄러 테스트 payload 갱신 허용 명기 ✓

---

## 4. 하지 말아야 할 것

1. **의존성 추가/업데이트 금지**: 쉬머 라이브러리, psycopg_pool, 코일 교체 등 일절 금지 — U4는 자체 구현으로 명시했다.
2. **Room 스키마·마이그레이션 변경 금지**(v8 유지). C6에서 기존 MessageEntity 필드로 부족하면 중단·보고.
3. **API 계약 파괴 금지**: 기존 필드 제거/의미 변경 금지. 추가는 additive만(C2 emotion, C6 FCM data 필드 — 계획에 명시된 것만).
4. **모델 변경 금지**: gpt-4.1/gpt-4.1-mini 유지, gpt-4o 금지. 임베딩 모델(text-embedding-3-small) 교체 금지(로컬 임베딩 전환은 백로그).
5. **프리픽스 캐시 정적 블록(`prompts.py:1124-1166`)에 동적 값 삽입 절대 금지** — C4 포함 모든 프롬프트 추가는 동적 꼬리에만.
6. **명시되지 않은 테스트 수정 금지**(허용: C4 골든 재생성, C6 스케줄러 payload, P7 스트림 테스트 추가). 깨지면 중단·보고.
7. **비용 가드 없는 DALL-E 자동 생성 금지**(C5 ③ — 게이트 부재 시 구현 중단).
8. **리팩토링 계획의 금지 목록 승계**: 휴면 세션 피드백 3파일 삭제 금지, `evaluate.py`/`tools/lora_pipeline.py` 불가침, 전체 리포맷 금지, 시즌 배너 15종 일괄 수정 금지(백로그).
9. **운영 DB에 인덱스 직접 적용 금지**(P5는 스키마 init DDL 추가까지 — 운영 반영은 소유자가 CONCURRENTLY로).
10. **P7의 SSE 예산 게이트 활성화는 동작 변경** — 배포 전 소유자 확인 없이 운영 반영 금지(코드 머지는 가능).

### 백로그 (이번 범위 외, 소유자 결정 필요)
- TTS 채팅 낭독(감정 pitch 변조) / 게스트(로그인 전) 체험 모드 / 홈 히어로 캐릭터(대형 LiveCharacter) + 홈→채팅 shared-element 전환 / 시즌 배너 15종 데이터 드리븐 통합 + 다크모드 / strings.xml 외부화 / Gallery 스켈레톤 / 로컬 임베딩으로 RAG TTFT 제거 / `mood` 파라미터: 배선(사용자 최근 감정 추정 전달) 또는 제거 — **소유자 결정 항목** / 스토리 콜백의 Postgres 의존(오프라인 시 무음 저하, `story_state_store.py:89-102`) 폴백 / SlowAPI 레이트리밋 X-Forwarded-For 키 정합(nginx 뒤 IP 뭉침).

---

## 5. 실행자를 위한 지침 (복사해 전달)

```
[작업 규칙]
1. docs/IMPROVEMENT_PLAN_2026-07-08_perf_ux_character.md의 항목을 I-0부터 순서대로, 한 번에 하나씩 실행한다.
2. 시작 전 확인: REFACTORING_PLAN_2026-07-07.md의 0-1(보존 커밋)이 git log에 존재하는지. 없으면 그것부터.
3. 1항목 = 1커밋. 메시지: "perf|feat|fix(<영역>): <항목ID> <요약>".
4. 검증: 서버 항목마다 cd server && python -m pytest tests/ -q (기준선 유지, 항목이 명시한 테스트 추가/갱신만 예외).
   Android 항목마다 cd android && .\gradlew.bat compileDebugKotlin. 수동 QA가 명시된 항목은 에뮬레이터로 해당 시나리오를 실행하고 결과(스크린샷 가능하면 포함)를 보고에 남긴다.
5. 완료 기준 미충족 시 해당 항목 revert 후 중단·보고. 테스트를 고쳐서 통과시키지 않는다(명시 허용 3건 제외).
6. 줄 번호는 2026-07-08 기준 — 심볼 이름으로 재확인. 크게 어긋나면 중단·보고.
7. "하지 말아야 할 것" 10개 조항을 매 항목 전 재확인. 특히: 의존성 추가 금지, 프리픽스 캐시 정적 블록 불가침, DALL-E 비용 가드.
8. OPENAI_API_KEY가 없는 환경에서는 LLM 실호출 검증 단계를 "키 부재로 생략"이라 명시하고 목/로그 검증으로 대체한다.
9. 전 항목 후 최종 회귀: pytest + compileDebugKotlin + uvicorn 기동 스모크 + 채팅 1턴 수동 QA. P1 계측 로그로 개선 전후 TTFT 구간 수치를 기록해 보고한다.
```

---

*작성: Claude (2026-07-08). 조사: 병렬 탐색 에이전트 3개(서버 성능 크리티컬 패스 추적 / Android UI·UX·디자인 시스템 / 살아있는 캐릭터 역량 인벤토리). 주요 판정 근거는 각 항목에 file:line으로 인용. 자매 문서: docs/REFACTORING_PLAN_2026-07-07.md (동작 보존 리팩토링, 선행 권장).*
