# MBTIChatFriend 리팩토링 계획서 (2026-07-07)

> **실행자 전제**: 이 문서와 코드 외에 컨텍스트 없음. 모든 줄 번호는 **항목 0 커밋 시점의 작업 트리 기준**이며, 이전 항목 실행 후에는 줄이 밀리므로 **반드시 심볼 이름(함수/클래스명)으로 위치를 재확인**할 것.

---

## 1. 현재 이해 (구조 맵)

**제품**: MBTI 16유형 AI 채팅 친구 앱. Android(Kotlin/Compose) 클라이언트 + FastAPI 서버 모노레포.

**서버 요청 흐름** (핵심 파이프라인):

```
routers/chat.py  POST /chat/send   → _run_chat_pipeline → chat_service.generate_reply → _finalize_chat_turn
                 POST /chat/stream → (OpenAI 경로) chat_service.stream_reply(SSE) → _finalize_chat_turn
                                     (LoRA 경로)  _run_chat_pipeline + stream_lora_response
```

- `chat_service.py`(1979줄): LLM 호출, 호감도 병렬 분석, 품질 게이트 재생성, RAG 병합, 일기 생성, `IncrementalReplyParser`. **최대 함수**: `generate_reply`(702–1065, ~364줄) ↔ `stream_reply`(1075–1337, ~263줄) — 서로 거의 미러 구조로 13곳 이상 중복.
- `prompts.py`(1193줄): MBTI 페르소나 텍스트 + `build_system_prompt`(991–1193, ~203줄). `finetune_service`, `routers/chat`, 테스트가 임포트하는 **하드 계약**.
- `routers/chat.py`(835줄): `_finalize_chat_turn`(139–360, ~222줄, 중첩 async 함수 2개 포함), `stream_message`(475–674, ~200줄, 이벤트 제너레이터 2벌 내장).
- DB 이중 레이어: `postgres.py`(sync psycopg, `%s`) + `postgres_async.py`(async, `$1`→`%s` 변환기). **`postgres.py`의 async 절반은 데드** — `main.py:51-56`이 자체 `init_async_pool`을 정의해 `postgres_async`만 사용.
- 기타 서비스(quality/memory/scheduler/subscription/ab_test 등)는 `main.py`의 라우터 등록을 통해 전부 살아있음. 단 `routers/subscriptions.py`(복수형), `app/compatibility.py`, `scripts/insert_community_seeds.py`는 **미배선 데드**.

**Android**: MVVM + Repository, Hilt DI, Room v8(마이그레이션 7개, `exportSchema=true`), Retrofit+SSE. 단일 모듈 `:app`, Gradle 8.9.

- `ChatApi.kt`(672줄): Retrofit 인터페이스 1개 + **DTO 55개**가 한 파일에 집적.
- `ChatScreen.kt`(1110줄): `ChatScreen` 컴포저블 415줄(다이얼로그 4개 인라인), `MessageBubble` 262줄(유저/AI 렌더 경로 혼재).
- `HomeScreen.kt`(831줄), `SettingsScreen.kt`(691줄)도 동일 패턴. 호감도 레벨명/색상 `when` 블록이 4곳+2곳 중복.
- `res/values/strings.xml`에는 `app_name` 1개뿐 — UI 문자열 100% 하드코딩(이번 계획 범위 외, 백로그).

**테스트 현황**: 서버 `pytest` 20파일 203함수 → Windows 실측 **177 passed, 2 skipped(~10초)**. ChromaDB 스위트 2파일은 Windows에서 자동 스킵(`RUN_CHROMA_TESTS=1`로 활성화). Android는 템플릿 스텁 2개뿐(실질 0). `server/tests/chat_quality_test.py`는 pytest가 수집하지 않는 **수동 스크립트**(라이브 서버 필요).

**git 상태 (중요)**: 브랜치 `chore/remove-orphan-routers`에 2026-07-02 스프린트 구현(P0 5건 + 개인화 + Android 계측, 서버 16파일 + Android 10파일 + 신규 테스트 5파일)이 **미커밋 상태로 존재**. 이 작업 트리가 177 GREEN의 기준이므로 절대 버리면 안 됨 → 항목 0-1에서 최우선 커밋.

---

## 2. 항목 0: 안전망 구축 (다른 어떤 항목보다 먼저)

### 0-1. 미커밋 스프린트 작업 커밋 + 리팩터 브랜치 생성

```bash
cd C:\Users\kci01\Projects\MBTIChatFriend
git status --short          # 변경 목록 확인 (서버/Android 수정 + 신규 테스트/문서)
git add -A
git status --short          # 스테이징 확인: 빌드 산출물/캐시(.pytest_cache 등)가 포함됐으면 unstage 후 .gitignore 추가
git commit -m "feat: 2026-07-02 챗봇 품질 회의 구현 (P0 5건 + 개인화 미러링 + Android 계측/피드백, Room v8)"
git checkout -b refactor/2026-07-structure
```

- **완료 기준**: `git status` clean, 새 브랜치 생성됨.
- **주의**: 이 커밋은 리팩토링이 아니라 기존 기능 작업의 보존임. 절대 내용을 수정하지 말고 있는 그대로 커밋.

### 0-2. 기준선 기록

```bash
cd server && python -m pytest tests/ -q     # 예상: 177 passed, 2 skipped
cd ..\android && .\gradlew.bat compileDebugKotlin   # 예상: BUILD SUCCESSFUL
```

- 두 결과를 기록해 둔다. 이후 모든 항목의 회귀 기준.

### 0-3. 특성화(characterization) 테스트 추가 — 1커밋

이후 항목이 건드릴 미커버 동작을 고정한다. **기존 테스트의 목킹 스타일(`tests/test_stream_reply.py`의 `patch_deps` 픽스처)을 그대로 모방**할 것.

**(a) `tests/test_generate_reply_characterization.py`** — `generate_reply`는 직접 테스트가 없음(stream만 있음). 다음 4개:

1. **정상 경로**: `chat_service.client`를 가짜 AsyncOpenAI로 패치(응답 content = `'[{"text": "안녕!", "emotion": "HAPPY"}]'`), `analyze_affinity_with_llm`→고정값 3, `_rag_search_sync`→`([], [])`, `build_memory_context` 계열→빈값, `quick_score`→1.0, `check_content`→허용. `generate_reply(message="안녕", mbti="INFP", speech_style="반말", relationship="친구", nickname="테스트", affinity_level=2, conversation_history=[])` 호출 → 반환 `(parts, delta)`에서 `parts[0].text == "안녕!"`, `parts[0].emotion == "HAPPY"`, `delta == 3` 단언.
2. **클라이언트 없음 폴백**: `chat_service.client = None` 패치 → 반환 리스트 비어있지 않고 delta가 int임을 단언(`_mock_reply` 경로).
3. **입력 차단 경로**: 먼저 `chat_service.py:741-747`을 읽고 `check_content` 차단 시의 실제 반환(거절 문구, delta)을 확인한 뒤 **관측된 값 그대로** 단언으로 고정.
4. **품질 게이트 재생성**: `quick_score`가 1차 호출 0.2, 2차 호출 0.9를 반환하도록 패치(호출 카운터 사용) → LLM 클라이언트가 2회 호출되고 최종 응답이 2차 응답임을 단언(`chat_service.py:928-992`의 현재 동작 고정).

**(b) `tests/test_prompts_golden.py`** — `build_system_prompt` 골든 테스트 3개. 입력 조합: ① (mbti="INFP", affinity_level=1, 기억/요약 없음) ② (mbti="ENTJ", affinity_level=5, memories+summary+episode+user_mbti 채움) ③ (mbti="ISTP", affinity_level=3, preference_context 지정). 작성 방법: 테스트를 먼저 `print(result)`로 실행해 현재 출력 전문을 얻고, 그 문자열을 테스트 파일 내 트리플쿼트 상수로 고정 → `assert build_system_prompt(...) == EXPECTED_①` (전체 문자열 완전 일치).

**(c) `tests/test_mbti_group_equivalence.py`** — 16개 유형 전부에 대해 `chat_service._get_mbti_group(m) == prompts._get_mbti_group(m)` 단언 1개 테스트. (두 구현은 로직이 다르지만 유효한 16유형에서는 결과가 같음 — 이 테스트가 그것을 증명하고 S10의 통합을 보호한다.)

- **완료 기준**: `cd server && python -m pytest tests/ -q` → **185 passed, 2 skipped** 부근(추가 8개 전부 통과; 실제 수를 새 기준선 N₀로 기록). 커밋: `test: generate_reply/build_system_prompt/mbti_group 특성화 테스트 추가`.
- **위험**: 없음(테스트 추가만). 실패 시 테스트를 코드에 맞춰 수정(코드를 테스트에 맞추지 말 것 — 지금은 현재 동작이 정답).

---

## 3. 작업 항목 목록 (실행 순서 = 우선순위: 효과×위험 반영)

공통 완료 기준(모든 서버 항목): `cd server && python -m pytest tests/ -q` → **N₀ 그대로**(항목이 테스트 파일을 명시적으로 수정하는 경우만 예외로 명기). 공통 롤백: `git revert <해당 커밋>` (푸시 전이면 `git reset --hard HEAD~1`).

### Phase 1 — 데드 코드 제거 (위험 최저, 즉효)

**S1. 미등록 라우터 삭제** — `server/app/routers/subscriptions.py` (복수형, 파일 전체)

- 문제: `main.py`는 단수형 `subscription.py`만 등록(grep으로 `subscriptions` 임포트 0건 확인 완료). `billing.py`/`subscription.py`/`referral.py` 기능의 복제 사본.
- 방법: 파일 삭제. 삭제 전 `tests/test_security_fixes.py`의 전 라우터 임포트 스모크 테스트를 열어 라우터 목록이 하드코딩돼 있는지 확인 — `subscriptions` 항목이 있으면 같은 커밋에서 그 항목만 제거.
- 완료 기준: pytest N₀ + `grep -rn "subscriptions" server/app server/tests` 에서 라우터 참조 0건.
- 위험: 낮음. | 종속: 0.

**S2. 고아 모듈 삭제** — `server/app/compatibility.py` (파일 전체)

- 문제: 궁합 계산 서비스가 2벌 존재. 라이브는 `routers/compatibility.py`(자체 `_COMPATIBILITY_RULES` 보유)이고 이 모듈은 임포트하는 곳 0건(grep 확인 완료). 게다가 모듈 임포트 시 JSON 3개를 무가드로 열어 앱 기동 크래시 위험까지 있음.
- 방법: 파일만 삭제. **이 모듈이 열던 JSON 데이터 파일은 삭제 전 `grep -rn "<파일명>" server/`로 `routers/compatibility.py`가 같이 쓰는지 확인** — 공유 중이면 JSON은 남긴다.
- 완료 기준: pytest N₀ + `cd server && python -c "from app.main import app"` 성공.
- 위험: 낮음. | 종속: 0.

**S3. 깨진 스크립트 삭제** — `server/scripts/insert_community_seeds.py`

- 문제: `postgres_async`에 존재하지 않는 `initialize_pool`/`_pool`을 임포트·호출(8행, 158-159행) — 실행하면 즉사하는 죽은 스크립트.
- 방법: 파일 삭제.
- 완료 기준: pytest N₀. | 위험: 없음. | 종속: 0.

**S4. `postgres.py`의 데드 async 절반 삭제** — `server/app/postgres.py:23,52-160` 일대

- 문제: `main.py:51-56`이 자체 풀 초기화 함수를 정의해 `postgres_async`를 쓰므로, `postgres.py`의 asyncpg 경로는 절대 실행되지 않음(호출자 0건 grep 확인 완료).
- 방법: 다음 심볼만 제거 — `init_async_pool`(:52), `close_async_pool`(:74), `get_postgres_health`(:87), `_asyncpg_to_psycopg`(:108) 및 `_PG_PLACEHOLDER_RE`(:105), `async_execute`(:115), `async_fetchone`(:133), `async_fetchall`(:147), asyncpg 풀 전역 `_pool`(:23)과 관련 asyncpg 임포트. 추가로 중복 임포트 정리: 9-10행과 12-13행이 동일 임포트 반복, `asynccontextmanager`는 미사용. **sync 절반(`execute/fetchone/fetchall/to_jsonb/get_conn/init_postgres_schema`, DDL 리스트 190-626)은 라이브 — 건드리지 말 것** (memory_service, quality_service, firebase_service 등 17개 모듈이 임포트).
- 완료 기준: pytest N₀ + `python -c "from app.main import app"` 성공 + 제거한 각 심볼명 `grep -rn` 0건.
- 위험: 중간(심볼 누락 삭제 시 ImportError — 임포트 스모크가 즉시 잡음). | 종속: 0.

**S5. `chat_service.py` 데드 함수/임포트 삭제**

- 대상: `calculate_affinity_decay`(:324-358), `calculate_return_bonus`(:361-369), `import math`(:6, 사용 0건 확인 완료).
- 문제: 프로덕션 호출자 0건. `tests/test_affinity.py`는 자체 로컬 사본을 정의해 테스트하므로(15, 31행) 삭제해도 테스트 무영향 — 스펙은 테스트에 보존됨.
- 방법: 두 함수와 `import math` 삭제. `CLAUDE.md`의 "시간 기반 감쇠 (7일 이후), 복귀 보너스" 줄에 `(서버 미배선 — 스펙은 tests/test_affinity.py에 보존)` 주석을 덧붙인다.
- 완료 기준: pytest N₀ (특히 `test_affinity.py` 15개 통과 유지).
- 위험: 낮음. 되돌리기: revert. | 종속: 0.

**S6. `models.py` 미사용 스키마 5종 삭제** — `DeleteConversationRequest`(:180), `DeleteConversationResponse`(:187), `SessionStartRequest`(:194), `SessionStartResponse`(:201), `MemoryMomentItem`(:303)

- 문제: 정의 외 참조 0건(grep 확인 완료).
- 방법: 각 클래스 삭제 직전 클래스명별 `grep -rn <이름> server/ android/` 재확인(0건일 때만 삭제) 후 제거.
- 완료 기준: pytest N₀ (특히 `test_models.py` 19개). | 위험: 낮음. | 종속: 0.

### Phase 2 — 상수·설정 집중화 (중복의 뿌리 제거)

**S7. 감정 코드 상수 단일화**

- 문제: `{"NEUTRAL","HAPPY","SHY","SAD","ANGRY","SURPRISED","LOVE","PLAYFUL","WORRIED","TOUCHED"}` 리터럴이 5곳 반복 — `chat_service.py:1488`, `:1553-1556`, `:1626`, `IncrementalReplyParser._VALID_EMOTIONS`(:1715-1718), `quality_service.py:105-108`.
- 방법: `server/app/models.py`(ReplyPart 정의 옆)에 `VALID_EMOTIONS: frozenset[str] = frozenset({...10종...})` 추가 → 5곳 모두 이를 임포트해 대체. `IncrementalReplyParser._VALID_EMOTIONS = VALID_EMOTIONS`로 클래스 속성은 유지(테스트가 참조할 수 있음).
- 완료 기준: pytest N₀ (특히 `test_incremental_reply_parser.py` 8개) + 리터럴 세트 `grep -c "PLAYFUL" server/app/chat_service.py` 감소 확인.
- 위험: 낮음. | 종속: 0.

**S8. 흩어진 env 읽기 → `config.py` 집결**

- 문제: `config.py`가 단일 소스인데 2곳이 이탈 — `postgres_async.py:423` `DATABASE_REPLICA_URL`, `routers/community.py:102` `REDIS_URL`(+`_TRENDING_TTL=600` 매직넘버 :103).
- 방법: `config.py`에 `DATABASE_REPLICA_URL = os.getenv("DATABASE_REPLICA_URL", "")`, `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")`, `TRENDING_CACHE_TTL = 600` 추가 → 두 파일은 `from .config import ...`(community는 `from ..config import ...`)로 대체. 기본값 문자열은 **한 글자도 바꾸지 말 것**.
- 완료 기준: pytest N₀ + `grep -rn "os.getenv" server/app --include="*.py" | grep -v config.py` → 0건.
- 위험: 낮음. | 종속: 0.

**S9. JSON 블록 추출 헬퍼 통일**

- 문제: `content.find("{") / content.rfind("}")+1` 슬라이싱 패턴이 9곳 반복 — `chat_service.py:425-428, 476-478(배열 변형), 1482-1485, 1558-1560, 1635-1637`, `quality_service.py:118-119, 194-195`, `memory_service.py:374-375, 456-457`.
- 방법: 신규 `server/app/json_utils.py` 생성:

  ```python
  def extract_json_object(content: str) -> str | None:
      start = content.find("{"); end = content.rfind("}") + 1
      return content[start:end] if start >= 0 and end > start else None

  def extract_json_array(content: str) -> str | None:
      start = content.find("["); end = content.rfind("]") + 1
      return content[start:end] if start >= 0 and end > start else None
  ```

  각 호출부는 **슬라이싱 부분만** 이 함수로 교체하고, 사이트별 `json.loads` try/except·폴백 동작은 그대로 유지. None 반환 시의 분기가 기존 `if start >= 0 ...` 실패 분기와 동일하게 이어지는지 사이트마다 확인.
- 완료 기준: pytest N₀ (특히 `test_quality_memory_improvements.py`, `test_memory_extraction.py`).
- 위험: 중간(사이트별 미세 변형 — 배열/객체 혼동 주의). 실패 시 해당 사이트만 원복. | 종속: 0.

**S10. `_get_mbti_group` 3중 정의 통일**

- 문제: `chat_service.py:119-130`(명시 분기), `prompts.py:804-808`(`mbti[1]+mbti[2]`), `prompts.py:871-879`(`get_compatibility_description` 내부 중첩 `get_group`) — 유효 16유형에서는 동치이나(0-3(c)가 증명) 비정상 입력 처리 상이.
- 방법: 신규 `server/app/mbti.py`에 **chat_service 버전(엄격한 쪽)을 정본으로 이동**, 이름 `get_mbti_group`. `chat_service.py`와 `prompts.py` 양쪽의 로컬 정의를 삭제하고 임포트로 대체(중립 모듈이므로 순환 임포트 없음). `prompts.py` 내 중첩 `get_group`도 이 함수 호출로 교체(중첩 `get_jp_desc`는 그대로 둠). `tests/test_mbti_group_equivalence.py`를 "16유형에 대해 `app.mbti.get_mbti_group` 결과가 기존 기대값 테이블과 일치" 형태로 갱신(이 항목의 유일한 테스트 수정 허용).
- 완료 기준: pytest N₀ (동등성 테스트 갱신 포함) + 0-3(b) 골든 테스트 3개 통과(프롬프트 출력 불변 증명).
- 위험: 중간. 골든 테스트가 최후 방어선. | 종속: 0-3(b), 0-3(c).

### Phase 3 — 채팅 파이프라인 중복 해소·분할 (효과 최대)

**S11. `generate_reply`/`stream_reply` 공통 블록 6종 헬퍼 추출** — `server/app/chat_service.py`

- 문제: 두 함수가 미러 구조로 동일 블록을 복붙 유지 — 수정 시 한쪽 누락 사고의 온상.
- 방법: 모듈 레벨 private 헬퍼로 추출(양쪽에서 호출). 짝은 다음과 같음(줄은 0커밋 기준):

  | 헬퍼(신규) | generate_reply | stream_reply | 내용 |
  |---|---|---|---|
  | `_trim_history` | 729-734 | 1111-1115 | `_MAX_HISTORY=10` 짝수 트림 |
  | `_build_recent_context` | 762-768 | 1146-1152 | 최근 8메시지 "사용자/캐릭터:" 조인 |
  | `_resolve_reply_client` | 881-889 | 1221-1225 | LoRA면 Together용 AsyncOpenAI 생성 |
  | `_merge_rag_results` | 830-843 | 1194-1205 | RAG 결과 dedupe 병합 + ep_lines |
  | `_collect_affinity_delta` | 912-921 | 1291-1299 | 병렬 task 수거 + 키워드 폴백 |
  | `_record_quality_gate_event` | 933-943 | 1278-1288 | quality_gate_triggered 이벤트 |

  추출 전 각 짝을 diff로 대조 — **완전 동일할 때만 공용화**, 미세 차이가 있으면 파라미터로 흡수하되 양쪽 동작 불변을 우선.
- 완료 기준: pytest N₀ (특히 `test_stream_reply.py` 9개, `test_generate_reply_characterization.py` 4개 전부).
- 위험: 중간. 헬퍼 하나 추출할 때마다 pytest 실행 권장. | 종속: 0-3(a).

**S12. `generate_reply` 품질 게이트 블록 추출** — `chat_service.py:928-992`

- 문제: 재생성 로직(점수→재시도→우세 선택) 65줄이 본문에 인라인.
- 방법: `async def _quality_gate_regenerate(...) -> tuple[list[ReplyPart], str]` 로 추출(입력: 1차 파싱 결과·점수·재호출에 필요한 client/model/messages, 출력: 최종 채택 replies와 content). stream 쪽 변형(1275-1288)은 텔레메트리만이므로 **이 항목 대상 아님**.
- 완료 기준: pytest N₀, 특성화 테스트 4번(재생성 경로) 통과.
- 위험: 중간. | 종속: S11, 0-3(a).

**S13. `generate_reply` 잔여 본문 단계별 분할**

- 방법: 남은 본문을 `_safety_check_input`(741-747), `_spawn_parallel_analysis`(761-790), `_assemble_prompt_and_model`(850-889), `_emit_background_metrics`(1015-1050) 으로 추출. **공개 시그니처(`generate_reply(...) -> Tuple[List[ReplyPart], int]`)와 예외 시 task 정리(1054-1065) 동작 불변**. 목표: 본문 ≤120줄.
- 완료 기준: pytest N₀. | 위험: 중간. | 종속: S12.

**S14. `stream_reply` 동일 분할**

- 방법: S13에서 만든 헬퍼를 재사용하고, 스트리밍 고유부(증분 파스 루프 1245-1260, 빈 방출 폴백 1263-1268, 저품질 텔레메트리)만 남긴다. `StreamDone` 계약·yield 순서 불변.
- 완료 기준: pytest N₀ (특히 `test_stream_reply.py` — 버블 방출 순서 검증 포함). | 위험: 중간~높음(제너레이터라 yield 타이밍 민감). 실패 시 즉시 revert. | 종속: S13.

### Phase 4 — routers/chat.py 및 라우터 공통화

**S15. `_finalize_chat_turn` 분해** — `routers/chat.py:139-360`

- 방법: 중첩 `async def _record_affinity_level_up`(:234-251)과 `async def _persist_chat_data`(:289-343)를 모듈 레벨로 승격, 야간일기 블록(:165-201)을 `_maybe_generate_night_diary`로, 레벨 추론(:208-233)을 `_infer_affinity_level_change`로 추출. **주의**: `tests/test_chat_turn_events_user_id.py`의 `patch_finalize_deps` 픽스처가 `record_event`/`create_tracked_task`/`mark_callback_used`/`get_story_state`를 모듈 경로로 monkeypatch함 — 이 이름들의 모듈 레벨 바인딩을 바꾸지 말 것(예: `from x import y`를 `import x` 스타일로 바꾸면 패치가 깨짐).
- 완료 기준: pytest N₀ (특히 `test_chat_turn_events_user_id.py` 3개). | 위험: 중간. | 종속: 0.

**S16. `stream_message` 분해** — `routers/chat.py:475-674`

- 방법: 위기 힌트 프롬프트 빌더(:501-527)를 `_build_crisis_hint`로, LoRA 경로 제너레이터(:586-620)와 OpenAI 경로 제너레이터(:623-674)를 각각 모듈 레벨 `_lora_event_generator`/`_openai_event_generator`(필요 값은 파라미터로 전달)로 추출. SSE 이벤트 포맷·순서 불변.
- 완료 기준: pytest N₀. | 위험: 중간. | 종속: S15.

**S17. 불필요한 지연 임포트 승격 (순환 없는 것만)**

- 대상: `routers/chat.py`의 `from ..models import ReplyPart`(:452, :532, :657 — 3회 반복), `import json as _json`(:744, :771), `import openai`(:713, :806) → 파일 상단으로. `chat_service.py:1342`의 중복 `from openai import AsyncOpenAI`(상단 :14에 이미 있음) 제거.
- **승격 금지(순환/기동 순서 회피 목적)**: `chat_service.py`의 `get_ab_manager`/`get_async_db` 지연 임포트, `scheduler.py`의 모든 잡 내부 임포트(의도적 — `tests/test_scheduler_jobs.py`가 이 패턴에 의존), `memory_service.py:439`의 `get_store`. 이들 각각에 `# 지연 임포트: 순환/기동 순서 회피` 주석만 추가.
- 완료 기준: pytest N₀ + `python -c "from app.main import app"`. | 위험: 낮음. | 종속: S16.

**S18. 소유권 검사 idiom 단일화**

- 문제: 동일한 "토큰 uid == 대상 user_id" 검사가 3가지 형태 — `community.py:13-17 _assert_owner`(403), `referral.py:14-18 get_uid`(401), 인라인 검사 `billing.py:103-105`/`routers/subscription.py:108-110`(403).
- 방법: `auth_middleware.py`에 `_assert_owner(user, user_id)`(403)와 `get_uid` 의존성(401)을 이동·공개하고, 위 4곳이 임포트해 사용. **각 엔드포인트의 현재 상태코드(401 vs 403)를 절대 바꾸지 말 것** — 검사 로직 위치만 이동.
- 완료 기준: pytest N₀ (특히 `test_feedback_user_id.py`, `test_security_fixes.py`). | 위험: 중간(보안 로직 — 상태코드 회귀 주의). | 종속: S1(subscriptions.py의 중복 `get_uid`가 먼저 삭제돼 있어야 함).

**S19. `datetime.utcnow()` 제거 (출력 포맷 보존)**

- 문제: deprecated API — `routers/chat.py:272`, `diary_store.py:13` 외 `grep -rn "utcnow" server/app`으로 전수 확인(S1이 지운 subscriptions.py 제외).
- 방법: 각 사이트를 `datetime.now(timezone.utc).replace(tzinfo=None)`로 교체(naive UTC 유지 → isoformat 출력·DB 저장값 바이트 동일). `routers/chat.py:272`처럼 `.isoformat() + "Z"`가 붙는 곳은 결과 문자열이 기존과 완전히 같은지 파이썬 REPL로 1회 확인.
- 완료 기준: pytest N₀ + pytest 실행 시 해당 DeprecationWarning 소멸. | 위험: 낮음. | 종속: S1.

### Phase 5 — Android

공통 완료 기준(전 항목): `cd android && .\gradlew.bat compileDebugKotlin` → BUILD SUCCESSFUL.

**A1. `ChatApi.kt` DTO 분리** — `data/remote/ChatApi.kt`(672줄)

- 문제: Retrofit 인터페이스 1개(:254-447) + 전 도메인 DTO 55개가 한 파일.
- 방법: `data/remote/dto/` 디렉터리에 도메인별 파일 신설 — `ChatDtos.kt`(Memory/Chat/Reply), `DiaryDtos.kt`, `FinetuneDtos.kt`, `ImageDtos.kt`, `FeedbackDtos.kt`, `CommunityDtos.kt`, `ReferralDtos.kt`, `BillingDtos.kt`, `MiscDtos.kt`(FCM/알림/시즌/궁합/연간리포트). **패키지 선언은 기존과 동일하게 `com.example.mbtichatfriend.data.remote` 유지** → 사용처 임포트 변경 0건. `ChatApi.kt`에는 인터페이스만 남긴다. 클래스 정의를 이동만 하고 필드·어노테이션은 한 글자도 수정 금지.
- 위험: 낮음(컴파일러가 전부 검증). | 종속: 0.

**A2. 호감도 레벨 표시 헬퍼 단일화**

- 문제: 레벨→한국어명 `when`이 4곳(`ChatScreen.kt:215-218, 394-399, 448-453`, `HomeScreen.kt:576-583`), 레벨→색상 `when`이 2곳(`HomeScreen.kt:472-479, 627-633`), 레벨 태그 변형 1곳(`HomeScreen.kt:536-543`).
- 방법: 신규 `ui/components/AffinityDisplay.kt`에 `fun affinityLevelName(level: Int): String`, `fun affinityLevelColor(level: Int): Color` 정의 후 교체. **교체 전 각 `when`의 문자열/hex를 서로 대조** — 완전 동일한 것만 공용 함수로, 다른 매핑(태그 변형 등)은 별도 함수(`affinityLevelTag`)로 분리해 문구 변화 0 보장.
- 위험: 낮음(육안 문자열 대조 필수). | 종속: A1.

**A3. 공용 `ConfirmDialog` 추출**

- 문제: 제목/본문/확인/취소 AlertDialog 패턴 4벌 — `ChatScreen.kt:494-513`(대화 삭제), `:516-536`(공유 확인), `HomeScreen.kt:129-153`(캐릭터 삭제), `SettingsScreen.kt:528-549`(로그아웃).
- 방법: `ui/components/ConfirmDialog.kt`에 `title/text/confirmLabel/dismissLabel/confirmColor/onConfirm/onDismiss` 파라미터 컴포저블 신설, 4곳 교체. 각 사이트의 기존 문구·색·버튼 순서 그대로 파라미터로 전달. 공유 확인 다이얼로그(:516-536)처럼 confirm 람다에 비즈니스 로직이 있는 경우 람다 내용은 그대로 유지.
- 위험: 낮음. | 종속: A1.

**A4. `ChatScreen` 컴포저블 분해** — `ChatScreen.kt:123-537`(415줄)

- 방법: 같은 파일 내(또는 `ui/chat/` 신규 파일)에 `ChatTopBar`(183-268), `AffinityProgressBar`(271-280), `OfflineBanner`(283-298), `EmptyChatPlaceholder`(312-333), `LevelUpDialog`(393-444), `LevelDownDialog`(447-491) 추출. state는 파라미터/람다로 내려주고 hoisting 구조 불변. 목표: `ChatScreen` 본문 ≤150줄.
- 위험: 중간(콜백 배선 실수). 완료 후 수동 스모크 권장: 앱 실행 → 채팅 진입 → 메시지 전송 1회. | 종속: A2, A3.

**A5. `MessageBubble` 분해** — `ChatScreen.kt:622-884`(262줄)

- 방법: `UserMessageBubble`(643-735, PENDING/FAILED/재시도 포함)과 `AiMessageBubble`(736-883, 감정 틴트+피드백 썸 포함)로 분리, 기존 `MessageBubble`은 role에 따라 위임하는 3줄 함수로 유지(호출부 무변경).
- 위험: 낮음~중간. | 종속: A4.

**A6. `SettingsScreen` 섹션 추출** — `SettingsScreen.kt:69-550`(481줄)

- 방법: `ProfileCard`(136-190), `ThemeSection`(230-255), `ReferralCard`(261-368, 카카오 공유 Intent 로직 포함 — 로직 이동 없이 통째로), `InviteCodeCard`(374-438) 추출. 중복 Snackbar 2벌(488-499, 502-513)은 하나의 로컬 컴포저블로.
- 위험: 낮음. | 종속: A2, A3.

**A7. `HomeScreen` 배너 카드 통합(동형 3종만)** — `HomeScreen.kt:671-778`

- 문제: `GalleryBannerCard`/`WhiteDayBannerCard`/`ImageGeneratorBannerCard`가 색·문구만 다른 구조 동일 복사본.
- 방법: `DismissibleBannerCard(title, subtitle, containerColor, onClick, onDismiss?)` 하나로 통합하고 3곳 호출 교체. **`ui/home/`의 13개 시즌 배너 파일 통합은 이번 범위 외(백로그)** — 손대지 말 것.
- 위험: 낮음. | 종속: A4.

**A8. redeem 엔드포인트 이중화 해소** — `ChatApi.kt:333, 420`

- 문제: 같은 서버 경로에 `redeemReferralCode(ReferralRedeemRequest)`(:333, 사용처 `OnboardingViewModel.kt:150`)와 `redeemReferral(RedeemRequest)`(:420, 사용처 `MainActivity.kt:177`, `SettingsViewModel.kt:85`)의 2개 선언이 공존. 코드 주석(:418 부근)도 중복을 인정. **온보딩 경로가 서버 기대와 다른 body를 보낼 가능성 있음.**
- 방법: ① 먼저 `server/app/routers/referral.py`의 redeem 핸들러를 읽어 기대 request body 스키마를 확인(예상: `{"code": ...}` — `SettingsViewModel.kt:78` 주석이 "V3 endpoint" 재사용을 명시하고 최근 커밋 5ac280d가 이 정합화를 수행). ② 서버 스키마와 일치하는 쪽(`redeemReferral`+`RedeemRequest`)으로 `OnboardingViewModel.kt:146-1xx`를 이관. ③ 이관 후 `redeemReferralCode`와 `ReferralRedeemRequest`의 잔여 사용처를 grep — 0건이면 삭제(`ReferralRedeemResponse`는 양쪽이 쓰므로 유지). ④ 두 DTO의 필드가 의미상 다르면(단순 이름 차이가 아니면) **삭제하지 말고 중단·보고**.
- 완료 기준: compileDebugKotlin OK + `grep -rn "redeemReferralCode" android/` 0건.
- 위험: 중간(런타임 계약). 서버는 절대 수정하지 않는다. | 종속: A1.

### 실행 순서 전체 추적 검증 (제출 전 확인 완료)

0-1→0-2→0-3 → S1→S2→S3→S4→S5→S6 → S7→S8→S9→S10 → S11→S12→S13→S14 → S15→S16→S17→S18→S19 → A1→A2→A3→A4→A5→A6→A7→A8

- S1이 `subscriptions.py`를 지우므로 S18(중복 get_uid)·S19(utcnow 대상 목록)의 전제 성립 ✓
- S10이 `prompts.py`를 수정하지만 0-3(b) 골든 테스트가 먼저 존재 ✓
- S11~S14는 S5(chat_service 삭제)로 줄 번호가 밀림 → 심볼 기준 탐색 지침으로 커버 ✓
- A2~A7이 참조하는 ChatScreen/HomeScreen 줄 번호는 A1(별도 파일)과 무간섭 ✓ / A4 이후 A5의 줄 번호는 밀림 → 심볼 기준 ✓

---

## 4. 하지 말아야 할 것 (금지 목록)

1. **동작 변경 금지**: 이 계획의 모든 항목은 동작 보존 리팩토링이다. 아래 "발견된 버그 백로그"의 버그를 포함해 **어떤 버그도 이번에 고치지 말 것** — 발견하면 보고만.
2. **의존성/버전 업데이트 금지**: requirements.txt, Gradle 플러그인, Kotlin/Compose/Room 버전, compileSdk 일절 변경 금지.
3. **Room 스키마·마이그레이션 변경 금지** (v8 유지, `schemas/` 파일 수정 금지).
4. **API 계약 변경 금지**: 서버 라우트 경로, request/response 스키마, SSE 이벤트 포맷, 응답 envelope(`{"status": "ok"}` vs `{"ok": true}` 등 비일관성 포함) 전부 현상 유지. A8도 클라이언트 내부 정리일 뿐 서버 계약은 불변.
5. **prompts.py의 한국어 페르소나/행동 텍스트 내용 수정 금지** — 구조 이동만 허용(이번 계획엔 S10의 함수 통일만 포함).
6. **모델명 변경 금지**: gpt-4.1/gpt-4.1-mini 유지, gpt-4o 도입 금지, `_MODEL_COSTS` dict 삭제 금지(비용 추적용 유지 관례).
7. **테스트 삭제·약화 금지**: 실패하면 테스트를 고치지 말고 중단·보고 (명시 허용된 S10의 동등성 테스트 갱신만 예외).
8. **`ui/chat/MemoryFabButton.kt`, `LottieAffinityView.kt`, `SessionFeedbackSheet.kt` 및 ChatViewModel의 세션 피드백 관련 상태 삭제 금지** — 미사용이지만 최근 스프린트에서 의도적으로 준비된 휴면 기능. 소유자 결정 필요.
9. **건드리지 않는 파일**: `server/tools/lora_pipeline.py`, `server/evaluate.py`(chat_service의 `analyze_affinity_with_llm`/`calculate_affinity_delta`/`score_response_async` 시그니처에 의존 — 이 시그니처들 변경 금지), `server/tests/chat_quality_test.py`(수동 스크립트 — pytest로 개조 금지), `server/app/legacy_vector_cleanup.py`(관리 CLI 전용, 데드 아님).
10. **전체 파일 리포맷/임포트 정렬 도구 실행 금지** — diff는 항목이 명시한 범위만.
11. **strings.xml 외부화, MVI 마이그레이션 완성, sync/async DB 단일화, 시즌 배너 13종 통합, HomeScreen 공유 로직 VM 이동 시도 금지** — 전부 별도 스프린트 백로그.

### 발견된 버그 백로그 (이번 리팩토링에서 수정 금지, 소유자 보고용)

- `community.py:299,446` — `AsyncDatabase.execute`는 항상 `None`을 반환하므로 `result == "UPDATE 0"` 분기가 영구 데드 → 비인가 삭제가 403 대신 조용히 204.
- `chat_service.py:1413-1434` — async 함수 `_post_response_quality_check`가 동기 `check_diversity`(블로킹 DB)를 이벤트 루프에서 직접 호출.
- `routers/chat.py:662-672` — SSE 제너레이터에서 `_finalize_chat_turn`이 try 밖 → 예외 시 클라이언트가 `done` 이벤트를 못 받음.
- `web_chat.py:268` — 업스트림 오류 원문을 클라이언트에 노출.
- `ChatRepository.kt:130-141` — 네트워크 실패 시 가짜 성공 응답("음... 잠깐 생각할게요!")을 정상 메시지로 저장 → 오류가 사용자/DB에서 구분 불가.
- Android 무음 예외 삼킴 7곳(`ChatViewModel.kt:193-195`, `HomeViewModel.kt:310-313`, `ChatRepository.kt:182-184, 233-235` 외).
- A8 조사 중 온보딩 redeem이 잘못된 body 스키마를 보내고 있을 가능성 — A8 ①단계에서 판명되면 보고.

---

## 5. 실행자를 위한 지침 (이 블록을 그대로 복사해 전달)

```
[작업 규칙]
1. 이 계획서의 항목을 0-1부터 명시된 순서대로, 한 번에 하나씩만 실행한다.
2. 각 항목 완료 시 즉시 커밋한다 (1항목 = 1커밋). 커밋 메시지: "refactor(<영역>): <항목ID> <한 줄 요약>" (0번대와 test 추가는 계획서에 적힌 메시지 사용).
3. 각 항목의 완료 기준 명령을 실행하고, 예상 결과와 다르면 그 항목의 변경을 되돌리고(git reset --hard HEAD, 커밋 전) 중단 후 무엇이 달랐는지 보고한다. 임의로 우회하거나 테스트를 수정해 통과시키지 않는다.
4. 검증 명령:
   - 서버: cd server && python -m pytest tests/ -q  → 기준선(0-3 이후 기록한 N₀ passed, 2 skipped) 유지
   - Android: cd android && .\gradlew.bat compileDebugKotlin  → BUILD SUCCESSFUL
5. 계획서의 줄 번호는 항목 0-1 커밋 시점 기준이다. 실행 시점에는 반드시 심볼 이름으로 위치를 재확인하고, 줄 번호와 실제 코드가 크게 어긋나면 중단·보고한다.
6. "하지 말아야 할 것" 11개 조항과 버그 백로그(수정 금지)를 매 항목 시작 전에 다시 읽는다.
7. 삭제 항목(S1~S6, A8③)은 삭제 직전 반드시 해당 심볼로 저장소 전체 grep을 다시 실행해 참조 0건을 확인한 뒤 삭제한다. 1건이라도 나오면 중단·보고.
8. 계획에 없는 개선점을 발견하면 수행하지 말고 목록으로만 보고한다.
9. 전 항목 완료 후 최종 회귀: 서버 pytest + Android compileDebugKotlin + (선택) 서버 기동 스모크
   cd server && uvicorn app.main:app --port 8090 (기동 성공 확인 후 종료)
   결과를 기준선과 함께 최종 보고한다.
```

---

*작성: Claude (2026-07-07). 조사 방법: 병렬 탐색 에이전트 4개(서버 코어 / 서버 인프라·라우터 / Android / 테스트 인벤토리) + 삭제 후보 전건 grep 직접 재검증 + 테스트 기준선 실측(177 passed, 2 skipped).*
