# Phase 2: 장기 기억 시스템

## 개요

AI 캐릭터가 대화에서 사용자의 개인 정보(직업, 취미, 고민 등)를 추출하여
다음 대화에서도 자연스럽게 기억하고 활용하는 기능입니다.

## 아키텍처

```
Android (클라이언트)                      Server (FastAPI)
──────────────────                        ─────────────────
MemoryEntity (Room DB)                    /api/v1/memory/extract
MemoryDao                                   └─ LLM으로 key-value 추출
MemoryRepository                          /api/v1/chat/stream
ChatViewModel                               └─ memories → system prompt
  └─ 5번마다 추출 트리거                   prompts.py
  └─ 매 메시지마다 기억 로드                └─ build_system_prompt(memories=...)
```

## 데이터 모델

### Android - MemoryEntity

```kotlin
@Entity(tableName = "memories")
data class MemoryEntity(
    val characterId: Long,
    val key: String,      // 예: "직업", "좋아하는 음식"
    val value: String,    // 예: "대학생", "라멘"
    val createdAt: Long
)
```

### Server - MemoryItem

```python
class MemoryItem(BaseModel):
    key: str    # 기억 항목 이름
    value: str  # 기억 항목 값
```

## 동작 흐름

```
사용자 메시지 전송
    │
    ├─ userMessageCount++
    │
    ├─ [userMessageCount % 5 == 0] → 백그라운드 추출 시작
    │       POST /api/v1/memory/extract
    │       { character_name, nickname, conversation_history }
    │       ← { memories: [{key, value}, ...] }
    │       → Room DB 저장 (기존 삭제 후 전체 갱신)
    │
    ├─ 현재 저장된 기억 로드 (Room DB)
    │
    └─ POST /api/v1/chat/stream
           { message, ..., memories: [{key, value}, ...] }
           → system_prompt에 기억 섹션 주입
```

## 추출 대상 정보

LLM이 대화에서 자동 추출하는 항목들:

- 직업, 학교, 학년
- 좋아하는 것 (음식, 취미, 음악, 게임, 영화)
- 싫어하는 것
- 최근 상황·고민
- 특별한 날 (생일, 기념일)
- 성격, 가치관
- 거주지, 고향

## 시스템 프롬프트 주입 형식

```
## 민준에 대해 기억하는 정보
- 직업: 대학생
- 좋아하는 음식: 라멘
- 좋아하는 음악: 인디팝
```

## API 레퍼런스

### POST /api/v1/memory/extract

**요청**
```json
{
  "character_name": "하루",
  "character_id": "1",
  "nickname": "민준",
  "conversation_history": [
    {"role": "user", "content": "나 오늘 대학교 수업 힘들었어"},
    {"role": "assistant", "content": "[{\"text\":\"어머 힘들었겠다ㅠ\",\"emotion\":\"SAD\"}]"}
  ]
}
```

**응답**
```json
{
  "memories": [
    {"key": "직업", "value": "대학생"}
  ]
}
```

## Room DB 마이그레이션

DB 버전 3 → 4에서 `memories` 테이블이 추가됩니다.
기존 사용자 데이터는 자동으로 마이그레이션됩니다 (`MIGRATION_3_4`).

## 설정

추출 빈도를 변경하려면 `ChatViewModel.kt`에서 수정:

```kotlin
// 기본값: 5번마다 추출
if (userMessageCount % 5 == 0) { ... }
```
