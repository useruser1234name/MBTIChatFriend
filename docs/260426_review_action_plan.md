# MBTIChatFriend Review Action Plan

**Date**: 2026-04-26
**Scope**: `server/`, `android/`
**Goal**: 리뷰에서 확인된 데이터 격리 문제와 Android-서버 계약 불일치를 우선 해소하고, 바로 검증까지 마친다.

## 1. 우선순위

1. 서버 메모리/RAG 저장소를 사용자 스코프로 격리한다.
2. 메모리 조회/삭제 API의 권한 검증과 삭제 범위를 정정한다.
3. `session/start`의 Android-서버 계약을 일치시킨다.
4. Windows 환경에서 `VectorStore` 테스트가 정리 단계에서 잠기지 않도록 종료 경로를 보완한다.
5. 서버 테스트와 Android 컴파일로 회귀를 확인한다.

## 2. 작업 항목

### 2.1 서버 스코프 정리
- 대화별 기본 식별자를 `uid + character_id` 기준으로 일관되게 만든다.
- 요약/사실 메모리 키와 Chroma 컬렉션 키에 같은 스코프를 사용한다.
- 기존 `character_name::nickname` 기반 데이터는 읽기 시 fallback 하도록 남겨 둔다.

### 2.2 메모리 조회/삭제 정정
- 메모리 조회 API는 인증 사용자 기준으로만 스코프를 계산한다.
- `character_id`를 함께 받을 수 있게 하여 조회/집계 기준을 정확히 맞춘다.
- 삭제 API는 서버에서 계산한 스코프 키로 `conversation_memory`, `response_feedback`, `vector_store`까지 정리한다.
- Android 삭제 요청도 `nickname` 포함 및 로컬 메모리/일기/피드백 정리까지 맞춘다.

### 2.3 `session/start` 계약 정정
- Android 요청에 현재 호감도 점수, 레벨, 마지막 대화 시각을 포함한다.
- Android 응답 모델은 서버의 `adjusted_score`, `original_score`, `days_inactive`에 맞춘다.
- ViewModel에서 서버 응답을 실제 점수 변화량으로 환산해 UI에 반영한다.

### 2.4 검증
- 서버: 관련 테스트 추가/수정 후 `python -m pytest -q --basetemp=.pytest-tmp`
- Android: `./gradlew.bat :app:compileDebugKotlin`

## 3. 완료 기준

- 사용자 A와 B가 같은 로컬 `character_id`를 가져도 서버 메모리/RAG/삭제 범위가 섞이지 않는다.
- 메모리 조회는 인증 사용자 스코프 밖 데이터를 읽지 않는다.
- `session/start`가 더 이상 조용히 실패하지 않고 실제 값으로 동작한다.
- `test_vector_store.py`가 Windows 정리 단계에서 잠기지 않는다.
