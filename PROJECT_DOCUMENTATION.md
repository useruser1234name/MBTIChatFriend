# MBTIChatFriend - 프로젝트 전체 문서

MBTI 기반 AI 채팅 컴패니언 앱. 16가지 MBTI 성격 유형의 캐릭터와 자연스러운 한국어 대화를 나누며, 호감도 시스템을 통해 관계를 발전시킬 수 있다.

---

## 1. 프로젝트 개요

### 1.1 기술 스택

| 영역 | 기술 |
|------|------|
| **Android** | Kotlin, Jetpack Compose, Hilt, Room, Retrofit, DataStore |
| **Server** | Python, FastAPI, Uvicorn |
| **Database** | PostgreSQL 16, Room (SQLite), ChromaDB |
| **AI/LLM** | OpenAI GPT-4o / GPT-4o-mini / gpt-image-1 |
| **Auth** | Firebase Auth (Anonymous + Google) |
| **Push** | Firebase Cloud Messaging (FCM) |
| **Storage** | Firebase Storage (이미지) |
| **Infra** | Docker Compose |

### 1.2 버전 정보

- Android: 0.6.0 (minSdk 28, targetSdk 35, Java/Kotlin 17)
- Server: FastAPI 0.115.0, Python 3.13
- Database: Room v7, PostgreSQL 16

### 1.3 핵심 기능 요약

| 기능 | 설명 |
|------|------|
| MBTI 채팅 | 16타입 성격 반영 AI 대화 |
| 호감도 시스템 | 5단계 관계 발전 (낯선 사이 → 연인) |
| 에피소딕 메모리 | 감정적 순간 기억 + 시간 가중 검색 |
| 밤 일기 | 세션 종료 시 캐릭터 시점 일기 자동 생성 |
| 음성 통화 | STT + TTS 기반 음성 대화 |
| 이미지 생성 | gpt-image-1 기반 캐릭터 표정 셋 |
| 파인튜닝 | 대화 데이터 기반 모델 커스터마이징 |
| 품질 관리 | 4축 실시간 품질 평가 + 재생성 게이트 |

---

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                     Android App                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ UI Layer │→│ ViewModel│→│Repository│               │
│  │ (Compose)│  │ (State)  │  │ (Data)   │               │
│  └──────────┘  └──────────┘  └────┬─────┘               │
│                                    │                     │
│              ┌────────────┬────────┼────────┐            │
│              │            │        │        │            │
│         ┌────┴───┐  ┌─────┴──┐  ┌──┴───┐ ┌──┴──────┐   │
│         │  Room  │  │Retrofit│  │ SSE  │ │Firebase │   │
│         │(SQLite)│  │ (REST) │  │Client│ │Auth/FCM │   │
│         └────────┘  └────┬───┘  └──┬───┘ └─────────┘   │
└──────────────────────────┼─────────┼────────────────────┘
                           │         │
                    ┌──────┴─────────┴──────┐
                    │    FastAPI Server      │
                    │  ┌─────────────────┐   │
                    │  │  chat_service   │   │
                    │  │  memory_service │   │
                    │  │  quality_service│   │
                    │  │  image_service  │   │
                    │  │  finetune_service│  │
                    │  └────────┬────────┘   │
                    │           │            │
                    │  ┌────────┼────────┐   │
                    │  │        │        │   │
                    │  ▼        ▼        ▼   │
                    │ PostgreSQL ChromaDB OpenAI│
                    └───────────────────────────┘
```

---

## 3. 서버 (FastAPI)

### 3.1 디렉토리 구조

```
server/
├── app/
│   ├── main.py              # FastAPI 앱 + 모든 API 엔드포인트
│   ├── config.py             # 환경변수 설정
│   ├── models.py             # Pydantic 요청/응답 모델
│   ├── chat_service.py       # 채팅 생성 + 호감도 분석
│   ├── prompts.py            # MBTI 성격 정의 + 프롬프트 빌더
│   ├── memory_service.py     # 대화 요약 + 핵심정보 + 에피소드 추출
│   ├── vector_store.py       # ChromaDB RAG 기반 장기 기억
│   ├── quality_service.py    # 응답 품질 평가 + 다양성 추적
│   ├── finetune_service.py   # OpenAI 파인튜닝 파이프라인
│   ├── image_service.py      # 이미지 생성 + Firebase Storage
│   ├── story_state_store.py  # 스토리 상태 + 관계 진행 추적
│   ├── diary_store.py        # 밤 일기 영속화
│   ├── postgres.py           # PostgreSQL 연결 + 스키마
│   ├── metrics_service.py    # 이벤트 로깅
│   ├── content_filter.py     # 콘텐츠 필터링 (테스트 중 비활성)
│   ├── auth_middleware.py    # Firebase 인증 미들웨어
│   └── firebase_service.py   # FCM 푸시 알림
├── evaluate.py               # 오프라인 품질 평가 스크립트
├── generate_synthetic_data.py # 합성 학습 데이터 생성 CLI
├── requirements.txt
└── .env.example
```

### 3.2 API 엔드포인트

#### 채팅

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/chat/send` | 메시지 전송 + AI 응답 | 30/min |
| POST | `/api/v1/chat/stream` | SSE 스트리밍 응답 | 30/min |

**ChatRequest 주요 필드:**
```python
message: str              # 사용자 메시지 (1-1000자)
mbti: str                 # 캐릭터 MBTI (e.g. "ENFP")
speech_style: str         # FORMAL | CASUAL | TSUNDERE | SWEET
relationship: str         # FRIEND | LOVER | SENIOR_JUNIOR
nickname: str             # 사용자 닉네임 (1-20자)
affinity_level: int       # 호감도 레벨 (1-5)
conversation_history: List[HistoryMessage]  # 최근 대화
character_name: str       # 캐릭터 이름
character_id: str         # 캐릭터 고유 ID
room_id: str              # 채팅방 ID
end_of_session: bool      # 세션 종료 여부 (밤 일기 트리거)
client_local_hour: int    # 클라이언트 로컬 시간 (0-23)
memories: List[MemoryItem] # key-value 기억 목록
```

**ChatResponse:**
```python
replies: List[ReplyPart]  # [{text, emotion, delay}]
affinity_delta: int       # 호감도 변화량
night_diary_generated: bool
next_hook: str            # 다음 대화 떡밥
next_goal: str            # 다음 대화 목표
```

#### 기억

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/memory/extract` | 대화에서 핵심 정보 추출 | 10/min |

#### 일기

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/diary/generate` | 캐릭터 일기 생성 | 10/min |

#### 이미지

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/image/generate` | 단일 이미지 생성 | 10/min |
| POST | `/api/v1/image/generate-set` | 15장 표정 셋 생성 (백그라운드) | 5/min |
| GET | `/api/v1/image/set-status/{task_id}` | 표정 셋 진행 상태 |  |

#### 파인튜닝

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/finetune/start` | 파인튜닝 작업 시작 | 5/min |
| GET | `/api/v1/finetune/status/{job_id}` | 작업 상태 확인 |  |
| POST | `/api/v1/finetune/activate` | 파인튜닝 모델 활성화 |  |

#### 피드백 & 품질

| Method | Path | 설명 | Rate Limit |
|--------|------|------|------------|
| POST | `/api/v1/feedback/submit` | 좋아요/싫어요 피드백 | 30/min |
| GET | `/api/v1/quality/dashboard` | 품질 대시보드 |  |
| GET | `/api/v1/quality/diversity/{character_id}` | 다양성 리포트 |  |

#### FCM

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/fcm/register` | FCM 토큰 등록 |
| POST | `/api/v1/fcm/send` | 푸시 알림 전송 |

### 3.3 핵심 서비스 상세

#### 3.3.1 chat_service.py - 채팅 파이프라인

**메시지 처리 흐름:**

```
사용자 메시지 수신
    │
    ▼
1. 콘텐츠 필터링 (현재 비활성)
    │
    ▼
2. 호감도 분석
   ├─ LLM 분석 (analyze_affinity_with_llm) ← 우선
   └─ 키워드 분석 (calculate_affinity_delta) ← fallback
    │
    ▼
3. 메모리 컨텍스트 구성
   ├─ 10턴마다 요약/핵심정보 갱신
   ├─ ChromaDB RAG 검색 (시맨틱 유사도)
   └─ 에피소드 기억 검색 (시간 가중)
    │
    ▼
4. 시스템 프롬프트 조립
   ├─ MBTI 성격 + 말투 + 관계
   ├─ 호감도별 행동 지침
   ├─ MBTI 궁합 정보
   ├─ 기억 컨텍스트 (요약 + 팩트 + 에피소드)
   └─ Few-shot 예시
    │
    ▼
5. 모델 라우팅
   ├─ 파인튜닝 모델 존재 → 해당 모델
   ├─ 복잡한 메시지 (>50자, 감정 키워드) → gpt-4o
   └─ 단순 메시지 (<10자, 인사) → gpt-4o-mini
    │
    ▼
6. LLM 호출 → JSON 응답 파싱
    │
    ▼
7. 품질 게이트
   ├─ quick_score() < 0.4 → 1회 재생성 (temp 0.9)
   └─ 통과 → 응답 전송
    │
    ▼
8. 백그라운드 품질 평가 (fire-and-forget)
   ├─ 4축 품질 점수 기록
   └─ 다양성 체크
    │
    ▼
9. 밤 일기 체크 (end_of_session + 22-04시)
```

**호감도 분석 (analyze_affinity_with_llm):**
- 모델: gpt-4o-mini, temperature 0.2, max_tokens 50
- 입력: 메시지 + 최근 8턴 맥락 + 장기 관계 맥락
- MBTI 그룹별 가중치:
  - NT: 논리적 대화에 높은 점수
  - NF: 감정 공유에 높은 점수
  - ST: 실질적 도움에 높은 점수
  - SF: 관심과 배려에 높은 점수
- 반환: -3 ~ +5 정수

**키워드 기반 호감도 fallback:**
```
긍정 카테고리: greeting(1), compliment(2), gratitude(2), empathy(2), affection(3), playful(1), interest(1)
부정 카테고리: dislike(1), annoyance(2), hostility(2), ignore(1)
부정문 감지: "안 ", "못 ", "않아", "없어" 등
보너스: 메시지 길이(>100자 +1), 이모티콘(ㅋㅋ +0.5), 대화 길이
레벨 승수: {1: 1.5, 2: 1.3, 3: 1.0, 4: 0.7, 5: 0.4}
MBTI 궁합: 0.8 ~ 1.3 배율
최종 스케일: ×0.4
```

**메시지 복잡도 분류 (_classify_message_complexity):**
```
simple: len < 10 AND ("안녕"|"ㅎㅎ"|"ㅋㅋ"|"응"|"어"|"ㅇㅇ"|"그래"|...) → gpt-4o-mini
complex: len > 50 OR ("고민"|"힘들"|"어떻게"|"속상"|"우울"|"고백"|...) → gpt-4o
default: history < 5 → simple, 이외 → complex
```

**응답 파싱 (_parse_reply):**
```
1차: JSON 배열 파싱 → [{text, emotion, delay}]
2차: 불완전 JSON 복구 (닫히지 않은 배열/객체)
3차: 정규식 추출 ("text": "...", "emotion": "...")
4차: 줄 단위 분리 (최후 수단)
```

**목업 응답 시스템 (_MOCK_RESPONSES):**
- API 키 없을 때 사용
- 4 MBTI 그룹 × 3 호감도 티어 = 12개 응답 세트
- lambda 함수로 동적 메시지 생성

#### 3.3.2 prompts.py - 성격 정의 & 프롬프트

**MBTI_PERSONALITIES (16타입):**
```python
{
    "INTJ": {
        "traits": "전략적 사고의 달인...",
        "style": "군더더기 없이 핵심만...",
        "speech_habits": ["...그건 비효율적이지 않아?", ...],
        "thinking": "모든 상황을 시스템적으로 분석...",
        "emotional": "감정 표현에 서툴지만...",
        "quirks": ["혼자만의 시간 필요", ...]
    },
    # ... 16타입 전부 정의
}
```

**AFFINITY_BEHAVIORS (5단계):**

| 레벨 | 설명 | 분위기 | 감정 |
|------|------|--------|------|
| 1 | 처음 만난 낯선 사이 | 정중, 조심스러움 | NEUTRAL, 가끔 SHY |
| 2 | 아는 사이, 편해지는 중 | 가끔 농담 | HAPPY/SHY, PLAYFUL 등장 |
| 3 | 친한 친구 | 편한 반말, 장난 | 다양한 감정 자유 사용 |
| 4 | 특별한 사이, 썸 | 은근한 애정 | LOVE/SHY 빈번 |
| 5 | 연인 사이 | 적극적 애정 | LOVE 적극, 모든 감정 자유 |

**FEW_SHOT_EXAMPLES:**
- 4 MBTI 그룹(NT/NF/ST/SF) x 3 호감도 티어(low/mid/high) x 2개 = 24 예시
- build_system_prompt()에 자동 삽입

**시스템 프롬프트 구성 (build_system_prompt):**
```
# 역할 설정 (최우선)
# 출력 형식 (JSON 배열)
# 캐릭터 성격
# 말투 & 표현 습관
# 감정 표현
# 특유 습관
# 말투 스타일
# 관계
## 현재 관계 상태 (호감도 N/5)
## MBTI 궁합
## 이전 대화 기억
## 기억 정보
## 떠오르는 기억 (에피소드)
## 대화 예시 (Few-shot)
# 표현 규칙
# 감정 선택 가이드
# 특수 상황 대응
# 대화 흐름 인식
```

#### 3.3.3 memory_service.py - 기억 시스템

```
┌─────────────────────────────────────────┐
│           Memory Architecture           │
│                                         │
│  ┌─────────┐    10턴마다    ┌─────────┐  │
│  │대화 히스토리│────────────→│요약 갱신 │  │
│  │(20개 메시지)│            │(gpt-4o-mini)│
│  └─────────┘              └────┬────┘  │
│                                │        │
│         ┌──────────────────────┼───┐    │
│         ▼                      ▼   ▼    │
│  ┌──────────┐  ┌──────────┐  ┌──────┐  │
│  │핵심정보   │  │대화 요약  │  │에피소드│  │
│  │(key-value)│  │(5-8문장) │  │(감정적)│  │
│  │max 15개  │  │캐릭터시점 │  │max 3개│  │
│  └────┬─────┘  └────┬─────┘  └──┬───┘  │
│       │             │           │       │
│       ▼             ▼           ▼       │
│  ┌─────────┐  ┌──────────┐  ┌───────┐  │
│  │PostgreSQL│  │PostgreSQL│  │ChromaDB│  │
│  │(facts)   │  │(summary) │  │(vector)│  │
│  └─────────┘  └──────────┘  └───────┘  │
└─────────────────────────────────────────┘
```

**인메모리 캐시 + PostgreSQL 이중 레이어:**
- `_conversation_summaries`: 대화 요약 캐시
- `_character_memories`: 핵심 정보 캐시
- Cold start 시 PostgreSQL에서 로드
- 변경 시 캐시 + DB 동시 갱신

**summarize_conversation():**
- 모델: gpt-4o-mini, temp 0.3, max_tokens 500
- 7가지 정보 포함: 사용자 정보, 중요 사건, 관계 진행, 약속, 감정 변화, 자주 언급 주제, 마지막 맥락
- 이전 요약과 통합하여 중복 제거

**extract_facts():**
- 모델: gpt-4o-mini, temp 0.2, max_tokens 300
- JSON 배열 출력 → 기존 facts와 병합 (중복 키 제외)
- 최대 15개 유지

**extract_episodes():**
- 감정 변화, 약속, 특별한 경험, 깊은 감정 교류, 처음 알게 된 순간
- ChromaDB ep_{character_id} 컬렉션에 저장
- 메타데이터: timestamp, emotion, importance(1-5), topic

#### 3.3.4 vector_store.py - ChromaDB 벡터 스토어

**컬렉션 구조:**
```
ChromaDB
├── char_{character_id}    # 일반 기억 (key-value)
│   ├── document: "{key}: {value}"
│   └── metadata: {timestamp, type: "memory", key}
│
└── ep_{character_id}      # 에피소드 기억
    ├── document: 에피소드 설명 텍스트
    └── metadata: {timestamp, emotion, importance, topic, type: "episode"}
```

**시간 가중 에피소드 검색 (search_episodes):**
```python
semantic_score = max(0, 1.0 - distance / 2.0)
decay = exp(-days_ago / 30)          # 30일 반감기
importance_weight = 0.6 + (importance / 5) * 0.4  # 0.8 ~ 1.4
final_score = semantic_score * decay * importance_weight
```

#### 3.3.5 quality_service.py - 품질 관리

**4축 품질 평가 (score_response_async):**
```
quality_score = 0.3 × mbti_consistency     (MBTI 일관성)
             + 0.3 × contextual_relevance  (맥락 적절성)
             + 0.2 × emotional_naturalness (감정 자연스러움)
             + 0.2 × engagement_quality    (대화 지속 유도력)
```
- 모델: gpt-4o-mini, fire-and-forget 백그라운드 실행

**빠른 품질 게이트 (quick_score):**
- JSON 형식 유효성 검사 (LLM 없이) → format_score
- LLM MBTI 일관성 검사 (max_tokens 30) → consistency_score
- 최종: 0.4 × format + 0.6 × consistency
- score < 0.4 → 재생성 트리거

**다양성 추적 (check_diversity):**
- 최근 20개 응답의 bigram 겹침 비율 계산
- diversity_score = 1.0 - avg_overlap
- score < 0.3 → `low_diversity_warning` 이벤트 기록

#### 3.3.6 finetune_service.py - 파인튜닝

**파이프라인:**
```
대화 수집 → 품질 필터링 → JSONL 생성 → OpenAI 업로드 → Fine-tuning 작업
              │                │
              ├─ score < 0.6 제외    ├─ 합성 데이터 병합 (선택)
              └─ thumbs_down 제외    └─ 셔플
```
- 모델: gpt-4o-mini-2024-07-18
- 하이퍼파라미터: n_epochs=3
- 최소 10개 학습 예시 필요
- 결과: finetune_models.json에 character_id → model_id 매핑 저장

#### 3.3.7 story_state_store.py - 스토리 상태

**StoryState 데이터:**
```python
room_id, character_id
chapter: int              # 현재 챕터
current_goal: str         # 현재 대화 목표
unresolved_hook: str      # 미해결 떡밥
promise: str              # 캐릭터가 한 약속
trust_score: int          # 신뢰도 (0-100)
turn_count: int           # 총 턴 수
next_hook: str            # 다음 대화 떡밥
next_goal: str            # 다음 대화 목표
```

**콜백 힌트 시스템:**
- 마지막 콜백 후 6턴 이상 경과 시 활성화
- 우선순위: unresolved_hook → promise → next_hook
- 시스템 프롬프트에 "이전 대화에서 ~한 이야기가 있었어" 형태로 삽입

#### 3.3.8 image_service.py - 이미지 생성

**표정 셋 구성 (15장):**
```
표정 (10장): neutral, happy, sad, angry, shy,
            surprised, love, playful, worried, touched
오버레이 (5장): eyes_half_closed, eyes_closed,
              mouth_small, mouth_medium, mouth_open
```
- 모델: gpt-image-1
- 배치: 5장씩 동시 생성 (API rate limit 대응)
- 저장: Firebase Storage `characters/{character_id}/expressions/{key}.png`
- 진행률 추적: 인메모리 `_tasks` dict

#### 3.3.9 content_filter.py - 콘텐츠 필터

현재 **테스트 모드로 비활성화** 상태.

정규식 기반 차단 패턴:
- 성적 콘텐츠 (섹스, 가슴, 엉덩이 등)
- 폭력 (죽여, 자살, 테러)
- 혐오 발언 (시발, 병신 등)

#### 3.3.10 auth_middleware.py - 인증

- Firebase ID Token 검증 (Bearer 토큰)
- `REQUIRE_AUTH` 환경변수로 강제 여부 제어
- development: 토큰 없어도 허용 (None 반환)
- production: 토큰 필수 (401 에러)

### 3.4 데이터베이스 스키마 (PostgreSQL)

```sql
-- 스토리 진행 상태
story_state (
    room_id TEXT PRIMARY KEY,
    character_id TEXT, chapter INT, current_goal TEXT,
    unresolved_hook TEXT, promise TEXT, trust_score INT,
    turn_count INT, next_hook TEXT, next_goal TEXT, ...
)

-- 캐릭터 일기
diary_entries (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT, character_id TEXT, diary_date DATE,
    diary_text TEXT, emotion TEXT,
    next_hook TEXT, next_goal TEXT,
    UNIQUE(room_id, character_id, diary_date)
)

-- 메트릭 이벤트
metric_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT,  -- chat_turn, quality_score, night_diary_generated, low_diversity_warning
    room_id TEXT, character_id TEXT,
    payload JSONB, created_at TIMESTAMPTZ
)

-- 대화 기억
conversation_memory (
    id BIGSERIAL PRIMARY KEY,
    memory_key TEXT UNIQUE,  -- "{character_name}_{nickname}"
    summary TEXT, facts JSONB, updated_at TIMESTAMPTZ
)

-- 사용자 피드백
response_feedback (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT, character_id TEXT, message_id TEXT,
    feedback_type TEXT,  -- thumbs_up | thumbs_down
    feedback_detail TEXT, created_at TIMESTAMPTZ
)
```

### 3.5 환경 설정 (config.py)

```python
OPENAI_API_KEY              # OpenAI API 키
HOST / PORT                 # 서버 바인드 (0.0.0.0:8000)
FIREBASE_CREDENTIALS_PATH   # Firebase 서비스 계정 JSON
FIREBASE_STORAGE_BUCKET     # Firebase Storage 버킷
DATABASE_URL                # PostgreSQL 연결 문자열
ENVIRONMENT                 # development | production
CORS_ORIGINS                # CORS 허용 도메인 (dev: "*")
REQUIRE_AUTH                # 인증 강제 여부
```

### 3.6 평가 & 합성 데이터

**evaluate.py - 오프라인 평가 (7개 카테고리):**
1. 응답 형식 (JSON 배열 유효성)
2. MBTI 일관성 (성격 반영도)
3. 호감도 분석 정확도
4. 메모리 추출 품질
5. 호감도 레벨별 행동
6. 응답 다양성
7. 품질 스코어 보정

**generate_synthetic_data.py - 합성 데이터:**
- 시나리오: daily, emotional, conflict, advice, bonding
- 호감도별 시나리오 가중치 자동 조정
- gpt-4o로 10턴 대화 생성 → JSONL 출력
- 사용: `python generate_synthetic_data.py --all --count-per-combo 10`

---

## 4. Android 앱

### 4.1 디렉토리 구조

```
android/app/src/main/java/com/example/mbtichatfriend/
├── MainActivity.kt              # 앱 진입점 (Scaffold + NavHost)
├── MBTIChatFriendApp.kt          # Application (Hilt, Firebase 초기화)
│
├── navigation/
│   ├── Routes.kt                 # 화면 경로 정의 (sealed class)
│   └── AppNavHost.kt             # 네비게이션 그래프
│
├── model/
│   ├── UserProfile.kt            # 사용자 프로필 enum/data class
│   ├── ChatMessage.kt            # 채팅 메시지 모델
│   ├── CharacterAvatar.kt        # 12개 아바타 정의
│   ├── CharacterEmotion.kt       # 10개 감정 코드
│   ├── AvatarConfig.kt           # v2 아바타 커스터마이징
│   └── PresetCharacters.kt       # 16개 프리셋 캐릭터
│
├── data/
│   ├── local/
│   │   ├── AppDatabase.kt        # Room DB (v7, 5개 Entity)
│   │   ├── MessageEntity.kt      # 메시지 테이블
│   │   ├── MessageDao.kt
│   │   ├── CharacterEntity.kt    # 캐릭터 테이블
│   │   ├── CharacterDao.kt
│   │   ├── DiaryEntity.kt        # 일기 테이블
│   │   ├── DiaryDao.kt
│   │   ├── MemoryEntity.kt       # 기억 테이블
│   │   ├── MemoryDao.kt
│   │   ├── FeedbackEntity.kt     # 피드백 테이블
│   │   ├── FeedbackDao.kt
│   │   ├── UserPreferences.kt    # DataStore 기반 설정
│   │   ├── OfflineMessageQueue.kt # 오프라인 메시지 큐
│   │   ├── NetworkObserver.kt    # 네트워크 상태 감지
│   │   ├── NotificationHelper.kt # 알림 생성
│   │   └── ContentFilter.kt     # 클라이언트 필터
│   │
│   ├── remote/
│   │   ├── ChatApi.kt            # Retrofit API 인터페이스
│   │   ├── SseClient.kt          # SSE 스트리밍 클라이언트
│   │   ├── FirebaseAuthManager.kt # Firebase 인증
│   │   ├── AuthInterceptor.kt    # OkHttp 토큰 인터셉터
│   │   ├── FirestoreManager.kt   # Firestore 프로필 동기화
│   │   ├── FcmTokenManager.kt    # FCM 토큰 관리
│   │   ├── ChatFirebaseMessagingService.kt # FCM 수신 서비스
│   │   └── RemoteConfigManager.kt # Remote Config
│   │
│   ├── repository/
│   │   ├── ChatRepository.kt     # 채팅 데이터 관리
│   │   ├── CharacterRepository.kt # 캐릭터 CRUD
│   │   ├── DiaryRepository.kt    # 일기 관리
│   │   ├── MemoryRepository.kt   # 기억 추출/저장
│   │   ├── FinetuneRepository.kt # 파인튜닝 관리
│   │   └── AuthRepository.kt     # 인증 관리
│   │
│   └── voice/
│       ├── TtsEngine.kt          # TTS 인터페이스
│       ├── AndroidTtsEngine.kt   # Android TTS 구현
│       └── SpeechRecognizerManager.kt # STT 관리
│
├── di/
│   └── AppModule.kt              # Hilt DI 모듈
│
└── ui/
    ├── theme/
    │   ├── Color.kt              # 색상 정의
    │   ├── Theme.kt              # 테마 (Light/Dark)
    │   └── Type.kt               # 타이포그래피
    │
    ├── components/
    │   ├── CharacterFaceCanvas.kt    # Canvas 기반 아바타
    │   ├── ImageCharacterFace.kt     # 이미지 기반 아바타
    │   ├── LiveCharacter.kt          # 실시간 감정 표현
    │   ├── EmotionLottieBackground.kt # 감정 배경 애니메이션
    │   ├── TypingIndicatorBubble.kt  # 타이핑 인디케이터
    │   ├── LottieOneShot.kt          # 1회성 Lottie 재생
    │   ├── OnboardingScaffold.kt     # 온보딩 공통 레이아웃
    │   └── SensorState.kt           # 근접 센서
    │
    ├── splash/SplashScreen.kt
    ├── login/
    │   ├── LoginScreen.kt
    │   └── AuthViewModel.kt
    ├── onboarding/
    │   ├── NicknameScreen.kt
    │   ├── GenderScreen.kt
    │   ├── AgeScreen.kt
    │   ├── MbtiSelectScreen.kt
    │   ├── StyleSelectScreen.kt
    │   └── OnboardingViewModel.kt
    ├── home/
    │   ├── HomeScreen.kt
    │   ├── HomeViewModel.kt
    │   ├── CreateCharacterSheet.kt
    │   ├── AvatarBuilderSheet.kt
    │   └── ImageGeneratorSheet.kt
    ├── chat/
    │   ├── ChatScreen.kt
    │   └── ChatViewModel.kt
    ├── character/
    │   ├── CharacterProfileScreen.kt
    │   └── CharacterProfileViewModel.kt
    ├── diary/
    │   ├── DiaryScreen.kt
    │   └── DiaryViewModel.kt
    ├── gallery/
    │   ├── GalleryScreen.kt
    │   └── GalleryViewModel.kt
    ├── voicecall/
    │   ├── VoiceCallScreen.kt
    │   └── VoiceCallViewModel.kt
    └── settings/
        ├── SettingsScreen.kt
        └── SettingsViewModel.kt
```

### 4.2 네비게이션 구조

```
Route.Splash
    │
    ▼ (onboardingCompleted?)
Route.Login ──(skip/signIn)──→ Route.OnboardingNickname
                                    │
                                    ▼
                              Route.OnboardingGender
                                    │
                                    ▼
                              Route.OnboardingAge
                                    │
                                    ▼
                              Route.OnboardingMbti
                                    │
                                    ▼
                              Route.OnboardingStyle
                                    │
                                    ▼
                              Route.Home ◄──────────────────────┐
                                │                               │
                    ┌───────────┼───────────┐                   │
                    ▼           ▼           ▼                   │
              Route.Chat  Route.Gallery  Route.Settings         │
                    │           │                               │
                    ▼           │                               │
          Route.CharacterProfile│                               │
                    │           │                               │
              ┌─────┼─────┐    │                               │
              ▼     ▼     ▼    │                               │
          Route.Diary  Route.VoiceCall                          │
                                                               │
        BottomNav: [Home] [Gallery] [Settings] ────────────────┘
```

**Route 정의 (sealed class):**
```kotlin
Route.Splash                    // 경로: "splash"
Route.Login                     // 경로: "login"
Route.OnboardingNickname        // 경로: "onboarding/nickname"
Route.OnboardingGender          // 경로: "onboarding/gender"
Route.OnboardingAge             // 경로: "onboarding/age"
Route.OnboardingMbti            // 경로: "onboarding/mbti"
Route.OnboardingStyle           // 경로: "onboarding/style"
Route.Home                      // 경로: "home"
Route.Chat(characterId: Long)   // 경로: "chat/{characterId}"
Route.CharacterProfile(characterId: Long) // 경로: "character/{characterId}"
Route.Diary(characterId: Long)  // 경로: "diary/{characterId}"
Route.VoiceCall(characterId: Long) // 경로: "voicecall/{characterId}"
Route.Gallery                   // 경로: "gallery"
Route.Settings                  // 경로: "settings"
```

### 4.3 데이터 레이어 상세

#### 4.3.1 Room Database (v7)

**MessageEntity:**
```kotlin
@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val characterId: Long,
    val text: String,
    val isFromUser: Boolean,
    val emotion: String? = null,       // NEUTRAL, HAPPY, SHY, ...
    val createdAt: Long,
    val sendStatus: String = "SENT",   // PENDING, SENT, FAILED
    val retryCount: Int = 0
)
```

**CharacterEntity:**
```kotlin
@Entity(tableName = "characters")
data class CharacterEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val mbti: String,
    val speechStyle: String,
    val relationship: String,
    val affinityScore: Int = 0,        // 0-100
    val totalMessages: Int = 0,
    val avatarId: String = "BUNNY",
    val expressionSet: String? = null,  // JSON: {emotion: url}
    val expressionSetReady: Boolean = false,
    val createdAt: Long
) {
    val affinityLevel: Int get() = when {
        affinityScore >= 81 -> 5   // 연인
        affinityScore >= 61 -> 4   // 썸
        affinityScore >= 41 -> 3   // 친구
        affinityScore >= 21 -> 2   // 아는 사이
        else -> 1                  // 낯선 사이
    }
}
```

**마이그레이션 이력:**
| 버전 | 변경 |
|------|------|
| v1→v2 | characters에 avatarId 컬럼 추가 |
| v2→v3 | diaries 테이블 생성 |
| v3→v4 | memories 테이블 생성 |
| v4→v5 | messages에 sendStatus, retryCount 추가 |
| v5→v6 | characters에 expressionSet, expressionSetReady 추가 |
| v6→v7 | feedback 테이블 생성 |

**초기 데이터 시딩:**
```kotlin
// AppDatabase onCreate 콜백
// PresetCharacters에서 ENFP 하루, INTJ 서진, ESFJ 민지, ISTP 재현 4개 생성
```

#### 4.3.2 UserPreferences (DataStore)

```kotlin
// 저장 키
onboarding_completed: Boolean
nickname: String
gender: String            // MALE, FEMALE, OTHER
ageGroup: String          // TEEN, TWENTIES, THIRTIES, FORTIES_PLUS
partnerMbti: String       // 선호 MBTI
userMbti: String          // 사용자 MBTI
speechStyle: String       // FORMAL, CASUAL, TSUNDERE, SWEET
relationship: String      // FRIEND, LOVER, SENIOR_JUNIOR
darkMode: String          // system, light, dark
firebaseUid: String
authProvider: String      // anonymous, google
fcmToken: String
fcmTokenSynced: Boolean
```

#### 4.3.3 오프라인 메시지 큐 (OfflineMessageQueue)

```
메시지 전송 시도
    │
    ├─ 성공 → status = SENT
    │
    └─ 실패 → status = PENDING, retryCount++
              │
              ▼
        네트워크 복구 감지 (NetworkObserver)
              │
              ▼
        flushPendingMessages()
        ├─ retryCount < 3 → 재시도
        └─ retryCount >= 3 → status = FAILED
```

#### 4.3.4 ChatApi (Retrofit)

```kotlin
interface ChatApi {
    @POST("api/v1/chat/send")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

    @POST("api/v1/diary/generate")
    suspend fun generateDiary(@Body request: DiaryRequest): DiaryResponse

    @POST("api/v1/memory/extract")
    suspend fun extractMemories(@Body request: MemoryExtractRequest): MemoryExtractResponse

    @POST("api/v1/finetune/start")
    suspend fun startFinetune(@Body request: FinetuneStartRequest): FinetuneStartResponse

    @POST("api/v1/image/generate")
    suspend fun generateImage(@Body request: ImageGenerateRequest): ImageGenerateResponse

    @POST("api/v1/image/generate-set")
    suspend fun generateExpressionSet(@Body request: ImageSetRequest): ImageSetResponse

    @POST("api/v1/feedback/submit")
    suspend fun submitFeedback(@Body request: FeedbackRequest): Response<Unit>
    // ... 등
}
```

#### 4.3.5 SSE 스트리밍 (SseClient)

```kotlin
sealed class SseEvent {
    data class Message(val text: String, val emotion: String, val delay: Int) : SseEvent()
    data class Done(val affinityDelta: Int) : SseEvent()
    data class Error(val message: String) : SseEvent()
}

// streamChat(request): Flow<SseEvent>
// OkHttp EventSource로 실시간 메시지 수신
// ChatViewModel에서 메시지 버블 하나씩 표시
```

#### 4.3.6 Firebase 연동

**인증 (FirebaseAuthManager):**
```
signInAnonymously()  →  익명 계정 생성
signInWithGoogle()   →  Google 계정 로그인 (Credential Manager)
linkWithCredential() →  익명 → Google 계정 연결
```

**인터셉터 (AuthInterceptor):**
- 모든 API 요청에 `Authorization: Bearer {token}` 헤더 추가
- 토큰 캐시: 55분 TTL, 만료 5분 전 갱신

**FCM (ChatFirebaseMessagingService):**
- 새 메시지 알림 수신 → NotificationHelper로 알림 표시
- Deep link: characterId 포함 → 해당 채팅방으로 이동

**Remote Config (RemoteConfigManager):**
```kotlin
max_message_length: 500
max_conversation_history: 20
content_filter_enabled: true
feature_sse_enabled: true
feature_google_signin: true
feature_push_notification: true
mbti_compatibility_enabled: true
affinity_max_delta: 5
```

### 4.4 ViewModel 상세

#### 4.4.1 ChatViewModel

```kotlin
// 상태
character: StateFlow<CharacterEntity?>      // 현재 캐릭터
messages: StateFlow<List<ChatMessage>>      // 채팅 메시지 목록
isTyping: StateFlow<Boolean>               // AI 타이핑 중
currentEmotion: StateFlow<CharacterEmotion> // 현재 감정
isOnline: StateFlow<Boolean>               // 네트워크 상태
errorMessage: StateFlow<String?>
levelUpEvent: StateFlow<Int?>              // 레벨업 알림
levelDownEvent: StateFlow<Int?>            // 레벨다운 알림
expressionUrls: Map<String, String>?       // 표정 이미지 URL
feedbackMap: MutableStateMap<Long, String>  // 피드백 상태

// 핵심 로직
fun streamMessage(text: String)   // SSE 스트리밍 전송
fun sendMessage(text: String)     // REST 전송 (fallback)
fun submitFeedback(messageId, feedbackType)
```

**메시지 전송 흐름:**
```
사용자 입력
    │
    ▼
1. 사용자 메시지 로컬 저장 (PENDING)
    │
    ▼
2. SSE 스트리밍 시작
   ├─ SseEvent.Message → AI 메시지 로컬 저장 + 감정 업데이트
   ├─ SseEvent.Done → 호감도 반영 + 메모리 추출
   └─ SseEvent.Error → REST fallback 시도
    │
    ▼
3. 호감도 변경 시
   ├─ 레벨 상승 → levelUpEvent 발행
   └─ 레벨 하락 → levelDownEvent 발행
    │
    ▼
4. 네트워크 복구 시 → 미전송 메시지 재전송
```

#### 4.4.2 HomeViewModel

```kotlin
characters: StateFlow<List<CharacterEntity>>  // 캐릭터 목록
nickname: StateFlow<String>                   // 사용자 닉네임
lastMessages: StateFlow<Map<Long, LastMessageInfo>>  // 마지막 메시지

fun createCharacter(name, mbti, speechStyle, relationship, avatarId)
fun deleteCharacter(id)
```

#### 4.4.3 CharacterProfileViewModel

```kotlin
sealed class FinetuneUiState {
    object Idle
    object Loading
    data class JobStarted(val jobId: String)
    data class InProgress(val status: String)
    data class Completed(val modelId: String)
    data class Error(val message: String)
}

fun startFinetune(character: CharacterEntity)
fun checkFinetuneStatus(jobId: String)
fun activateFinetunedModel(characterId, modelId)
```

### 4.5 UI 화면 구성

#### 4.5.1 SplashScreen
- 장식 원, 로고 박스, 감정 아이콘 행 애니메이션
- 1.5초 후 온보딩 완료 여부에 따라 Login 또는 Home으로 이동

#### 4.5.2 LoginScreen
- 4가지 기능 프리뷰 카드
- Google 로그인 / 익명 로그인 / 건너뛰기

#### 4.5.3 온보딩 (5단계)
```
1. NicknameScreen  - 닉네임 입력 (2-8자)
2. GenderScreen    - 성별 선택
3. AgeScreen       - 연령대 선택
4. MbtiSelectScreen - MBTI 선택 (16타입)
5. StyleSelectScreen - 말투/관계 설정
```

#### 4.5.4 HomeScreen
- 캐릭터 카드 목록 (아바타, 이름, MBTI, 마지막 메시지, 호감도 레벨 태그)
- 빈 상태: Lottie 애니메이션 + "캐릭터 만들기" 버튼
- FAB: 캐릭터 생성 BottomSheet
- CreateCharacterSheet → AvatarBuilderSheet (v2 커스텀 아바타)

#### 4.5.5 ChatScreen
- 상단: 캐릭터 아바타 (140dp, 감정에 따라 변화) + Lottie 감정 배경
- 중앙: 메시지 버블 목록
  - 사용자: 파란/보라 버블 (우측)
  - AI: 흰색 버블 (좌측) + 감정 태그 + 피드백 버튼
- 하단: 멀티라인 입력 (최대 4줄) + 전송 버튼 (스케일 애니메이션)
- 타이핑 인디케이터: Lottie 기반 점 3개 애니메이션
- 레벨업/다운 이벤트: Lottie 1회 재생

#### 4.5.6 CharacterProfileScreen
- 캐릭터 정보 (이름, MBTI, 호감도 게이지)
- 호감도 레벨별 설명
- 파인튜닝 관리 (시작/상태확인/활성화)
- 일기 보기, 음성 통화, 삭제 버튼

#### 4.5.7 DiaryScreen
- 오늘 일기 생성 버튼
- 과거 일기 카드 (날짜, 감정, 내용)
- animateContentSize로 펼치기/접기

#### 4.5.8 GalleryScreen
- 프리셋 캐릭터 16개 (MBTI 그룹별 탭)
- 카드 프레스 애니메이션 (scale 0.95)
- "추가하기" → 즉시 캐릭터 생성

#### 4.5.9 VoiceCallScreen
- 음성 통화 UI (캐릭터 아바타 + 상태 인디케이터)
- STT: 한국어 음성 인식 → 텍스트
- TTS: AI 응답 → 음성 출력
- 상태: IDLE → LISTENING → PROCESSING → SPEAKING

#### 4.5.10 SettingsScreen
- 프로필 카드 (아바타 이니셜, 닉네임, 수정 버튼)
- 다크모드 설정 (시스템/라이트/다크)
- Google 계정 연결
- 로그아웃

### 4.6 컴포넌트

| 컴포넌트 | 설명 |
|----------|------|
| `CharacterFaceCanvas` | Canvas API로 아바타 얼굴 렌더링 (v2 AvatarConfig) |
| `ImageCharacterFace` | Coil로 표정 이미지 로드 (gpt-image-1 생성) |
| `LiveCharacter` | Canvas/Image 아바타 + 감정 전환 + 눈 깜빡임 |
| `EmotionLottieBackground` | 감정별 Lottie 배경 애니메이션 |
| `TypingIndicatorBubble` | AI 응답 대기 타이핑 인디케이터 |
| `LottieOneShot` | 레벨업 등 1회성 Lottie 재생 |
| `OnboardingScaffold` | 온보딩 화면 공통 레이아웃 |

### 4.7 테마

**라이트 모드:**
- Primary: PastelPink (#FFB5C0)
- Secondary: PastelPurple (#C4B5FD)
- Background: CreamWhite (#FFF8F0)
- 사용자 버블: UserBubble (#E8DEF8)
- AI 버블: AiBubble (#FFFFFF)

**다크 모드:**
- Background: DarkNavy (#1A1B2E)
- Surface: DarkSurface (#252640)
- Card: DarkCard (#2D2E4A)
- 사용자 버블: DarkUserBubble (#3D3270)
- AI 버블: DarkAiBubble (#2D2E4A)

### 4.8 의존성 주입 (Hilt)

```kotlin
@Module @InstallIn(SingletonComponent::class)
object AppModule {
    // Database
    @Provides @Singleton
    fun provideDatabase(app: Application): AppDatabase
    // + 5개 DAO 각각 @Provides

    // Network
    @Provides @Singleton
    fun provideOkHttpClient(interceptor: AuthInterceptor): OkHttpClient
    // + Retrofit, ChatApi, Moshi

    // Voice
    @Provides @Singleton
    fun provideTtsEngine(app: Application): TtsEngine
    @Provides @Singleton
    fun provideSpeechRecognizer(app: Application): SpeechRecognizerManager
}
```

---

## 5. 모델 & 데이터 구조

### 5.1 캐릭터 아바타 (12종)

| ID | 이름 | 색상 |
|----|------|------|
| BUNNY | 토끼 | #FFB5C0 |
| CAT | 고양이 | #C4B5FD |
| BEAR | 곰 | #A8D8B9 |
| FOX | 여우 | #FFD4A8 |
| PENGUIN | 펭귄 | #A8C8FF |
| DOG | 강아지 | #F5D0A9 |
| WOLF | 늑대 | #B0B0C8 |
| DRAGON | 용 | #C8A8D8 |
| UNICORN | 유니콘 | #F0C0E8 |
| HAMSTER | 햄스터 | #FFE0B0 |
| OWL | 부엉이 | #C0B8A0 |
| DEER | 사슴 | #B8D8C8 |

### 5.2 v2 아바타 커스터마이징 (AvatarConfig)

```kotlin
data class AvatarConfig(
    val skinTone: Int = 0,      // 5종 피부톤
    val hairStyle: Int = 0,     // 6종 헤어스타일
    val hairColor: Int = 0,     // 8종 머리색
    val eyeStyle: Int = 0,      // 4종 눈 모양
    val blushEnabled: Boolean = true,
    val accessory: Int = 0,     // 6종 악세사리
    val bgColorIndex: Int = 0   // 8종 배경색
)
// 직렬화: "v2:0,0,0,0,true,0,0"
```

### 5.3 감정 코드 (10종)

| 코드 | 설명 | 사용 맥락 |
|------|------|-----------|
| NEUTRAL | 평범 | 일상 대화 |
| HAPPY | 기쁨 | 즐거운 상황 |
| SHY | 수줍음 | 칭찬, 고백 |
| SAD | 슬픔 | 위로 상황 |
| ANGRY | 화남 | 불만, 항의 |
| SURPRISED | 놀람 | 예상치 못한 말 |
| LOVE | 사랑 | 애정 표현 |
| PLAYFUL | 장난 | 놀리기, 유머 |
| WORRIED | 걱정 | 염려 상황 |
| TOUCHED | 감동 | 감동적 순간 |

### 5.4 프리셋 캐릭터 (16개)

| MBTI | 이름 | 그룹 |
|------|------|------|
| ENFP | 하루 | NF |
| INFP | 시온 | NF |
| ENFJ | 유나 | NF |
| INFJ | 도윤 | NF |
| INTJ | 서진 | NT |
| ENTP | 지안 | NT |
| INTP | 하윤 | NT |
| ENTJ | 준서 | NT |
| ESFJ | 민지 | SJ |
| ISFJ | 소율 | SJ |
| ESTJ | 태현 | SJ |
| ISTJ | 지호 | SJ |
| ISTP | 재현 | SP |
| ESTP | 우진 | SP |
| ISFP | 예린 | SP |
| ESFP | 수아 | SP |

### 5.5 호감도 시스템

```
점수 범위    레벨    설명           행동 변화
─────────────────────────────────────────
  0 - 20      1     낯선 사이       존댓말, 조심스러움
 21 - 40      2     아는 사이       반말 섞기, 가끔 농담
 41 - 60      3     친한 친구       편한 반말, 자기 이야기
 61 - 80      4     썸 단계         은근한 애정, 질투
 81 - 100     5     연인 사이       적극적 애정, 스킨십
```

---

## 6. 인프라 & 배포

### 6.1 Docker Compose

```yaml
services:
  server:
    build: ./server
    ports: ["8000:8000"]
    env_file: ./server/.env
    depends_on: [db]

  db:
    image: postgres:16
    ports: ["127.0.0.1:5432:5432"]  # 로컬 바인드
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-mbti_app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_in_production}
      POSTGRES_DB: ${POSTGRES_DB:-mbti_chat}
    volumes:
      - pgdata:/var/lib/postgresql/data
```

### 6.2 환경 분리

| 항목 | Development | Production |
|------|-------------|------------|
| CORS | `*` (전체 허용) | 명시적 도메인만 |
| Auth | 선택 (REQUIRE_AUTH=false) | 필수 (REQUIRE_AUTH=true) |
| Content Filter | 비활성 | 활성 |
| DB 비밀번호 | change_me_in_production | 환경변수로 강한 비밀번호 |
| DB 포트 | 127.0.0.1:5432 | 외부 비공개 |

### 6.3 Lottie 애니메이션 에셋

```
android/app/src/main/assets/lottie/
├── happy.json, love.json, idle.json, sad.json, angry.json
├── shy.json, surprised.json, playful.json, touched.json, worried.json
├── typing_indicator.json   # 타이핑 인디케이터
├── levelup.json            # 레벨업 효과
└── empty_chat.json         # 빈 채팅방
```

---

## 7. 데이터 흐름 다이어그램

### 7.1 채팅 전체 흐름

```
[Android]                              [Server]                    [External]
    │                                      │                           │
    │  1. ChatRequest (SSE)                │                           │
    │─────────────────────────────────────→│                           │
    │                                      │  2. story_state bump      │
    │                                      │─────→ PostgreSQL          │
    │                                      │                           │
    │                                      │  3. analyze_affinity      │
    │                                      │─────────────────────────→│ gpt-4o-mini
    │                                      │←─────────────────────────│
    │                                      │                           │
    │                                      │  4. memory context        │
    │                                      │─────→ PostgreSQL          │
    │                                      │─────→ ChromaDB (RAG)      │
    │                                      │─────→ ChromaDB (Episode)  │
    │                                      │                           │
    │                                      │  5. build_system_prompt   │
    │                                      │  (personality + memory    │
    │                                      │   + few-shot + episode)   │
    │                                      │                           │
    │                                      │  6. LLM call              │
    │                                      │─────────────────────────→│ gpt-4o/4o-mini
    │                                      │←─────────────────────────│
    │                                      │                           │
    │                                      │  7. quality gate          │
    │                                      │  (score < 0.4 → retry)   │
    │                                      │                           │
    │  8. SSE events (Message/Done)        │                           │
    │←─────────────────────────────────────│                           │
    │                                      │                           │
    │  9. 로컬 저장 (Room)                  │  9. 백그라운드 품질 평가   │
    │  10. 감정 업데이트                     │─────────────────────────→│ gpt-4o-mini
    │  11. 호감도 반영                       │                          │
    │  12. 메모리 추출 요청                  │  10. metric_events 기록   │
    │─────────────────────────────────────→│─────→ PostgreSQL          │
```

### 7.2 기억 시스템 흐름

```
대화 10턴마다:
    │
    ├─ summarize_conversation()
    │   └─ gpt-4o-mini → conversation_memory.summary (PostgreSQL)
    │
    ├─ extract_facts()
    │   └─ gpt-4o-mini → conversation_memory.facts (PostgreSQL)
    │
    ├─ extract_memories()
    │   └─ gpt-4o-mini → char_{id} 컬렉션 (ChromaDB)
    │
    └─ extract_episodes()
        └─ gpt-4o-mini → ep_{id} 컬렉션 (ChromaDB)

프롬프트 구성 시:
    │
    ├─ build_memory_context() → 요약 + 핵심정보
    ├─ search_relevant() → RAG 시맨틱 검색 (top 3)
    └─ search_episodes() → 시간 가중 에피소드 (top 3)
```

---

## 8. 주요 의존성

### 8.1 서버 (requirements.txt)

```
fastapi==0.115.0           # 웹 프레임워크
uvicorn==0.30.6            # ASGI 서버
openai==1.51.0             # OpenAI API
chromadb==0.5.23           # 벡터 스토어
psycopg[binary]==3.2.3     # PostgreSQL 드라이버
firebase-admin==6.5.0      # Firebase Admin SDK
slowapi==0.1.9             # Rate limiting
sse-starlette==2.1.0       # SSE 스트리밍
python-dotenv==1.0.1       # 환경변수
pydantic==2.9.2            # 데이터 검증
```

### 8.2 Android (build.gradle.kts 주요)

```kotlin
// UI
compose-bom: "2025.02.00"
navigation-compose: "2.8.9"
lottie-compose: "6.6.2"
coil-compose: "2.7.0"

// DI
hilt: "2.51.1"
hilt-navigation-compose: "1.2.0"

// Database
room: "2.6.1"

// Network
retrofit: "2.11.0"
okhttp: "4.12.0"
moshi: "1.15.1"

// Firebase
firebase-bom: "33.10.0"
firebase-auth, firebase-messaging, firebase-firestore, firebase-config

// Auth
credentials: "1.5.0-rc01"
googleid: "1.1.1"

// Storage
datastore-preferences: "1.1.2"
```
