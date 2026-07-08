# MBTIChatFriend 프로젝트 종합 리뷰

**평가일**: 2026-07-02
**브랜치**: `chore/remove-orphan-routers` (origin 대비 uncommitted 변경 다수)
**평가 방식**: 6개 전문 페르소나 병렬 에이전트 (backend / llm / frontend / ux / pm / data)
**검증**: 서버 `pytest` **177 passed, 2 skipped GREEN**, Android `compileDebugKotlin` GREEN — 모두 실측

---

## 한 줄 총평

> **기능은 경쟁 앱 수준으로 완성됐지만, "설계는 있으나 실행 경로엔 없는" 결함이 계층마다 반복된다.** 그리고 오늘 회의에서 고친 핵심 수정본이 **전부 uncommitted 상태** — 지금 배포되는 빌드는 여전히 결함 버전이다.

---

## 🔴 교차 검증된 최우선 이슈

> 여러 에이전트가 독립적으로 같은 문제를 지적 = 진짜 문제

### 1. 수익화가 "실물처럼 보이지만 실제로 작동하지 않는다" — 3개 에이전트 수렴 ⚠️ 최대 발견

| 에이전트 | 지적 |
|---------|------|
| PM | "결제 배관이 목업 아닌 실물, 남은 건 검증뿐" — **강점으로 평가** |
| Frontend | `PremiumScreen.kt:89` **"구독하기" 버튼이 무인자 `subscribe()`로 바인딩 → 실제 `launchBillingFlow` 절대 호출 안 됨.** 게다가 `AppModule.kt:145`의 `PurchasesUpdatedListener`가 빈 스텁이라 구매 콜백 수신 불가 (Critical) |
| Data | "`PURCHASE_INITIATED` 이벤트는 찍히는데 실제 구매는 발생 불가능 — 대시보드가 이걸 그대로 반영할 것" |

**결론**: PM의 낙관(실물)과 Frontend의 코드 증거(버튼 미작동)가 정면 충돌. 서버·레퍼럴 배관은 실물이 맞지만 **Android 결제 진입점 자체가 죽어 있어 단 1건도 결제 불가**. `BILLING_ALLOW_MOCK=true` 기본값(`config.py:64`)까지 겹치면 이중 리스크.

### 2. "코드는 있으나 실행 경로엔 없는" 유령 코드 패턴 — 전 계층 반복

| 위치 | 에이전트 | 내용 |
|------|---------|------|
| `chat_service.py:682` | LLM | **A/B 실험이 복잡도 라우팅을 완전 무력화** — `_classify_message_complexity`가 dead code. 감정상담이 mini로, 인사가 gpt-4.1로 가는 이중 손해 |
| `routers/chat.py:445` | LLM | **위기 모델 선택이 로깅용 장식** — tier1 자해 위기에도 mini로 응답 생성 가능 |
| `chat_service.py:1104` (`stream_reply`) | LLM | 품질 재생성 안전망이 프로덕션 스트리밍 경로엔 없음 (텔레메트리만) |
| `postgres.py:21` | Backend | asyncpg 풀 150줄이 `main.py`에서 초기화 안 됨 → 항상 죽은 고속경로 |
| `chat_turn` user_id | Data / PM | (오늘 수정됨) 원래 "제대로 된 코드"는 아무도 import 안 하는 `shared.py`에만 있었음 |

**결론**: 이 프로젝트의 구조적 취약점. 정적으로 코드를 읽으면 멀쩡해 보이지만 실행 경로가 우회한다. 리뷰·테스트가 "실행 경로 검증"을 놓치고 있다는 신호.

### 3. Uncommitted 수정본 = 출시 blocker — Backend·PM·Frontend 수렴

- 오늘 회의 수정본(리텐션 푸시 4종 부활, chat_turn user_id, 세션 피드백)이 **전부 미커밋**. 지금 스토어 빌드는 결함 버전.
- `android/app/schemas/.../8.json` **untracked** (Frontend) — 커밋 누락 시 Room 스키마 이력 단절.
- `scheduler.py` 334줄 전면 재작성 (Backend) — 단위테스트 GREEN이나 라이브 미검증.
- **d3 푸시 잠금화면 원문 20자 노출**(PM, 프라이버시) — scheduler 수정과 **반드시 같은 PR로** 배포해야 함.

### 4. 세션 단위 지표 측정 불가 — Data·PM 수렴

`session_start`/`session_end` 이벤트 부재 → DAU/MAU, 세션당 턴 수, D1/D7/D30 리텐션 전부 측정 불가. `users.created_at`이 "첫 대화 시점"이라 **온보딩 이탈자가 분모에서 빠지는 생존자 편향**까지 존재.

---

## 🟡 페르소나별 단독 핵심 발견

### 🎨 UX (사용자 관점)
- **온보딩 MBTI 이중 질문 버그**: `MbtiSelectScreen`(step4)에서 고른 값을 다음 화면 `OnboardingScreen`(StyleSelect)이 독립 상태로 다시 물어보고 덮어씀. 라벨은 "나의 MBTI"인데 실제론 상대 MBTI 재설정 (`OnboardingViewModel.kt:74-76`, `AppNavHost.kt:152-156`).
- **홈 화면 배너 과부하**: `HomeScreen.kt:220-432`에 배너/프로모션 카드 최대 20개가 실제 캐릭터 리스트 앞을 막음. 헤비 유저 매일 반복 마찰.
- **온보딩 진행바 소실**: StyleSelect/StarterSelection 화면이 `OnboardingScaffold` 미사용 → 이탈 위험 큰 마지막 구간에서 진행률 안내 끊김.
- **레벨다운 다이얼로그 톤이 처벌적** (`ChatScreen.kt:447-491`, 제목이 "...") → 죄책감 유발.
- **채팅 상단바 아이콘 5개 진입점** 몰림, 대화 스타터 칩이 100턴 유저에게도 초면용 문구 반복.

### 🔧 Backend (서버 엔지니어)
- **[Medium/보안]** `diary.py:58-69` 감정일기 `content`가 **쿼리 파라미터**로 전송 → 프록시/액세스로그 평문 노출 + 입력 검증 부재. Pydantic Body 모델로 교체 필요.
- **[Medium/성능]** 이벤트 루프 블로킹 동기 DB 호출 3곳 (`quality.py:36`, `quality.py:155`→`finetune_audit.py:274`, `data.py:123`) → SSE 스트림 지연 유발.
- **[Medium]** `postgres.py` 미사용 asyncpg 풀(`_pool`/`init_async_pool`/`async_*`) — 제거 또는 deprecated 표시.
- **[Low-Medium]** `/chat/starters/used` 인증·rate limit 둘 다 없어 익명 DB flood 가능.
- **[Low]** `scheduler.py:299` `send_gratitude_day_push` 트리거가 `datetime(2027, 4, 24)` — 의도한 연도인지 확인 필요.

### 🤖 LLM (프롬프트 전문가)
- **[Medium]** few-shot이 16유형이 아닌 4그룹(NT/NF/ST/SF) 공유 → INTJ·ENTP 말투 뭉개짐. `mbti_consistency` 점수 저하 주원인 가능.
- **[Medium]** prefix caching 순서가 설계와 어긋남 — 매 턴 변동 블록(`preference_section`)이 정적 `few_shot`보다 앞, 정적 꼬리(표현규칙·flow·safety)가 동적 뒤에 위치 → 캐시 효율 저하.
- **[Medium]** TSUNDERE 말투("절대 솔직하게 안 함") × 호감도5("달달한 고백") 지시 충돌, 해소 규칙 없음.
- **[Medium/비용]** 턴당 LLM 3회 호출 — 호감도 분석을 키워드 모호 시에만 LLM 태우면 절감 가능.
- **[Low]** 죽은 코드: `detect_crisis` 미사용 import, `get_safety_system_prompt` 이중 정의. 콘텐츠 필터 substring 우회 가능(자모분리·띄어쓰기).

### 📈 Data (분석가)
- **개인화(`user_preference.py`)가 대조군 없이 전 사용자 적용** → 효과 측정 불가. A/B 인프라(`ab_test.py`)는 완비돼 실험 등록 비용 낮음.
- **thumbs 피드백을 응답 속성에 귀속시킬 조인 키 부재** — "어떤 스타일 응답이 썸다운받았나" 분석 불가.
- **클라 계측 12종 중 3종(`app_background`, 클라측 `affinity_level_up`, `community_post_viewed`) 미연결.**
- `quality_gate_triggered`(`chat_service.py:933/1278`)는 이번 P0 수정 범위 밖이라 여전히 user_id 없음.

### 💰 PM (제품 관리자)
- 핵심 대화 루프(캐릭터 대화 → 호감도 → 관계 진행)는 기능적으로 완성.
- **Play 스토어 배포 흔적 0건 + 실유저 데이터 0건** — "리텐션이 나쁘다"를 논하기 전에 측정 대상 자체가 없음.
- 갭 B(몰입형 역할극 프롬프트) 프로덕션 미이식 — 경쟁사 자유도 대비 정형화된 JSON 계약 안에 갇힘.
- 별명짓기 등 손실회피 리텐션 훅이 스펙 단계 머묾.

---

## ✅ 공통 강점 (여러 에이전트 인정)

1. **호감도 시스템** — UX·LLM·PM 모두 극찬. 온도계 시각화 + 레벨업 Lottie + 단계별 말투 개방도. "관계가 눈에 보인다".
2. **테스트/검증 문화** — Backend·Data 확인. 177 passed, mutation-저항 스타일 assert, 회귀 테스트로 P0 고정.
3. **보안 기본값 & IDOR 방지** — production `REQUIRE_AUTH` 강제 가드, CORS wildcard+credentials 금지, user_id를 토큰에서만 채우는 패턴 일관.
4. **fire-and-forget 인프라 + 스트리밍 파서** — 메인 경로 논블로킹, `IncrementalReplyParser`(brace-depth 카운팅) 구현 정확.
5. **품질 평가 파이프라인** — `quick_score`(~1ms) + `score_response_async`(4축) + `check_diversity`(bigram) + 대시보드 API까지 자동 수집.
6. **결제/레퍼럴 서버 배관** — 목업 아닌 실물(레퍼럴 redeem, 영수증 검증). *단 Android 진입점 결함으로 반쪽.*

---

## 🎯 권고 실행 순서

| 순위 | 액션 | 근거 에이전트 | 성격 |
|------|------|--------------|------|
| **0** | Android 결제 버튼 수정 (`subscribe(activity)` 바인딩 + `PurchasesUpdatedListener` 구현) | Frontend | Critical, 매출 직결 |
| **1** | 오늘 수정본 **커밋 + 배포 + 라이브 검증** (8.json 포함, d3 프라이버시 동일 PR) | Backend·PM·Frontend | 안 하면 모든 성과 무효 |
| **2** | `_route_model` / 위기 모델을 실제 생성에 연결 (`stream_reply`에 `model_override` 추가) | LLM | 품질·비용·안전 동시 |
| **3** | `session_start` 이벤트 신설 + signup 시점을 `users.created_at`과 분리 | Data·PM | 데이터 기반 의사결정 전제 |
| **4** | 온보딩 MBTI 이중선택 통합 + 홈 배너 정리 | UX | 신규 이탈 방지 |
| **5** | diary 쿼리파라미터→Body, 블로킹 DB 호출 `to_thread` 이관 | Backend | 보안·성능 |
| **6** | `BILLING_ALLOW_MOCK=false` 프로덕션 강제 + 실 영수증 1회 종단 검증 | PM | 매출/보안 게이트 |

---

## 메타 발견

가장 주목할 점은 **"정적으로 멀쩡해 보이나 실행 경로가 우회하는" 결함이 결제·라우팅·위기대응·계측 4곳에서 동시에 나타난 것**이다. 이는 개별 버그가 아니라 리뷰 프로세스가 실행 경로 검증을 놓치는 구조적 문제다. 향후 리뷰/테스트에 "이 코드가 실제로 호출되는가" 검증 단계를 명시적으로 추가할 것을 권장한다.

---

*이 리포트는 6개 페르소나 에이전트의 병렬 평가 결과를 교차 검증해 종합한 것입니다. 각 발견은 실제 코드(파일:라인)와 테스트 실행 결과에 근거합니다.*
