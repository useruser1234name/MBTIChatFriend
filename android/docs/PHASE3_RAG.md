# Phase 3: RAG + Vector DB (ChromaDB)

## 개요

Phase 2의 키-값 기억 시스템에 **시맨틱 검색(RAG)**을 추가합니다.
현재 대화 주제와 의미적으로 가장 관련 있는 기억을 골라 AI에 주입하여
더 자연스럽고 맥락에 맞는 응답을 생성합니다.

## 아키텍처

```
Server
  └─ vector_store.py (ChromaDB PersistentClient)
       ├─ upsert_memories()  ← 기억 추출 시 임베딩 저장
       └─ search_relevant()  ← 채팅 시 시맨틱 검색
  └─ chat_service.py
       ├─ extract_memories() → upsert_memories()
       └─ generate_reply()   → search_relevant() → system_prompt
```

## 동작 흐름

```
[기억 추출 시]
LLM 추출 → memories 리스트
    └─ ChromaDB upsert (text-embedding-3-small 임베딩)

[채팅 시]
사용자 메시지 →
    ├─ Phase 2: Room DB에서 전체 기억 로드
    ├─ ChromaDB.query(query=사용자메시지, n_results=3)
    │   → 의미적으로 가장 유사한 기억 top-3 반환
    ├─ 두 기억 집합 합산 (중복 제거)
    └─ system_prompt에 주입 → LLM 응답 생성
```

## ChromaDB 설정

### 설치

`requirements.txt`에 자동 포함되어 있습니다:

```
chromadb==0.5.23
```

### 임베딩 모델

- **모델**: `text-embedding-3-small` (OpenAI)
- **비용**: 약 $0.00002 / 1K tokens (매우 저렴)
- **API 키 없음**: Chroma 기능이 자동으로 비활성화되고 Phase 2 기억만 사용됩니다

### 데이터 저장 위치

```
server/chroma_db/          ← 임베딩 데이터 (자동 생성)
```

> `.gitignore`에 `chroma_db/` 추가를 권장합니다.

### 컬렉션 구조

캐릭터별 독립 컬렉션 (`char_{character_id}`):

```
char_1/  → 캐릭터 ID 1의 임베딩
char_2/  → 캐릭터 ID 2의 임베딩
...
```

## vector_store.py API

```python
from app.vector_store import get_store

store = get_store()  # None이면 ChromaDB 미사용

# 기억 저장 (임베딩)
store.upsert_memories(character_id="1", memories=[
    MemoryItem(key="직업", value="대학생"),
    MemoryItem(key="좋아하는 음식", value="라멘"),
])

# 시맨틱 검색
results = store.search_relevant(character_id="1", query="오늘 학교에서...", n_results=3)
# → ["직업: 대학생", "좋아하는 음식: 라멘", ...]

# 캐릭터 삭제 시
store.delete_character(character_id="1")
```

## Android 변경사항

RAG는 서버 사이드 전용으로, Android 코드 변경은 `character_id` 전달만 추가됩니다:

```kotlin
// ChatRequest에 character_id 포함
ChatRequest(
    ...,
    characterId = characterId.toString()
)
```

## 성능 고려사항

| 항목 | 값 |
|------|-----|
| 임베딩 지연 | ~100-300ms (첫 upsert 시) |
| 검색 지연 | ~50-150ms |
| 저장 공간 | 기억 1개당 ~1KB |
| 최대 결과 | n_results=3 (조정 가능) |

## 비활성화 방법

RAG 없이 Phase 2만 사용하려면 `vector_store.py`에서:

```python
CHROMA_AVAILABLE = False  # 강제 비활성화
```

또는 OpenAI API 키 없이 실행하면 자동으로 비활성화됩니다.
