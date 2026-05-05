# MBTIChatFriend 프로젝트 종합 리뷰 리포트

**검토일**: 2026-03-09 | **검토 범위**: Android 클라이언트 + FastAPI 서버 전체

---

## 1. 프로젝트 현황 요약

| 항목 | 현황 |
|------|------|
| 전체 완성도 | 약 72% (MVP 수준, 프로덕션 배포 전 필수 수정 사항 다수) |
| Android 화면 수 | 11개 (Splash, Login, Onboarding 5개, Home, Chat, Profile, Gallery, Diary, VoiceCall, Settings) |
| Room DB 버전 | v7 (마이그레이션 체계 잘 구축됨) |
| 서버 기능 | 채팅(SSE/REST), 메모리 추출, 일기 생성, 이미지 생성, 파인튜닝, 피드백, 품질 대시보드 |
| 테스트 | 사실상 0% (Android: 예시 계측 테스트 1개, Server: 테스트 파일 없음) |
| 치명적 보안 이슈 | 콘텐츠 필터 완전 비활성화 상태로 코드 존재 |

---

## 2. 누락된 기능 (Missing Features)

### Critical (프로덕션 배포 전 필수)

**C1. 콘텐츠 필터 재활성화**
- `server/app/content_filter.py:26-30`에서 `check_content()`가 항상 `True, ""`를 반환
- `chat_service.py:357-365`, `510-518`에서 AI 입출력 필터 주석 처리
- 프롬프트 인젝션, 유해 콘텐츠 생성, API 비용 폭증 위험

**C2. 파인튜닝 모델 영속성 취약**
- `finetune_service.py:19-52`에서 파인튜닝 모델 매핑을 JSON 파일에 저장
- 멀티 서버 환경에서 race condition, 재시작 시 데이터 유실
- PostgreSQL로 마이그레이션 필요

**C3. PostgreSQL 동기 블로킹 호출**
- `postgres.py:31-45`의 `get_conn()`이 동기 `psycopg.connect()` 사용
- FastAPI async 엔드포인트에서 이벤트 루프 블로킹
- `asyncpg` 또는 `psycopg` 3 비동기 연결로 교체 필요

**C4. SseClient의 Done 이벤트 파싱 누락**
- `SseClient.kt:95-99`에서 `affinity_delta`만 파싱
- `night_diary_generated`, `next_hook`, `next_goal`, `room_id` 필드 무시
- `SseEvent.Done` 데이터 클래스에 누락 필드 추가 필요

### Important (빠른 시일 내 필요)

**I1. 인증 강제 적용 일관성 없음**
- `REQUIRE_AUTH=false` 기본값으로 비용 발생 API도 인증 없이 호출 가능
- `/api/v1/finetune/start`, `/api/v1/image/generate` 등

**I2. OpenAI API 키 클라이언트 저장**
- `UserPreferences.kt:37-38`에서 `OPENAI_API_KEY`를 DataStore에 저장
- API 키는 서버에서만 관리되어야 함

**I3. 다양성 체크 버그**
- `quality_service.py:181-196`에서 `ai_response` 필드가 저장되지 않아 `past_texts`가 항상 빈 리스트
- 다양성 체크가 무용지물

**I4. 오프라인 대기 메시지 재전송 시 SSE 미사용**
- `ChatViewModel.kt:144-165`의 오프라인 플러시가 REST API만 사용

**I5. Docker Compose 프로덕션 부적합**
- 매 시작마다 `pip install` 실행, `--reload` 플래그 사용
- Dockerfile 작성 및 레이어 캐시 활용 필요

### Nice-to-have

- **N1**: 캐릭터 삭제 시 서버 ChromaDB 컬렉션 정리 미연동
- **N2**: SSE 실패 시 지수 백오프 재연결
- **N3**: 호감도 레벨업 푸시 알림
- **N4**: 파인튜닝 진행 상태 폴링 UI

---

## 3. 코드 품질 (Code Quality)

### Android

**Q1. ChatViewModel 책임 과중 (SRP 위반)**
- 554줄에 메시지 전송, SSE/REST 폴백, 오프라인 큐, 레벨업, 표정 폴링, 피드백 모두 처리
- `ExpressionSetViewModel`, `AffinityViewModel`로 분리 권장

**Q2. 호감도 업데이트 로직 3곳 반복 (DRY 위반)**
- `sendWithSse:323-331`, `fallbackToRest:395-404`, `retrySend:465-471`
- `private fun handleAffinityDelta(delta: Int)`로 추출 필요

**Q3. HomeViewModel에서 DAO 직접 접근**
- `HomeViewModel.kt:29`에서 `MessageDao` 직접 주입 (Repository 패턴 위반)

**Q4. pollExpressionSetStatus() 무한 루프 위험**
- `ChatViewModel.kt:517-542`의 `while(true)` 폴링에 최대 시도 횟수 미설정

**Q5. DataStore에서 매 전송마다 읽기**
- 매 메시지 전송마다 `prefs.nickname.first()`, `prefs.userMbti.first()` 2회 호출
- `StateFlow`로 캐싱 권장

### Server

**Q6. 호감도 계산 이중 구조 복잡**
- LLM 결과가 0이면 키워드로 덮어쓰는 로직이 중립 메시지에서 오작동 가능

**Q7. 야간 일기 생성 직렬 실행**
- `_run_chat_pipeline()`에서 `await`로 일기 생성 → 마지막 메시지 응답 지연
- `asyncio.create_task()`로 분리 권장

**Q8. 파이썬 타입 힌트 불완전**
- `Optional` 없이 `None` 기본값 사용

---

## 4. 아키텍처 (Architecture)

### Android

**A1. 단일 Hilt 모듈**
- `AppModule.kt` 하나에 모든 의존성 → `NetworkModule`, `DatabaseModule`, `RepositoryModule` 분리 권장

**A2. Navigation 아키텍처 혼재**
- `AppNavHost.kt`에서 BottomSheet를 NavHost에서 직접 관리

**A3. 상태 관리 일관성 부재**
- ChatViewModel: `mutableStateOf`, HomeViewModel: `MutableStateFlow` 혼합 → `StateFlow` 통일 권장

### Server

**A4. FastAPI 서비스 계층 없음**
- `main.py`가 라우터이자 비즈니스 로직 오케스트레이터 → `ChatService` 클래스 분리 필요

**A5. 인메모리 상태 저장**
- `finetune_service.py`, `image_service.py`, `story_state_store.py`가 메모리 의존
- 서버 재시작/다중 인스턴스 시 데이터 유실 → PostgreSQL 마이그레이션

**A6. ChromaDB 단일 프로세스 제한**
- `PersistentClient` 사용으로 멀티 워커 환경에서 파일 락 충돌
- `chromadb.HttpClient`로 별도 Chroma 서버 분리 필요

---

## 5. 테스트 & QA

현재 상태: 테스트 커버리지 사실상 0%

### 우선 작성 테스트

**T1. 서버 핵심 비즈니스 로직**
```python
- test_calculate_affinity_delta_negation()  # "좋아 안해" 부정 처리
- test_calculate_compatibility_all_types()  # 16x16 MBTI 조합
- test_parse_reply_malformed_json()         # JSON 파싱 폴백
- test_content_filter_blocked_words()       # 금칙어 차단
- test_chat_endpoint_without_auth()         # REQUIRE_AUTH=true 시 401
```

**T2. Android ViewModel 단위 테스트**
```kotlin
- testSendMessage_offline_saves_pending()
- testSendMessage_online_triggers_sse()
- testAffinityLevelUp_emitsEvent()
- testPollExpressionSet_stopsOnCompleted()
- testRetrySend_marksFailedAfterMaxRetry()
```

**T3. 엣지 케이스**
- 메시지 길이 1000자 초과 시 서버 검증
- MBTI 형식 오류 시 서버 400 응답
- ChromaDB 없을 때 RAG 없이 정상 응답
- 네트워크 단절 후 복구 시 오프라인 큐 플러시
- 호감도 100점 초과 시 레벨 캡 처리

---

## 6. 보안 (Security)

### 심각 (Critical)

**S1. 콘텐츠 필터 비활성화**
- 모든 입력이 그대로 OpenAI에 전달 → 프롬프트 인젝션, 유해 콘텐츠, API 비용 폭증

**S2. API 비용 발생 엔드포인트 느슨한 인증**
- `REQUIRE_AUTH=false` 기본값으로 비용 API 무인증 호출 가능

### 높음 (High)

**S3. OpenAI API 키 클라이언트 저장**
- 서버에서만 관리해야 할 키가 클라이언트 DataStore에 저장

**S4. 프롬프트 인젝션 취약점**
- 사용자 닉네임이 프롬프트에 직접 삽입 (`prompts.py:1050`)
- nickname에 허용 문자 패턴 검증 필요: `pattern=r"^[\w가-힣\s]+$"`

**S5. room_id 예측 가능성**
- `{uid}:{character_id}:{nickname}` 형식으로 추측 가능
- UUID v4로 생성 후 DB 저장 방식 권장

### 중간 (Medium)

**S6. Rate Limit이 IP 기반** - 리버스 프록시 뒤에서 프록시 IP가 키가 됨
**S7. 로그에 민감 정보 노출** - LLM 호감도 분석 이유에 사용자 메시지 포함 가능

---

## 7. 성능 (Performance)

### Android

**P1. N+1 쿼리 문제**
- `HomeViewModel.kt:48-63`에서 캐릭터마다 `getLastMessage()` 루프 호출
- 단일 배치 쿼리 `getLastMessagesForAllCharacters()` 추가 필요

**P2. pollExpressionSetStatus() 타임아웃 없음**
- 무한 루프로 10초마다 서버 호출, 태스크 유실 시 영원히 폴링

### Server

**P3. 매 채팅 턴마다 LLM 2~4번 호출**
1. `analyze_affinity_with_llm()` - gpt-4o-mini
2. `generate_reply()` - gpt-4o / gpt-4o-mini
3. `quick_score()` - gpt-4o-mini (품질 게이트)
4. `score_response_async()` - gpt-4o-mini (백그라운드)
- 호감도 분석과 응답 생성을 단일 API 호출로 통합 권장

**P4. RAG 검색에서 매번 컬렉션 목록 조회**
- 매 채팅마다 `list_collections()` 호출 → 인메모리 캐시로 대체

**P5. SSE 딜레이 중복 적용**
- 서버(`asyncio.sleep`)와 클라이언트(`delay`) 양쪽에서 딜레이 적용
- 서버 딜레이 제거, 클라이언트에서만 적용

---

## 8. AI/ML 모델 방향성

**M1. 파인튜닝 데이터 수집 전략**
```
1단계: 실제 사용자 대화 수집 (thumbs_up 받은 것만)
2단계: gpt-4o로 고품질 합성 데이터 생성 (MBTI × 호감도 × 시나리오)
3단계: 합성 80% + 실제 20% 비율로 첫 파인튜닝
4단계: 사용자 피드백 반영 점진적 개선
```

**M2. MBTI별 대화 특성 강화**
- 현재 few_shot_examples가 그룹(NT/NF/ST/SF) 단위 각 2개
- 16개 각 MBTI 타입별 최소 5-10개 고품질 예시 필요
- 특히 INTJ "전략적 쿨함", ENFP "흥분 주제전환", ISFJ "세심한 배려" 등

**M3. 호감도 시스템 정밀화**
- LLM 결과 0일 때 키워드 대체 로직이 중립 메시지에서 오작동
- 신뢰도 기반 결합: LLM 실패 시에만 키워드 폴백, 성공 시 LLM 단독

**M4. 대화 연속성 강화 (스토리 아크)**
- `story_state_store.py`의 `next_hook`/`next_goal` 시스템이 서버에만 구현
- Android에서 SSE Done의 `nextHook`을 다음 채팅 세션에 전달하여 연속성 확보

---

## 9. UX/UI

**U1. 온보딩 완료 사용자 재로그인 시 온보딩 반복**
- `isOnboardingDone` 상태 확인하여 완료 사용자는 바로 Home으로 이동

**U2. 메시지 전송 실패 이유 미표시**
- 네트워크/서버/콘텐츠필터 구별하여 적절한 안내 필요

**U3. 빈 Gallery 상태 안내 부족**

**U4. VoiceCall TTS 품질**
- MBTI 성격에 맞는 목소리 톤(속도, 피치) 설정 기능 제안

---

## 10. DevOps/인프라

**D1. CI/CD 파이프라인 없음**
- GitHub Actions: Android lint/test/APK빌드, Server flake8/pytest

**D2. 헬스체크 미흡**
- PostgreSQL, ChromaDB, OpenAI API 상태 포함 상세 헬스체크 필요

**D3. 로깅 구조화 없음**
- `structlog` 또는 `python-json-logger`로 JSON 구조화 로그 전환

**D4. ChromaDB 볼륨 마운트 없음**
- 컨테이너 재시작 시 모든 RAG 기억 초기화

---

## 11. 우선순위 액션 플랜

### 즉시 (1주 이내)
1. content_filter.py 활성화 + chat_service.py 입출력 필터 복원
2. SseClient.Done 이벤트 파싱 보완 (누락 필드 추가)
3. quality_service.py 다양성 버그 수정 (ai_response 저장)
4. pollExpressionSetStatus() 최대 시도 횟수 제한 (30회)
5. ChatViewModel 호감도 업데이트 로직 중복 제거

### 단기 (2-4주)
6. PostgreSQL 비동기 연결 전환 (asyncpg)
7. 파인튜닝 모델 저장 PostgreSQL 마이그레이션
8. nickname 입력값 서버 검증 강화 (프롬프트 인젝션 방어)
9. HomeViewModel N+1 쿼리 해결
10. Docker Compose 개선 (Dockerfile, --reload 제거, Chroma 볼륨)

### 중기 (1-2개월)
11. 서버 단위 테스트 작성 (pytest, 커버리지 70% 목표)
12. Android ViewModel 단위 테스트
13. 스토리 아크(next_hook/next_goal) Android 연동
14. ChromaDB 별도 서버 분리
15. CI/CD 파이프라인 구축

### 장기 (3개월+)
16. MBTI별 파인튜닝 데이터셋 구축 (16 MBTI × 5 레벨 × 10+ 시나리오)
17. 호감도 계산 A/B 테스트
18. 다중 인스턴스 스케일아웃 대비 (인메모리 상태 전체 PostgreSQL 이전)

---

*리뷰 팀: Architect, Code Reviewer, QA Engineer, Security Auditor, Performance Analyst, UX Reviewer*
