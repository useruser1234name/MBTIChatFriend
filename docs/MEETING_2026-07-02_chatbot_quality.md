# 챗봇 품질 개선 회의 — 2026-07-02

**형식**: 병렬 멀티에이전트 3라운드 (제안 4 → 적대적 검증 2 → 종합 1)
**참석**: llm-expert ×2, data-analyst, pm, 검증관 ×2
**베이스라인**: `chore/remove-orphan-routers` 브랜치, 작업 트리 클린, origin 대비 3커밋 ahead. 서버 테스트 **132 passed, 2 skipped GREEN** (본 회의 중 2회 독립 재실행으로 확정 — 이전 기록의 "158개"는 test 함수 수 오기).

**배경**: 챗봇 3대 축 중 응답속도(스트리밍)·기억(추출 복구)은 완료. 남은 갭 = (A) 개인화 되먹임 루프 부재, (B) 웹 MVP 몰입형 프롬프트의 prompts.py 미이식.

---

## 1. 검증에서 새로 발견된 결함 (전부 CONFIRMED, 파일:줄 실측)

회의의 최대 성과. 제안 검토 중 적대적 검증관이 발견:

| # | 결함 | 근거 | 영향 |
|---|---|---|---|
| D1 | **모든 라이브 `chat_turn` 이벤트에 user_id 부재** | `routers/chat.py:259` record_event에 user_id 인자 없음. user_id를 넣은 "올바른" 코드는 import 0건인 고아 모듈 `shared.py:204`에만 존재 | 유저 단위 분석 전면 불가. weekly_summary 푸시(scheduler.py:258-263, `user_id IS NOT NULL` 집계)는 scheduler 버그를 고쳐도 이것까지 고쳐야 작동 |
| D2 | **session_rating 전량 유실** | `models.py:176` `Literal["thumbs_up","thumbs_down"]` → 클라의 `"session_rating:$rating"`(ChatViewModel.kt:552)은 422 거부. 클라는 에러를 삼키고 무한 재시도(ChatRepository.kt:188) | 세션 별점이 DB에 단 한 건도 저장된 적 없음. 세션 피드백 텍스트도 클라에서 버려짐(ChatViewModel.kt:545 주석은 거짓) |
| D3 | **feedback room_id 전부 빈 문자열** | 클라가 roomId 미전송 (ChatApi.kt:155 기본 `""`, ChatRepository.kt:161-166 미전달) | thumbs↔응답 조인 불가는 물론 room 단위 만족도 집계마저 불가 |
| D4 | **스트리밍 경로 A/B 결과 미기록** | 배정(chat_service.py:1211)만 되고 `_record_ab_result`는 논스트림(:1021)에만 호출 | 스트리밍이 기본 경로 → model_routing 실험 데이터 사실상 미축적 |
| D5 | **d3 푸시가 유저 원문 20자를 잠금화면에 노출** | `scheduler.py:161-166` `content[:20]` | 프라이버시 사고 위험. scheduler 버그 수정과 **같은 PR로만** 배포 (분리 배포 시 그 사이 구간이 라이브 사고) |
| D6 | scheduler d3/d5/weekly/gratitude 여전히 미작동 | `scheduler.py:114,181,248,293` `from app.postgres_async import _pool` — 모듈 레벨 `_pool` 심볼 없음 → ImportError. gratitude는 등록도 안 됨(:322-325 주석) | 리텐션 푸시 4종 전멸. 데이터(users :585, messages :601, 매턴 적재 chat.py:295-333)는 준비됨 — 소비만 죽음. **메모리의 "RESOLVED 2026-06-14" 노트는 stale** |
| D7 | d5 푸시 문구가 MBTI 16종 중 8종만 정의 | scheduler.py:188-198 | 나머지 8종은 기본 문구 |
| D8 | few_shot_section이 매턴 변경 블록(episode) 뒤에 배치 | prompts.py:1148 | prefix caching 사각지대 — 갭 B 이식 때 함께 수정 기회 |

## 2. 갭 B — 웹 MVP 프롬프트 이식 (llm-expert #1, 검증 통과)

**핵심 발견**: 웹 MVP는 자유 텍스트(web_chat.py:96, :270), 프로덕션은 `[{"text","emotion"}]` JSON 강제(prompts.py:1122-1125) — **복붙 불가, 크래프트 지침만 추출해 JSON 계약 안에 재봉제**해야 함. 웹 예시를 그대로 옮기면 평문 유도 → quick_score 재생성 폭주.

**확정 사실**: text 값 안의 괄호 행동지문 `(책장을 넘기며)`는 IncrementalReplyParser와 안전 호환 (소괄호는 depth 계산 대상 아님 + in_str 처리, chat_service.py:1716-1746).

**충돌 3건과 해소** (검증 CONFIRMED):
- Scene vs 호감도 거리감 → Scene은 호칭·프레이밍만, 감정 개방도는 호감도가 게이팅
- Show-don't-tell vs 호감도 4-5 개방성(few-shot 직접 발화 prompts.py:769) → 전역이 아닌 **affinity 조건부**로 (flow/situation 분기 패턴 :1079-1117 재사용)
- MBTI 위상 → 웹의 MBTI 강등은 이식하지 않고 "라벨 자기설명 금지"만 선별 이식

**단계**: Phase 0 예시 JSON 재작성 → Phase 1 자기설명 금지(Register는 SPEECH_STYLES·호감도1 존댓말과 3중 말투 충돌 발견되어 "최저위험"에서 **하향**, 별도 조정 필요) → Phase 2 행동처리 → Phase 3 show-don't-tell(호감도 게이팅) → Phase 4 Scene(클라 협업 필요, user_role/situation 없으면 생략 = 하위호환).

**깨질 테스트**: test_content_filter.py:178-183 (AI 가드 문구 assert — prompts.py:1166-1170 유지 필수). test_stream_reply 등은 프롬프트 내용 assert 없어 안전 (검증관이 "충돌 예상" 초기 주장을 REFUTED).

## 3. 갭 A — 개인화 되먹임 (llm-expert #2, 검증 통과 + 범위 축소)

**핵심 발견**: thumbs를 응답 속성(길이/말투/화제)에 귀속시킬 **조인 키가 없음** (response_feedback에 본문·user_id 없음 postgres.py:259-267, quality_score에 message_id 없음, message_id는 클라 Room 로컬 PK, room_id마저 빈 문자열=D3). → "thumbs 기반 스타일 학습"은 스키마 수리 전 불가.

**MVP (갭 A-lite)**: 유저 발화 스타일 미러링 — conversation_history(매 요청 도착, models.py:38)에서 규칙 기반 산출(LLM 호출 0, 신규 계측 0): 메시지 길이/반말·존댓말/ㅋㅋㅎㅎ/이모티콘 빈도 → ≤100토큰 `preference_section`으로 주입. 저장은 conversation_memory 재사용(`pref::{room_id}`, upsert 패턴 memory_service.py:214-225 실재 확인).

**주입 위치 (캐시 관점 확정)**: prompts.py:1148의 compat_section과 summary_section **사이** — 세션 내 불변이라 프리픽스 캐시 유지. 갭 B와 삽입 지점이 달라 **공존 가능**. 합의된 반동적 구역 순서: affinity → Scene → compat → **preference** → summary/memory/episode.

**리스크 완화**: 캐릭터 정체성 훼손 방지 위해 preference는 하단 "약한 힌트" + "페르소나 우선" 명시. 최근 N턴 슬라이딩으로 고착 방지. 단 히스토리가 최근 10개 제한(chat_service.py:654)이라 표본 작음 유의.

## 4. 측정 계획 (data-analyst, 검증 통과)

- **A/B 프레임워크는 이미 완비** (ab_test.py 배정/기록/집계 + summary 엔드포인트). 단 유일한 실호출 model_routing은 `assign_variant(user_id=character_id)` — **캐릭터 단위 배정**. 신규 실험(personalization_v1, prompt_style_v1)은 character_id를 비워 **유저 단위**로 등록, 해시 독립이라 2×2 팩토리얼처럼 효과 분리 가능.
- 갭 A/B 효과 판정은 **서버 사이드 수정만으로 완결** (D1~D4 수리 전제). 클라 track() 연결은 수익화 퍼널용 별도 트랙 — 크리티컬 패스 아님.
- turn_count는 세션이 아닌 room 누적(story_state PK=room_id) → 세션 지표는 30분 gap 휴리스틱 + session_start 서버 이벤트 신설 필요.
- 클라 계측 실호출은 app_open, onboarding_step **2종뿐** (onboarding_complete도 상수만 존재 — Round 1 보고에서 추가 하향).
- 표본 추정 전제인 실유저 규모는 미실측 — DB row count 확인이 선행 (현재 출시 전 단계 추정: BILLING_ALLOW_MOCK=true 기본, 스토어 배포 흔적 0).

## 5. 최종 우선순위 (pm, Round 3 확정)

### P0 — "측정 파이프라인 무결성" (병렬 서브트랙)
| # | 항목 | 담당 |
|---|---|---|
| P0-1 | chat_turn에 user_id 배선 (D1) | backend-dev |
| P0-2 | scheduler `_pool`→`get_async_db()` + **d3 원문 노출 제거 같은 PR** (D5+D6) + gratitude 등록 | backend-dev (+llm-expert 문구) |
| P0-3 | 스트리밍 경로 A/B 결과 기록 (D4) | backend-dev |
| P0-4 | feedback 계약 수정: room_id 필수화 + session_rating 필드 분리 (D2+D3) — 서버/클라 **동시 배포 필수** | backend-dev + frontend-dev |
| P0-5 | analytics 이벤트 6종 콜사이트 연결 | frontend-dev |

### P1
- **갭 A-lite**: user_style 미러링 MVP (satisfaction 축 제외) — llm-expert. 신규 계측 불요로 P0와 병렬 가능
- **갭 B**: 경량 내부 평가(팀 3~5인, PROMPT_EXPERIMENT_PLAN.md 프로토콜) → 통과 시 Phase 0~2 이식 — pm+llm-expert
- d5 미정의 8종 MBTI 카피 보강 — llm-expert
- 별명짓기 D1 훅 스펙 (P0-1 데이터 확보 후 재확정) — pm

### P2
- 갭 A-full (satisfaction 축): P0-4 완료 + 실데이터 1~2주 축적 후
- 웹 MVP 외부 5~10인 정식 테스트 (경량 평가로 1차 대체)
- Play Billing 실연동 (출시 임박 시), lora_pipeline.py 이동 (트리비얼)

### 스프린트 배치
- **Sprint N**: backend-dev P0-1~4(서버측), frontend-dev P0-4(클라)+P0-5, llm-expert d3/d5 문구+갭A-lite 설계
- **Sprint N+1**: llm-expert 갭A-lite 구현+갭B 경량평가+d5 카피, backend-dev weekly 실데이터 검증, pm 갭B 착수 판정+별명짓기 스펙

## 6. 검증에서 기각·수정된 주장 (기록용)

| 주장 | 판정 |
|---|---|
| pm: "갭 A는 계측 없이 시작 불가" | **REFUTED** — 정확한 명제는 "계측 없이 효과 검증 불가". MVP는 오늘 구현 가능. pm이 Round 3에서 수용·정정 |
| llm#1: "Register 이식은 최저위험" | 하향 — SPEECH_STYLES(prompts.py:654-658)·호감도1 존댓말(:674)과 3중 말투 충돌 |
| 검증 의뢰 시 전제 "스트리밍 chat_turn은 user_id 있음" | REFUTED — 그 코드는 고아 shared.py. 라이브는 전 경로 user_id 없음 |
| 사전 브리핑 "테스트 ~158개" | 정정 — 실측 132 passed 2 skipped (def test_ 함수 수와 실행 수의 혼동) |
| 메모리 노트 "scheduler import bug RESOLVED", "chat.py user_id=_uid 전달" | **둘 다 stale** — 현 브랜치에 버그 현존 / messages INSERT와 chat_turn 이벤트를 혼동한 기록 |

## 7. 다음 회의 안건
- P0 완료 후 weekly/d3/d5 푸시 실발송 검증 결과
- 갭 B 경량 평가 점수 → 이식 go/no-go
- 실유저 규모 실측 → A/B 표본 계획 확정
