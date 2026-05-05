# Phase 4: GPT Fine-tuning 파이프라인

## 개요

사용자와 캐릭터의 실제 대화 기록을 훈련 데이터로 활용하여
해당 캐릭터만의 전용 GPT 모델을 생성하는 파이프라인입니다.
파인튜닝 모델은 기본 gpt-4o보다 해당 캐릭터의 말투·성격을 더 정확히 재현합니다.

## 전체 흐름

```
1. 대화 충분히 쌓기 (최소 10회 교환 필요)
         ↓
2. 캐릭터 프로필 → "파인튜닝 시작" 버튼
         ↓
3. Android: 전체 대화 기록 수집 → POST /api/v1/finetune/start
         ↓
4. Server: JSONL 훈련 데이터 생성 → OpenAI Files API 업로드
         ↓
5. Server: Fine-tuning 잡 생성 (gpt-4o-mini, 3 epoch)
         ↓
6. Android: job_id 수신 → "상태 확인" 버튼으로 폴링 (수십 분 소요)
         ↓
7. 완료 시 → "이 모델 활성화하기" 버튼
         ↓
8. 이후 해당 캐릭터와 대화 시 파인튜닝 모델 자동 사용
```

## 훈련 데이터 형식 (JSONL)

각 줄이 하나의 훈련 예시:

```jsonl
{"messages": [{"role": "system", "content": "# 역할 설정\n..."}, {"role": "user", "content": "안녕!"}, {"role": "assistant", "content": "[{\"text\": \"야호~ 왔구나!\", \"emotion\": \"HAPPY\"}]"}]}
{"messages": [{"role": "system", "content": "# 역할 설정\n..."}, {"role": "user", "content": "오늘 힘들었어"}, {"role": "assistant", "content": "[{\"text\": \"어머 무슨 일이야?\", \"emotion\": \"SAD\"}]"}]}
```

## API 레퍼런스

### POST /api/v1/finetune/start

대화 기록으로 파인튜닝 잡을 시작합니다.

**요청**
```json
{
  "character_id": "1",
  "character_name": "하루",
  "mbti": "ENFP",
  "speech_style": "SWEET",
  "relationship": "FRIEND",
  "nickname": "민준",
  "affinity_level": 3,
  "conversations": [
    {"role": "user", "content": "안녕!"},
    {"role": "assistant", "content": "[{\"text\":\"야호!\",\"emotion\":\"HAPPY\"}]"},
    ...
  ]
}
```

**응답 (성공)**
```json
{
  "job_id": "ftjob-abc123",
  "status": "validating_files",
  "training_count": 42,
  "model": "gpt-4o-mini-2024-07-18",
  "error": ""
}
```

**응답 (데이터 부족)**
```json
{
  "job_id": "",
  "status": "insufficient_data",
  "training_count": 7,
  "model": "",
  "error": "훈련 데이터 부족 (현재 7개, 최소 10개 필요)..."
}
```

### GET /api/v1/finetune/status/{job_id}

파인튜닝 진행 상태를 조회합니다.

**응답**
```json
{
  "job_id": "ftjob-abc123",
  "status": "running",          // validating_files | queued | running | succeeded | failed | cancelled
  "fine_tuned_model": "",       // succeeded 시 "ft:gpt-4o-mini:..."
  "error": ""
}
```

### POST /api/v1/finetune/activate

완료된 파인튜닝 모델을 캐릭터에 활성화합니다.

**요청**
```json
{
  "character_id": "1",
  "model_id": "ft:gpt-4o-mini:my-org:mbti-1:abc123"
}
```

**응답**
```json
{
  "status": "ok",
  "character_id": "1",
  "model_id": "ft:gpt-4o-mini:my-org:mbti-1:abc123"
}
```

## 파인튜닝 모델 관리

활성화된 모델은 `server/finetune_models.json`에 저장됩니다:

```json
{
  "1": "ft:gpt-4o-mini:my-org:mbti-1:abc123",
  "3": "ft:gpt-4o-mini:my-org:mbti-3:def456"
}
```

이 파일을 삭제하면 모든 캐릭터가 기본 `gpt-4o`로 돌아갑니다.

## Android UI

캐릭터 프로필 화면 하단에 **파인튜닝 카드**가 표시됩니다:

| 상태 | 표시 |
|------|------|
| Idle | "파인튜닝 시작" 버튼 |
| Loading | 로딩 스피너 |
| JobStarted | 잡 ID + "상태 확인" 버튼 |
| InProgress | 진행 표시 + "새로고침" 버튼 |
| Completed | "이 모델 활성화하기" 버튼 |
| Error | 에러 메시지 + "다시 시도" |

## 비용 안내

| 항목 | 비용 |
|------|------|
| 훈련 (gpt-4o-mini) | $0.0080 / 1K tokens |
| 추론 (파인튜닝 모델) | $0.0120 / 1K tokens (입력) |
| 훈련 예시 42개 기준 | 약 $0.10~0.30 |

> **주의**: 파인튜닝은 실제 비용이 발생합니다. 테스트 시 소량 데이터로 먼저 시도하세요.

## 제한사항

- 최소 훈련 예시: **10개** (더 많을수록 품질 향상)
- 권장 대화 횟수: **50회 이상**
- 파인튜닝 소요 시간: **20분~수 시간** (OpenAI 큐 상황에 따라 변동)
- OpenAI API 키 필수 (목업 모드에서는 동작하지 않음)

## 문제 해결

### "훈련 데이터 부족" 오류

더 많이 대화한 후 시도하세요. 한 번의 user→assistant 교환이 1개의 훈련 예시입니다.

### 파인튜닝 후 응답 품질이 낮을 때

- 훈련 데이터 다양성 부족: 다양한 주제로 대화 후 재시도
- epoch 수 조정: `finetune_service.py`의 `n_epochs` 값 변경 (기본 3)

### 모델 롤백

`server/finetune_models.json`에서 해당 character_id 항목을 삭제하면 기본 gpt-4o로 복귀합니다.
