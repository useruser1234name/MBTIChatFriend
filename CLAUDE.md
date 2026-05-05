# MBTIChatFriend

MBTI 기반 AI 채팅 친구 앱. 16가지 MBTI 성격 유형의 캐릭터와 대화하며 호감도를 키워나가는 관계 시뮬레이션.

## Tech Stack

- **Android**: Kotlin, Jetpack Compose, Hilt (DI), Room (DB v7), Retrofit + SSE, Lottie
- **Server**: Python 3.13, FastAPI, Uvicorn, SSE Starlette, SlowAPI (rate limit)
- **AI**: OpenAI GPT-4.1 / GPT-4.1-mini (복잡도 기반 라우팅), DALL-E, Fine-tuning
- **DB**: PostgreSQL (asyncpg), Room (Android 로컬), ChromaDB (벡터 검색)
- **Auth**: Firebase Auth + FCM + Storage
- **Build**: Gradle KSP, compileSdk 35, minSdk 28, Java 17, Kotlin 1.9
- **Test**: pytest (server), 72 tests

## Project Structure

```
android/app/src/main/java/com/example/mbtichatfriend/
├── data/
│   ├── local/           # Room DB: 5 Entity, 5 DAO, 7 Migrations
│   ├── remote/          # Retrofit ChatApi, SseClient, Firebase 연동
│   ├── repository/      # Chat, Character, Auth, Diary, Memory, Finetune
│   └── voice/           # TTS, SpeechRecognizer
├── di/AppModule.kt      # Hilt: Room, Retrofit(OkHttp+AuthInterceptor), Moshi, TTS
├── model/               # PresetCharacters(16종), CharacterEmotion, AvatarConfig
├── navigation/          # Route sealed class(14개), BottomNavItem(3), AppNavHost
└── ui/                  # 10 screens + components + theme
    ├── splash, login, onboarding(5), home, chat
    ├── character, diary, gallery, voicecall, settings
    ├── components/      # CharacterFaceCanvas, LiveCharacter, Lottie 애니메이션
    └── theme/           # 파스텔 핑크/보라, 다크모드

server/app/
├── main.py              # FastAPI endpoints (REST + SSE), CORS, rate limit 30/min
├── chat_service.py      # 핵심: LLM 호출, 호감도 병렬 분석, 일기 생성, 복잡도 라우팅
├── prompts.py           # MBTI별 시스템 프롬프트 (1100줄+), prefix caching 최적화
├── models.py            # Pydantic request/response schemas, MBTI 16종 validation
├── auth_middleware.py   # Firebase token 검증, require_auth_always
├── content_filter.py    # 콘텐츠 안전 필터 + 2-tier 위기 감지
├── quality_service.py   # 형식 검증 quick_score, 비동기 품질 평가, 다양성 추적
├── memory_service.py    # 대화 요약, 팩트 추출, 에피소드 추출 → ChromaDB
├── finetune_service.py  # OpenAI fine-tuning (gpt-4.1-mini-2025-04-14 base)
├── image_service.py     # DALL-E 이미지 + 표정 세트(15종) 생성
├── firebase_service.py  # FCM 푸시 알림
├── story_state_store.py # 스토리 진행 상태 (턴, 콜백)
├── postgres.py          # asyncpg(async) / psycopg(sync fallback) 이중 접근
└── vector_store.py      # ChromaDB 벡터 임베딩 (RAG)

server/tests/            # pytest 5개 파일, 72 tests
```

## Architecture Patterns

- **Android**: MVVM + Repository 패턴, 단방향 데이터 흐름 (StateFlow)
- **Server**: Layered (endpoint → service → DB/LLM), fire-and-forget 품질 평가
- **DI**: Hilt `@Inject` (Android), FastAPI `Depends` (Server)
- **Navigation**: `Route` sealed class로 타입 안전 라우팅, Compose Navigation

## Core Systems

### 호감도 시스템
- 0-100 점수, 5단계 (1=낯선 사이 → 5=연인)
- LLM 호감도 분석은 메인 응답과 `asyncio.create_task`로 병렬 실행
- 시간 기반 감쇠 (7일 이후), 복귀 보너스

### 채팅 파이프라인
- 복잡도 분류 → 모델 선택 (complex=gpt-4.1, simple=gpt-4.1-mini)
- 응답 형식: `[{"text": "...", "emotion": "EMOTION_CODE"}]` JSON 배열
- quick_score 형식 검증(~1ms) → 임계값 0.4 미만이면 재생성
- 비동기 품질 평가 (score_response_async) fire-and-forget
- 10턴마다 대화 요약 + 팩트 추출 + 에피소드 추출

### 감정 코드
`NEUTRAL | HAPPY | SHY | SAD | ANGRY | SURPRISED | LOVE | PLAYFUL | WORRIED | TOUCHED`

### 프롬프트 구조 (prefix caching 최적화)
1. 정적: 출력 형식, 캐릭터 성격, 말투, 감정, 습관, 표현 규칙, 대화 규칙
2. 반동적: 역할 설정, 관계, 호감도, 궁합, few-shot
3. 동적: 대화 요약, 기억, 에피소드 (매 호출 변경)

### 콘텐츠 안전
- 입력 필터: 성적/폭력/혐오 차단, 허용 목록 (음식/영화 표현)
- 위기 감지: Tier1 (자해/자살 → 즉시 개입), Tier2 (무의미/포기 → 부드러운 안내)
- 레이트 리밋: 30 req/min

## Code Conventions

### Android
- Hilt DI만 사용, 수동 생성자 호출 금지
- Room Migration 순차 관리 (현재 v7)
- Compose 애니메이션: Lottie(감정), 300ms 슬라이드(전환)
- 모든 Screen은 ViewModel과 1:1 매핑

### Server
- 모든 LLM 호출은 gpt-4.1 / gpt-4.1-mini (gpt-4o 사용 금지)
- `_MODEL_COSTS` dict에 이전 모델 유지 (비용 추적용)
- finetuned 모델 감지: `not in ("gpt-4o", "gpt-4.1")` 로 base 모델 제외
- 비동기 우선: asyncpg > psycopg fallback
- 테스트: `cd server && python -m pytest tests/ -v`

### 공통
- MBTI 16종: INTJ, INTP, ENTJ, ENTP, INFJ, INFP, ENFJ, ENFP, ISTJ, ISFJ, ESTJ, ESFJ, ISTP, ISFP, ESTP, ESFP
- 메시지 최대 2000자, 대화 히스토리 최대 50턴
- 한국어 기본, 캐릭터 프롬프트/UI 전부 한국어

## Environment Variables (server/.env)

```
OPENAI_API_KEY=         # Required
DATABASE_URL=           # PostgreSQL connection string
FIREBASE_CREDENTIALS_PATH=
FIREBASE_STORAGE_BUCKET=
ENVIRONMENT=development # development | production
CORS_ORIGINS=           # comma-separated, default "*" in dev
REQUIRE_AUTH=true       # false로 설정 시 인증 우회 (개발용)
HOST=0.0.0.0
PORT=8000
```

## Quick Commands

```bash
# Server
cd server && pip install -r requirements.txt
cd server && uvicorn app.main:app --reload --port 8090
cd server && python -m pytest tests/ -v

# Docker (PostgreSQL + Server)
docker-compose up -d
```
