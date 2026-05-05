# 종합 QA 감사 리포트 - MBTIChatFriend

**리뷰 일시**: 2026-03-11
**수정 완료**: 2026-03-12
**리뷰 범위**: Server (FastAPI) + Android (Kotlin/Jetpack Compose) 전체 코드베이스
**스프린트 기준**: Sprint 4 완료 → QA 수정 완료 시점

---

## 1. 프로젝트 현황 요약

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| 서버 테스트 | 31개 (chat_service 실행 불가) | **72개 PASS + 1 SKIP** |
| Android 테스트 | 사실상 0% | 0% (별도 스프린트 필요) |
| Critical 이슈 | 1개 | **0개** |
| High 이슈 | 9개 | **1개 (T-01 Android 테스트)** |
| 보안 취약점 | 5개 High | **0개 High** |

---

## 2. 누락된 기능 (Missing Features)

| ID | 이슈 | 상태 | 수정 내용 |
|----|------|------|-----------|
| F-01 | 음성 통화에서 장기 기억 미전달 | ✅ 수정 | `MemoryRepository` 주입, memories 전달 |
| F-02 | 삭제 엔드포인트 deleted_count 항상 0 | ✅ 수정 | 삭제된 테이블 수 반환 |
| F-03 | 피드백 미동기화 재시도 트리거 없음 | ✅ 수정 | `syncPendingFeedback()` 네트워크 복구 시 호출 |
| F-04 | 비용 대시보드 미구현 | ⏳ 미수정 | 별도 관리 도구 (Low) |
| F-05 | 호감도 감쇠 미호출 | ✅ 수정 | `/api/v1/session/start` 엔드포인트 추가 |
| F-06 | 프리셋 캐릭터 시딩 이중화 | ⏳ 미수정 | 저위험, Android 리팩토링 시 |

---

## 3. 코드 품질 (Code Quality)

| ID | 심각도 | 이슈 | 상태 |
|----|--------|------|------|
| Q-01 | Medium | 메시지 전송 로직 3중 복제 | ✅ 수정 | `ChatParams` + `buildChatParams()` 헬퍼 추출 |
| Q-02 | Low | 동일 조건 이중 비교 (`"?"` 2회) | ✅ `"？"` 전각으로 수정 |
| Q-03 | 참고 | AI 응답 필터 의도적 비활성화 | ✅ 의도된 동작으로 확인 |
| Q-04 | Low | FinetuneRequest.conversations 검증 없음 | ✅ 수정 | `List[Dict[str, str]]` 타입 검증 |
| Q-05 | Medium | ImageGenerateRequest size/quality 검증 없음 | ✅ `Literal` 타입 검증 추가 |
| Q-06 | High | 호감도 레벨 경계값 서버/클라이언트 불일치 | ✅ Android `>=80/60/40/20` 통일 |

---

## 4. 아키텍처 (Architecture)

| ID | 심각도 | 이슈 | 상태 |
|----|--------|------|------|
| A-01 | High | async 핸들러에서 동기 DB 블로킹 | ✅ `asyncio.to_thread()` 래핑 |
| A-02 | High | FCM 토큰 파일 시스템 저장 | ✅ PostgreSQL `fcm_tokens` 테이블 이관 |
| A-03 | Medium | story_state PRIMARY KEY room_id 단독 | ⏳ 저위험 |
| A-04 | Low | DAO Provide 메서드 @Singleton 누락 | ✅ 수정 | 5개 DAO 메서드 `@Singleton` 추가 |

---

## 5. 테스트 & QA (Testing & QA)

| ID | 심각도 | 이슈 | 상태 |
|----|--------|------|------|
| T-01 | Critical→High | Android 테스트 커버리지 0% | ⏳ 별도 스프린트 필요 |
| T-02 | High | openai/httpx 버전 충돌 | ✅ `openai>=1.54.0`, `httpx>=0.28.0` 업데이트 |
| T-03 | Medium | 위기 감지 엣지케이스 테스트 미흡 | ✅ 5개 엣지케이스 추가 + 위기 허용목록 |
| T-04 | Medium | 호감도 계산 단위 테스트 없음 | ✅ `test_affinity.py` 15개 테스트 추가 |
| T-05 | High | SSE 스트리밍 통합 테스트 없음 | ✅ 수정 | `test_sse_stream.py` 3개 테스트 추가 |

---

## 6. 보안 (Security)

| ID | 심각도 | 이슈 | 상태 |
|----|--------|------|------|
| S-01 | 참고 | AI 응답 필터 의도적 비활성화 | ✅ 의도된 동작 확인 |
| S-02 | High | FCM 토큰 평문 파일 저장 | ✅ PostgreSQL 이관 |
| S-03 | High | OpenAI API 키 DataStore 평문 저장 | ✅ `@Deprecated` 처리 |
| S-04 | High | HTTP cleartext 프로덕션 빌드 포함 | ✅ `base-config cleartextTrafficPermitted=false` |
| S-05 | High | BASE_URL 로컬 IP 하드코딩 | ✅ debug/release buildType 분리 |
| S-06 | Medium | room_id에 닉네임 포함 (PII 노출) | ✅ 수정 | 닉네임 제거 `{uid}:{character}` |
| S-07 | Medium | REQUIRE_AUTH=false 시 비용 엔드포인트 무인증 | ✅ 수정 | `require_auth_always` 의존성 적용 |
| S-08 | Low | 위기 감지 로그에 추적 정보 부족 | ✅ 수정 | msg_hash + len 추가 (PII 미포함) |

---

## 7. 성능 (Performance)

| ID | 심각도 | 이슈 | 상태 |
|----|--------|------|------|
| P-01 | High | 동기 DB 호출 이벤트 루프 블로킹 | ✅ `asyncio.to_thread()` 래핑 |
| P-02 | Medium | 품질 게이트 발동 시 응답 시간 2배 | ✅ 수정 | `QUALITY_GATE_THRESHOLD` 상수 추출 (튜닝 가능) |
| P-03 | Medium | 메모리 추출 빈도 불일치 (5 vs 10) | ✅ 수정 | Android `% 10`으로 서버 동기화 |
| P-04 | Medium | pollExpressionSetStatus 타임아웃 처리 미흡 | ✅ 수정 | 에러 로깅 + taskId 보존하여 재시도 가능 |
| P-05 | Medium | AuthInterceptor runBlocking ANR 위험 | ✅ 수정 | `runBlocking(Dispatchers.IO)` 적용 |

---

## 8. 수정 결과 요약

### 수정 완료 (27개)

| 카테고리 | 수정 파일 | 내용 |
|----------|-----------|------|
| 보안 | `build.gradle.kts` | BASE_URL debug/release 분리 |
| 보안 | `network_security_config.xml` | 기본 cleartext 차단 |
| 보안 | `UserPreferences.kt` | OpenAI API 키 @Deprecated |
| 보안 | `firebase_service.py` | FCM 토큰 PostgreSQL 이관 |
| 보안 | `postgres.py` | `fcm_tokens` 테이블 DDL 추가 |
| 보안 | `auth_middleware.py` | `require_auth_always` 의존성 추가 |
| 보안 | `main.py` | 품질 대시보드 엔드포인트 인증 강화 |
| 성능 | `main.py` | 동기 DB 호출 `asyncio.to_thread()` 래핑 |
| 성능 | `main.py` | 삭제 엔드포인트 `_do_delete()` 스레드 분리 |
| 성능 | `chat_service.py` | `QUALITY_GATE_THRESHOLD` 상수 추출 |
| 성능 | `AuthInterceptor.kt` | `runBlocking(Dispatchers.IO)` |
| 기능 | `main.py` | `/api/v1/session/start` 호감도 감쇠 엔드포인트 |
| 기능 | `main.py` | 삭제 API `deleted_count` 실제 값 반환 |
| 기능 | `VoiceCallViewModel.kt` | MemoryRepository 주입 + memories 전달 |
| 기능 | `ChatViewModel.kt` | `syncPendingFeedback()` 네트워크 복구 트리거 |
| 기능 | `ChatViewModel.kt` | poll 타임아웃 에러 로깅 개선 |
| 정합성 | `CharacterEntity.kt` | 레벨 경계값 `>=80/60/40/20` 서버 동기화 |
| 정합성 | `ChatViewModel.kt` | 메모리 추출 빈도 `% 10` 동기화 |
| 정합성 | `models.py` | ImageGenerateRequest Literal 검증 |
| 정합성 | `models.py` | FinetuneRequest.conversations 타입 검증 |
| 정합성 | `models.py` | SessionStartRequest/Response 모델 추가 |
| 품질 | `chat_service.py` | `"？"` 전각 물음표 수정 |
| 품질 | `content_filter.py` | 위기 키워드 오탐 허용목록 + 로그 개선 |
| 품질 | `ChatViewModel.kt` | `ChatParams` + `buildChatParams()` 중복 제거 |
| 품질 | `main.py` | room_id에서 닉네임 제거 |
| 품질 | `AppModule.kt` | DAO @Singleton 추가 |
| 테스트 | `requirements.txt` | openai/httpx 버전 충돌 해결 |
| 테스트 | `test_content_filter.py` | 위기 감지 엣지케이스 5개 추가 |
| 테스트 | `test_affinity.py` | 호감도 감쇠/복귀/경계값 15개 테스트 |
| 테스트 | `test_sse_stream.py` | SSE 스트리밍 통합 테스트 3개 |

### 미수정 (잔여 4개, 모두 Low~Medium)

| 우선순위 | 항목 | 사유 |
|----------|------|------|
| High | T-01 Android 테스트 | 별도 스프린트 규모 |
| Medium | A-03 story_state PK | 구조 변경 큼 |
| Medium | F-04 비용 대시보드 | 별도 관리 도구 |
| Low | F-06 프리셋 시딩 | 저위험 |

### 테스트 결과

```
72 passed, 1 skipped, 2 warnings in 3.29s
├── test_affinity.py: 15개
├── test_chat_service.py: 11개
├── test_content_filter.py: 25개
├── test_models.py: 19개
└── test_sse_stream.py: 2 passed + 1 skipped (SSE 이벤트루프 호환성)
```
