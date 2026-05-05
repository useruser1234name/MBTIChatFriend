# Sprint 3 QA Report - 품질/안전

> Sprint 기간: Week 3
> 테스트일: 2026-03-11

---

## 1. 단위 테스트

### 1.1 테스트 파일 현황

| 파일 | 테스트 수 | 대상 모듈 |
|------|-----------|-----------|
| `tests/test_content_filter.py` | 15개 | content_filter.py (필터, 위기감지, 프롬프트) |
| `tests/test_models.py` | 17개 | models.py (ChatRequest 검증, 입력 제한) |
| `tests/test_chat_service.py` | 10개 | chat_service.py (MBTI 그룹, 복잡도 분류) |
| **합계** | **42개** | 핵심 비즈니스 로직 |

### 1.2 테스트 커버리지 항목

| 테스트 영역 | 항목 | 상태 |
|-------------|------|------|
| 콘텐츠 필터 | 정상 메시지 통과 | ✅ |
| 콘텐츠 필터 | 성적/폭력/혐오 차단 | ✅ |
| 콘텐츠 필터 | 영어 패턴 차단 | ✅ |
| 콘텐츠 필터 | 허용목록 오탐 방지 | ✅ |
| 위기 감지 | Tier1 즉시 키워드 | ✅ |
| 위기 감지 | Tier2 부드러운 키워드 | ✅ |
| 위기 감지 | 정상 메시지 미감지 | ✅ |
| 안전 프롬프트 | 비어있지 않음, 가이드라인 포함 | ✅ |
| 입력 검증 | message min/max 길이 | ✅ |
| 입력 검증 | MBTI 유효성 (16종 전체) | ✅ |
| 입력 검증 | XSS 살균 | ✅ |
| 입력 검증 | conversation_history 50턴 제한 | ✅ |
| 입력 검증 | speech_style/relationship enum | ✅ |
| MBTI 분류 | 16종 전체 그룹 분류 정확성 | ✅ |
| MBTI 분류 | 잘못된 입력 폴백 | ✅ |
| 복잡도 분류 | simple 패턴 (인사, 반응) | ✅ |
| 복잡도 분류 | complex 패턴 (긴 메시지) | ✅ |

---

## 2. 대화 기록 삭제 API

### 2.1 엔드포인트 명세

| 항목 | 값 |
|------|-----|
| Method | POST |
| Path | `/api/v1/data/delete-conversation` |
| Auth | Firebase Token 필수 |
| Rate Limit | 5/분 |
| Request | `DeleteConversationRequest` (room_id, character_id) |
| Response | `DeleteConversationResponse` (deleted_count, status) |

### 2.2 삭제 범위

| 테이블 | room_id 기반 | character_id 기반 | 상태 |
|--------|:----------:|:-----------:|------|
| story_state | ✅ | ✅ | ✅ |
| diary_entries | ✅ | ✅ | ✅ |
| metric_events | ✅ | ✅ | ✅ |
| response_feedback | ✅ | ✅ | ✅ |
| conversation_memory | ✅ (LIKE) | - | ✅ |

### 2.3 테스트 케이스

| 테스트 케이스 | 기대 동작 | 상태 |
|---------------|-----------|------|
| room_id로 삭제 | 해당 room의 모든 데이터 삭제 | ✅ |
| character_id로 삭제 | 해당 캐릭터의 모든 데이터 삭제 | ✅ |
| room_id + character_id 모두 빈값 | 400 에러 | ✅ |
| 인증 없이 요청 | 401 에러 | ✅ |
| 삭제 이벤트 기록 | data_deletion 이벤트 로깅 | ✅ |

---

## 3. 변경 파일 목록

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `server/tests/__init__.py` | 신규 | 테스트 패키지 초기화 |
| `server/tests/test_content_filter.py` | 신규 | 콘텐츠 필터 15개 테스트 |
| `server/tests/test_models.py` | 신규 | 입력 검증 17개 테스트 |
| `server/tests/test_chat_service.py` | 신규 | 핵심 로직 10개 테스트 |
| `server/app/models.py` | 수정 | DeleteConversation 모델 추가 |
| `server/app/main.py` | 수정 | 삭제 엔드포인트 추가 |
| `server/requirements.txt` | 수정 | pytest, pytest-asyncio 추가 |

---

## 4. 미완료 / 향후 과제

| 항목 | 사유 | 후속 조치 |
|------|------|-----------|
| ChromaDB 벡터 삭제 | vector_store.py에 삭제 API 추가 필요 | Sprint 4 |
| Android Room DB 삭제 | DAO에 deleteByCharacterId() 추가 필요 | Sprint 4 |
| 인간 테스트 (수동) | 실 서버 환경에서 E2E 테스트 필요 | 별도 QA 세션 |
