# 서버 설정 가이드

## 요구사항

- Python 3.11+
- OpenAI API 키 (없어도 목업 모드로 동작)
- (Phase 3) chromadb 라이브러리

## 설치

```bash
cd server
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 환경 변수 설정

`server/.env` 파일 생성:

```env
OPENAI_API_KEY=sk-...          # OpenAI API 키 (없으면 목업 모드)
FIREBASE_CREDENTIALS=          # Firebase 서비스 계정 JSON 경로 (FCM 알림용, 선택)
HOST=0.0.0.0
PORT=8000
```

> **목업 모드**: `OPENAI_API_KEY`가 없으면 서버가 MBTI 그룹별 샘플 응답을 반환합니다. 개발·테스트 시 활용하세요.

## 서버 실행

```bash
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Android 에뮬레이터 연결

에뮬레이터에서 서버에 접근하는 주소:

```
http://10.0.2.2:8000/
```

`app/build.gradle.kts`의 `buildConfigField`에서 `BASE_URL`을 위 값으로 설정하세요.

## API 문서

서버 실행 후 브라우저에서 확인:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 주요 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/api/v1/chat/send` | REST 채팅 (하위호환) |
| POST | `/api/v1/chat/stream` | SSE 스트리밍 채팅 |
| POST | `/api/v1/memory/extract` | 대화에서 장기 기억 추출 |
| POST | `/api/v1/diary/generate` | 캐릭터 일기 생성 |
| POST | `/api/v1/finetune/start` | GPT 파인튜닝 시작 |
| GET | `/api/v1/finetune/status/{job_id}` | 파인튜닝 상태 조회 |
| POST | `/api/v1/finetune/activate` | 파인튜닝 모델 활성화 |
| POST | `/api/v1/fcm/register` | FCM 토큰 등록 |
| POST | `/api/v1/fcm/send` | FCM 푸시 알림 발송 |
