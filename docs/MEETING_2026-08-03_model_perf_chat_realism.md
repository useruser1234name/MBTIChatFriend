# 회의록 — 모델 성능 개선 × 실제 채팅하는 듯한 UI (2026-08-03)

- **형식**: 3라운드 멀티에이전트 (제안 4 → 적대 검증 2 → 종합 1)
- **참여**: llm-expert, ux-designer, frontend-dev, pm (제안) / 서버·Android 적대 검증 2명
- **브랜치**: `improve/2026-07-perf-ux-character` (clean, U9=66192ef 이후)
- **검증 원칙**: 파일:줄 근거 없는 주장 기각. 라운드1 주장 총 27건 중 REFUTED 0건, DOWNGRADED 1건(quick_score), 각주 필수 2건. 검증 라운드에서 **신규 결함 8건** 추가 발견.

---

## 1. 확정 결함 (검증 CONFIRMED, 버그성 — 우선 수정 대상)

### 서버 (축1: 모델 성능)

| ID | 결함 | 근거 | 규모 |
|---|---|---|---|
| **S1** | **few-shot 4개 유형 오배정**: `FEW_SHOT_EXAMPLES` 키 "ST"/"SF"의 예시 본문이 SJ/SP 기준으로 작성됐는데 디스패치는 S+T/S+F → ISTP·ESTP·ISFJ·ESFJ(16종 중 25%)가 페르소나와 정반대 few-shot 수령. 실행 검증됨(ISTP가 SJ식 잔소리 돌봄 예시를 받음) | `prompts.py:775,789,806-809`, `mbti.py:24-27` | S |
| **S2** | **복잡도 라우팅 프로덕션 사망**: `_route_model`이 character_id 존재 시(사실상 항상) A/B `assign_variant`를 즉시 반환 → `_classify_message_complexity` 도달 불가. sha256(character_id) 해시로 캐릭터의 70%는 영구 mini, 30%는 영구 4.1. 자해·심층 상담 턴도 mini로 처리될 수 있고, A/B 결과도 캐릭터 고정 배정이라 교란됨 | `chat_service.py:623-636`, `ab_test.py:29-37,225-230`, `routers/chat.py:476,712` | S(코드)/M(검증) |
| **S3** | **위기(crisis) 3중 미배선**: (a) `select_model_for_crisis` 결과가 로그/이벤트에만 쓰이고 generate_reply/stream_reply에 미전달 — Tier1 자해 턴이 mini로 갈 수 있음. (b) `_build_crisis_hint` 지침이 LoRA 경로에만 전달되는데 (c) ChatRequest에 ab_variant 필드가 없어 LoRA 경로 자체가 도달 불가 → **위기 지침이 실질적으로 어디에도 적용 안 됨**. LoRA 실험 16종 + `AB_VARIANT_TO_LORA_KEY` 매핑도 사문화(후기 7종은 매핑조차 미등록) | `routers/chat.py:558-560,651-652,762-766,816`, `models.py:24-56`, `model_routing.py:26-34,63-64` | M |
| **S4** | **신규 방 memory 이중 조회 + 네거티브 캐시 부재**: 캐시 미스 시 아무것도 기록하지 않아 매 턴 DB 재조회 + `if not mem_ctx:` 재호출로 기억 없는 방은 턴당 build_memory_context 2회 = fetchone 최대 4회, 그중 2회는 TTFT 직렬 경로 | `memory_service.py:181-182,490-503`, `chat_service.py:987-998,1236-1242,1445,1472-1475` | M |
| **S5** | **quick_score 자모 무방비** (DOWNGRADED에서 살아남은 실체): `_normalize_text`가 자모(ㅇㅋㅎㅠ)를 전부 제거해 `"ㅇㅇ"` 반복 응답이 **0.95점**(거의 만점). 형식 실패 게이트(0.1~0.3)는 동작하나 내용 휴리스틱은 사실상 무력. 임계값 조정만으로 못 잡고 `_normalize_text` 수정 필수 | `quality_service.py:164-168,183-188,210-245` (실측 0.95) | S |
| **S6** | **`get_safety_system_prompt` 중복 정의**: content_filter.py에 동명 함수 2개, 나중 정의(핫라인 포함)가 이기고 앞 정의는 데드 코드 — 앞쪽을 수정하면 무효과가 되는 함정 | `content_filter.py:321,487` | S |

### Android (축2: 채팅 리얼리즘)

| ID | 결함 | 근거 | 규모 |
|---|---|---|---|
| **A1** | **메시지 등장 애니메이션 no-op**: `AnimatedVisibility(visible = true)` 상수라 enter 전이(fadeIn+slideIn)가 한 번도 재생 안 됨. `MutableTransitionState(false)` 필요 | `ChatScreen.kt:261-267` | S |
| **A2** | **피드백 아이콘 비반응형 구독**: `viewModel.feedbackMap.value[msg.id]`로 StateFlow.value 직접 읽음 → 탭 자체는 어떤 snapshot state도 안 건드려 **항상** 갱신 지연(다음 메시지/스크롤까지). `collectAsState()` 치환 필요 | `ChatScreen.kt:273`, `FeedbackUseCase.kt:18-28` | S |
| **A3** | **피드백 영속성 단절**: feedbackMap이 메모리 전용, Room 저장은 되나 복원 경로 데드코드(호출부 0) → 재진입 시 표시 소실 + 중복 제출 가능 | `FeedbackUseCase.kt:18,27,39`, `ChatRepository.kt:159-166,188` | S/M |
| **A4** | **LoRA 스트리밍 활성 시 응답 전체 소실(조건부 치명)**: LoRA 성공 경로는 token 이벤트만 yield하는데 SseClient는 token을 드롭 → LoRA 켜지는 순간 클라는 텍스트 0개 수신. 현재는 LoRA 도달 불가(S3-c)라 잠복 상태 | `chat.py:662-672,815-818`, `SseClient.kt:90-111` | 결정 필요 |
| **A5** | uiState 이중 관리 + `isStreaming`/`error` 등 stale(트리거 미배선), 미소비 필드 다수 | `ChatViewModel.kt:90-103,140-153,225-228`, `ChatUiState.kt:23-32` | M |
| **A6** | `items` 내 `messages.indexOf(msg)` O(n²) + `TypingIndicatorBubble.kt`(Lottie) 데드코드 | `ChatScreen.kt:259-260,106` | S |

### 측정 (pm)

| ID | 결함/공백 | 근거 |
|---|---|---|
| **P1** | `turn_latency`가 t_gate 의도적 제외 + t_first_token이 LLM 호출 시작 기준 → 사용자 체감 end-to-end TTFT 미대표 | `chat_service.py:767-776` |
| **P2** | `cached_tokens` 미기록 — 실제 prefix cache 히트율 완전 미지 | `chat_service.py:1678-1707` (grep 0건) |
| **P3** | 세션 경계 정의 부재 — "세션당 턴 수" 산출 불가 (turn_count는 room 누적) | `story_state_store` PK=room_id |
| **P4** | `AFFINITY_LEVEL_UP` 클라 계측 부재(서버 기록은 존재 `chat.py:405-409`), `COMMUNITY_POST_VIEWED`는 양측 완전 사장 | `AnalyticsRepository.kt:96,102` |

---

## 2. 확정 개선 제안 (검증 통과)

### 축1: 모델 성능

| ID | 제안 | 핵심 설계 | 규모 | 게이트 |
|---|---|---|---|---|
| **M1** | Phase 3 — 호감도별 disclosure 게이팅 | `prompts.py:1143` "조금만 내주고 더 많이 감춰"(정적, 전 레벨)가 Lv5 "달달함 최대치" 및 high few-shot 직접 진술과 3중 충돌 확정. 정적 블록은 바이트 불변 유지, `AFFINITY_BEHAVIORS`에 `disclosure` 키 신설(Lv1-3 감춤/Lv4 슬쩍/Lv5 직접 표현 허용, 해설만 금지)해 반동적 구역에 주입. `:1167` "질문으로 대화 이어가" → 2~3턴에 한 번으로 완화. few-shot 정형 위로 문구 3개(`:767,772,781` — 웹 MVP 금지 목록과 동일 문구) 교체 | M | **사람 평가 12셀(MBTI 4그룹×호감도 3티어) 필수** — 자동 점수는 질문 제거를 감점할 소지 |
| **M2** | user_role/situation 이식 (웹 MVP → 메인) | ChatRequest에 필드 2개(max_length=200) → `# 관계` 뒤 반동적 구역에 `## 장면` 블록. 빈 값이면 블록 미생성 → 골든 테스트 바이트 등가 무영향. persona 안전 규칙 동일 적용. Android 입력 UI 필요(ux/frontend 협업) | 서버 S + 클라 M | 프롬프트 인젝션 표면 — length 제한+안전 문구 |
| **M3** | prefix cache 정비 | ①cached_tokens 계측 먼저(P2) ②preference↔few_shot 순서 교환(2026-07-02 합의의 세부 수정 — few_shot이 summary 앞이라는 핵심 목적은 유지, 회의 재결정 사항으로 명시) ③정적 꼬리 671자 전진 배치는 준수율 회귀 위험 → 계측 후 판단 | S(①②)/M(③) | ①이 ②③의 선행 조건 |
| **M4** | quick_score 2단계 | ①quick_score 값을 quality_score payload에 기록(무위험) ②분포 확인 후 `_normalize_text` 자모 단일 토큰화 + MONOTONE 0.05→0.15 + 재생성/텔레메트리 임계 분리. 스트리밍 경로는 재생성 불가라 체감 효과는 논스트림+파인튜닝 데이터 필터 정확도에 한정 | S/M | 분포 확인 선행 |

### 축2: 채팅 리얼리즘

| ID | 제안 | 핵심 설계 | 규모 | 서버 협조 |
|---|---|---|---|---|
| **R1** | **선톡 연출 — nextHook/nextGoal 소비** | 서버가 done payload로 이미 전송(`chat.py:786-799`), 클라 파싱까지 완비(`SseEvent.Done:28-29`)인데 ViewModel이 affinityDelta만 읽고 버림(`ChatViewModel.kt:427-431`). 보관 → 재진입+시간 경과 시 `sendInitialGreeting` 패턴(`:593-612`)으로 캐릭터 선발화. **단서: next_hook은 야간 일기 생성 이후에만 채워짐**(`chat.py:299-320`) — "배선 완비, 야간 일기 이후 활성"이 정확한 전제 | S~M | 불필요 |
| **R2** | 말풍선 그룹핑(이어치기) + 시간 표시 규칙 | 20초 이내 연속 발화 그룹: 첫 버블만 아바타, 마지막 버블만 타임스탬프, 간격 4→2dp, 중간 버블 라운드 축소. 세트 구현 | S | 불필요 |
| **R3** | 읽음 표시 "1" | SseClient에 `onOpen` 콜백 추가(현재 미구현 확인) → 연결 수립 = 읽음. 읽음 지연 절대 금지(읽씹 불안이 아닌 즉시 반응 안정감으로 설계). REST 폴백은 요청 시점 근사 | M | 불필요 |
| **R4** | 햅틱 피드백 | 전송 시 짧은 tick, 수신은 **그룹당 1회**(R2 연동). 사운드는 기본 OFF+설정 토글. 현재 진동/사운드 코드 0건 확인 | S | 불필요 |
| **R5** | 스타터 칩 조건 노출 | 현재 무조건 상시 노출(`ChatScreen.kt:1161-1185`). 첫 대화만 강조, 이후 포커스/무입력 시 페이드인. nextHook 있으면 1순위 칩 | S | 불필요 |
| **R6** | 새 메시지 pill | 스크롤 이탈 중 AI 응답 도착 시 무알림 확정(`:155-177`) → "새 메시지 N개 ↓" 오버레이, 로컬 상태만 | M | 불필요 |
| **R7** | 딜레이 지터 + 감정 가중치 | `_calculate_delay` 순수 결정론 확정(서버는 sleep 안 함, delay는 메타데이터 → 클라 적용 구조 정합 확인됨). ±15% 지터 + 감정별 배수(SURPRISED/ANGRY 즉답, WORRIED/SAD 머뭇) + 첫 버블 +300~500ms. **서버측 sleep 추가 금지(클라 delay와 이중 적용됨)** | S | 필요(서버만) |
| **R8** | 오프라인/실패 카피 캐릭터 보이스화 | 시스템 톤 정적 문구(`:481-498,820-833`) → MBTI 그룹별 대사 4~8종 | S | 불필요 |
| **R9** | TTFB 대기 단계적 문구 | 4초 경과 시 "조금만 더 기다려줘..." 등 문구 전환(보조 타이머). 체감만 개선 — 근본은 S4 | S | 불필요 |

---

## 3. 우선순위 (종합)

**게이트 원칙(pm)**: ①효과를 무슨 지표로 검증할지 사전 답변 불가면 반려 ②리얼리즘 UI는 `session_feedback.rating` + 세션당 턴 수 사전/사후 비교가 최소 검증 기준 → **세션 경계 정의(P3)가 축2 전체의 선행 조건**.

### P0 — 버그 수정 (즉시, 검증 게이트 불요)
1. **S1** few-shot 오배정 (S) — 골든 3개 재캡처 동반
2. **S2** 복잡도 라우팅 복구 + A/B 정책 오버레이 전환 (S) — `_route_model` 신규 테스트 필수(현재 회귀 안전망 0)
3. **S3** crisis 배선: generate/stream에 crisis_tier/hint 파라미터(기본값으로 기존 테스트 보호), Tier1이면 4.1 강제 (M) — 안전 인접 최우선
4. **A1** 등장 애니메이션 no-op (S) + **A2** feedbackMap collectAsState (S) + **A3** 피드백 복원 (S/M)
5. **S6** safety prompt 중복 정의 정리 (S)

### P1 — 성능·계측 (P0 직후)
6. **S4** memory 이중 조회 제거 + 네거티브 캐시(60s TTL) + t_memory_cache_hit 계측 (M) — TTFT 최대 개선 후보
7. **P1+P2** end-to-end TTFT 계측(t_gate 포함) + cached_tokens 기록 (S) — 이후 모든 성능 주장의 근거
8. **P3** 세션 경계 정의(30분 gap 휴리스틱) (S) — 축2 검증 선행 조건
9. **M4-①** quick_score 분포 기록 (S)

### P2 — 리얼리즘 1차 (저비용·고체감부터)
10. **R1** 선톡 연출 (S~M) — 죽은 데이터 재활용, 최고 효율
11. **R2** 그룹핑+시간 규칙 (S) → **R4** 햅틱(그룹 연동) (S) → **R5** 칩 조건 노출 (S)
12. **R3** 읽음 표시 (M) / **R6** 새 메시지 pill (M) / **R8** 카피 보이스화 (S) / **R9** 대기 문구 (S)
13. **A6** itemsIndexed + 데드코드 정리 (S)

### P3 — 검증 게이트 딸린 것 (준비 후)
14. **M1** Phase 3 disclosure 게이팅 (M) — **사람 평가 12셀 게이트 통과 필수**
15. **M2** user_role/situation 이식 (서버 S + 클라 M) — 3팀 협업
16. **R7** 딜레이 지터 (S) — R2/R3 안착 후
17. **M3-②③** prefix cache 재배치 — cached_tokens 데이터 확인 후
18. **M4-②** quick_score 강화 — 분포 확인 후

### 소유자 결정 대기
- **LoRA 처리 방향**: 실험 16종+매핑+A4 결함까지 전부 사문화 상태. (a) 제거(권장: SseClient token 드롭·A4도 자연 해소) vs (b) ab_variant 필드 복구로 부활 — 부활 시 A4(클라 token 분기)와 매핑 7종 미등록도 함께 수리 필요
- **A5** uiState 이중 관리: ChatUiState.kt 주석의 "2단계 마이그레이션" 계획과 충돌 가능 — 방향 결정 필요
- 이월: C5 표정세트 게이트, C6 선제 메시지(FCM), P7 SSE 예산 게이트 배포 시점 (2026-07-08 계획 참조)

---

## 4. 파손 예상 테스트 (실재 확인됨)
- `test_prompts_golden.py:305,326,347` — S1·M1·M2·M3-② 시 재캡처 (347은 ISTP few-shot+preference 위치 내장이라 특히 민감)
- `test_prompts_roleplay.py:50-52` `test_show_dont_tell_hint` — "행동/말투/망설임/침묵" 문구는 반드시 유지
- `test_content_filter.py` — S3 작업 시 위기 감지 레이어는 무영향(경로 분리)
- S2: `test_model_routing.py` 4개는 무영향이나 `_route_model` 직접 테스트 부재 → 신규 작성 필수

## 5. 기각/각주 (교훈)
- llm-expert "quick_score 게이트 도달 불가" → **DOWNGRADED**: 형식 실패(0.1~0.3)는 발동됨. "내용 게이트 사실상 무력 + 자모 무방비"가 정확.
- ux-designer R1의 "매 턴 nextHook 제공" 전제 → 각주: 야간 일기 이후에만 값 존재.
- pm "AFFINITY_LEVEL_UP 미계측" → 각주: 서버 기록은 존재, 클라 계측만 부재.
- 메모리 기록 "복잡도 라우팅 유지" → **stale 확정** (S2). RESOLVED/유지 표기도 재검증 필수라는 기존 교훈 재확인.
