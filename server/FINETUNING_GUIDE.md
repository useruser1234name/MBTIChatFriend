# MBTI Chat Fine-Tuning Guide

MBTI Chat 캐릭터의 응답 품질을 높이기 위한 파인튜닝 전체 가이드.

---

## 1. 개요

### 파인튜닝이란?

기본 GPT 모델(gpt-4o-mini)을 특정 캐릭터의 MBTI 성격, 말투, 호감도 패턴에 맞게 **추가 학습**시키는 과정.
파인튜닝 후에는 프롬프트만으로는 불가능한 수준의 일관된 캐릭터 유지가 가능해진다.

### 파인튜닝 파이프라인

```
대화 데이터 수집 → 품질 필터링 → 합성 데이터 보강 → JSONL 생성 → OpenAI 업로드 → Fine-tuning Job → 모델 활성화
```

---

## 2. 데이터 소스

### 2A. 실제 대화 데이터 (자동 수집)

사용자와 캐릭터 간의 실제 대화가 자동으로 저장된다.

**품질 필터링 기준** (`quality_service.py`):
- `quality_score >= 0.6` 이상만 학습 데이터로 채택
- 사용자가 thumbs_down한 응답은 제외
- 4축 평가: MBTI 일관성(30%) + 맥락 적절성(30%) + 감정 자연스러움(20%) + 몰입도(20%)

**파일**: `server/app/quality_service.py` → `get_quality_filtered_conversations()`

### 2B. 합성 데이터 (수동 생성)

gpt-4o를 사용해 다양한 시나리오의 고품질 대화를 자동 생성.

**파일**: `server/generate_synthetic_data.py`

---

## 3. 합성 데이터 생성

### 3A. 기본 사용법

```bash
# 단일 MBTI + 호감도 조합
python generate_synthetic_data.py --mbti INTJ --affinity 3 --count 50 --output synthetic_intj_lv3.jsonl

# 특정 MBTI의 전 호감도 레벨
python generate_synthetic_data.py --mbti ENFP --affinity 1 --count 20 --output enfp_lv1.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 2 --count 20 --output enfp_lv2.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 3 --count 30 --output enfp_lv3.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 4 --count 20 --output enfp_lv4.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 5 --count 20 --output enfp_lv5.jsonl

# 전체 조합 (16 MBTI x 5 호감도 = 80 조합) - 시간 오래 걸림
python generate_synthetic_data.py --all --count-per-combo 10 --output synthetic_all.jsonl
```

### 3B. 옵션 설명

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--mbti` | MBTI 유형 (INTJ, ENFP 등) | 필수 (--all 아닐 때) |
| `--affinity` | 호감도 레벨 (1-5) | 3 |
| `--count` | 생성할 대화 수 | 10 |
| `--output` | 출력 JSONL 파일 경로 | synthetic_data.jsonl |
| `--all` | 전체 MBTI x 호감도 조합 생성 | false |
| `--count-per-combo` | --all 사용 시 조합당 생성 수 | 5 |
| `--nickname` | 사용자 닉네임 | "사용자" |
| `--character-name` | 캐릭터 이름 | "캐릭터" |

### 3C. 시나리오 카테고리

생성되는 대화는 5가지 카테고리에서 호감도에 따라 가중치 선택된다:

| 카테고리 | 설명 | 호감도 1 비중 | 호감도 5 비중 |
|----------|------|:----:|:----:|
| `daily` | 일상 대화 (날씨, 음식, 취미) | 50% | 15% |
| `emotional` | 감정 상황 (스트레스, 기쁨, 외로움) | 10% | 30% |
| `conflict` | 갈등/토론 | 0% | 10% |
| `advice` | 조언 요청 (진로, 관계) | 20% | 10% |
| `bonding` | 유대 강화 (추억, 여행 계획) | 20% | 35% |

### 3D. 출력 형식

OpenAI fine-tuning JSONL 형식:

```jsonl
{"messages": [{"role": "system", "content": "시스템 프롬프트..."}, {"role": "user", "content": "안녕!"}, {"role": "assistant", "content": "[{\"text\": \"안녕~!\", \"emotion\": \"HAPPY\"}]"}]}
```

### 3E. 권장 데이터 규모

| 목적 | MBTI당 대화 수 | 총 데이터 | 예상 비용 |
|------|:----:|:----:|:----:|
| 최소 테스트 | 10개 | ~160개 | ~$5 |
| 기본 학습 | 50개 | ~800개 | ~$25 |
| 권장 품질 | 100개 | ~1,600개 | ~$50 |
| 고품질 | 200개 | ~3,200개 | ~$100 |

---

## 4. 파인튜닝 실행

### 4A. API 기반 자동 파인튜닝

서버 엔드포인트를 통해 실행 (실제 대화 데이터 + 합성 데이터 병합):

```bash
# POST /finetune/start
curl -X POST http://localhost:8000/finetune/start \
  -H "Content-Type: application/json" \
  -d '{
    "character_id": "char_abc123",
    "character_name": "미래",
    "mbti": "INTJ",
    "speech_style": "CASUAL",
    "relationship": "FRIEND",
    "nickname": "사용자",
    "affinity_level": 3,
    "synthetic_file": "./synthetic_intj_lv3.jsonl"
  }'
```

### 4B. 수동 파인튜닝 (OpenAI CLI)

```bash
# 1. 합성 데이터 생성
python generate_synthetic_data.py --mbti INTJ --affinity 3 --count 100 --output training_data.jsonl

# 2. 데이터 검증
openai tools fine_tunes.prepare_data -f training_data.jsonl

# 3. 파일 업로드
openai api files.create -f training_data.jsonl -p fine-tune

# 4. 파인튜닝 시작
openai api fine_tuning.jobs.create \
  -m gpt-4o-mini-2024-07-18 \
  -t file-xxxxxx \
  --suffix "mbti-intj"

# 5. 상태 확인
openai api fine_tuning.jobs.retrieve -i ftjob-xxxxxx
```

### 4C. 파인튜닝 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| base model | `gpt-4o-mini-2024-07-18` | 비용 효율적, 충분한 품질 |
| n_epochs | 3 | 기본 3회, 데이터 적으면 5회 권장 |
| suffix | `mbti-{character_id[:8]}` | 모델 식별 접미사 |

### 4D. 비용 예측

gpt-4o-mini 파인튜닝 비용 (2024 기준):
- 학습: ~$0.003 / 1K tokens
- 추론: ~$0.0006 / 1K tokens (input), ~$0.0024 / 1K tokens (output)

| 데이터 규모 | 학습 토큰 | 학습 비용 | 월 추론 비용 (1만 메시지) |
|:----:|:----:|:----:|:----:|
| 100 대화 | ~200K | ~$0.60 | ~$3.00 |
| 500 대화 | ~1M | ~$3.00 | ~$3.00 |
| 1000 대화 | ~2M | ~$6.00 | ~$3.00 |

---

## 5. 모델 활성화 & 라우팅

### 5A. 파인튜닝 모델 활성화

파인튜닝 완료 후 자동 또는 수동 활성화:

```python
# 자동: finetune_service.py 내에서 job 완료 시
activate_model("char_abc123", "ft:gpt-4o-mini-2024-07-18:org::xxxxxxxx")

# 수동: API 호출
# POST /finetune/activate
curl -X POST http://localhost:8000/finetune/activate \
  -d '{"character_id": "char_abc123", "model_id": "ft:gpt-4o-mini-2024-07-18:org::xxxxxxxx"}'
```

활성화 정보는 `./finetune_models.json`에 저장됨.

### 5B. 모델 라우팅 우선순위

```
1. 파인튜닝 모델 (ft:gpt-4o-mini-...) → 항상 최우선
2. 복잡도 기반 라우팅:
   - simple (인사, 짧은 반응, 단순 질문) → gpt-4o-mini
   - complex (감정 상담, 긴 텍스트, 갈등) → gpt-4o
```

**분류 기준** (`_classify_message_complexity()`):
- **simple**: 10자 미만 + 인사/반응 패턴 (안녕, ㅋㅋ, 응, 그래 등)
- **complex**: 50자 초과 또는 감정 키워드 (고민, 힘들, 속상, 우울 등)
- 대화 초반(5턴 미만)은 simple, 이후는 complex 기본

---

## 6. 품질 관리 체계

### 6A. 실시간 품질 평가 (자동)

모든 응답에 대해 백그라운드에서 4축 평가 수행:

| 축 | 가중치 | 설명 |
|----|:----:|------|
| MBTI 일관성 | 30% | 캐릭터 성격에 맞는 응답인지 |
| 맥락 적절성 | 30% | 대화 흐름에 맞는 응답인지 |
| 감정 자연스러움 | 20% | 감정 표현이 자연스러운지 |
| 몰입도 | 20% | 대화를 이어가고 싶게 만드는지 |

### 6B. 응답 전 품질 게이트

LLM 응답 생성 직후, 전송 전에 빠른 품질 체크:

```
score = quick_score(user_msg, ai_response, mbti)
if score < 0.4:  # 매우 저품질
    → 1회 재생성 (temperature 0.9)
```

- `quick_score()`: JSON 형식 검증(40%) + MBTI 일관성 LLM 체크(60%)
- 최대 1회 재생성으로 사용자 지연 최소화

### 6C. 응답 다양성 추적

최근 20개 응답과의 bigram 겹침 비율로 다양성 점수 산출:
- `diversity_score < 0.3` → 경고 이벤트 기록
- 반복적 응답 패턴 조기 감지

### 6D. 학습 데이터 필터링

파인튜닝 학습 데이터 선별 기준:
1. `quality_score >= 0.6` (품질 점수 기준)
2. thumbs_down 피드백이 없는 응답만
3. 합성 데이터와 실제 데이터 병합 후 셔플

---

## 7. 6단계 품질 개선 시스템 요약

### Phase 1: Few-Shot 예시

시스템 프롬프트에 MBTI 그룹 x 호감도별 대화 예시 2개를 자동 삽입.
모델이 "이런 느낌"을 즉시 파악할 수 있게 함.

```
NT(low): 건조하고 분석적 → "...책 읽고 있었는데. 왜?"
NF(high): 감성적이고 애정 넘침 → "나도 진짜 보고 싶었어ㅠㅠ"
```

### Phase 2: 합성 데이터

`generate_synthetic_data.py`로 다양한 시나리오의 학습 데이터를 대량 생성.
실제 대화 데이터가 부족할 때 파인튜닝 품질 보장.

### Phase 3: 에피소드 기억

감정적으로 의미 있는 대화 순간(에피소드)을 ChromaDB에 저장.
시간 가중 검색으로 최근 기억을 더 강하게 반영.

```
decay_factor = exp(-days_ago / 30)
final_score = semantic_score * decay_factor * importance_weight
```

### Phase 4: 품질 게이트

응답 전 빠른 품질 체크 → 저품질(< 0.4) 시 1회 재생성.
형식 검증 + MBTI 일관성 체크.

### Phase 5: 모델 라우팅

메시지 복잡도에 따라 gpt-4o / gpt-4o-mini 자동 선택.
파인튜닝 모델이 있으면 항상 우선.

### Phase 6: 호감도 분석 강화

- 장기 기억(memory_context)을 호감도 분석에 반영
- MBTI 그룹별 가중치 차별화 (NT=논리, NF=감정, ST=실용, SF=관심)
- 이모티콘/반복문자 감정 분석 추가
- 부정문 패턴 확장

---

## 8. 추천 파인튜닝 워크플로

### 신규 캐릭터 런칭 시

```bash
# 1. 합성 데이터 생성 (호감도 3 위주, 1&5도 포함)
python generate_synthetic_data.py --mbti ENFP --affinity 1 --count 20 --output enfp_lv1.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 3 --count 60 --output enfp_lv3.jsonl
python generate_synthetic_data.py --mbti ENFP --affinity 5 --count 20 --output enfp_lv5.jsonl

# 2. 합치기
cat enfp_lv1.jsonl enfp_lv3.jsonl enfp_lv5.jsonl > enfp_combined.jsonl

# 3. 파인튜닝 시작 (API 또는 수동)
# synthetic_file 파라미터로 합성 데이터 전달
```

### 운영 중 품질 개선 시

1. 품질 대시보드에서 낮은 점수 카테고리 확인
2. 해당 카테고리 시나리오 합성 데이터 추가 생성
3. 기존 실제 대화 + 합성 데이터 병합 후 재학습
4. A/B 테스트로 개선 확인

### 주기적 재학습

- **주 1회**: 품질 지표 모니터링
- **월 1회**: 새로운 실제 대화 데이터로 재학습 검토
- **분기 1회**: 합성 데이터 시나리오 업데이트

---

## 9. 트러블슈팅

### 문제: 파인튜닝 후 응답이 오히려 나빠짐

**원인**: 학습 데이터 품질 부족 또는 overfitting
**해결**:
- `min_quality` 임계값을 0.7로 올려서 데이터 재필터링
- `n_epochs`를 2로 줄여서 재학습
- 합성 데이터 비율을 높여서 다양성 확보

### 문제: 캐릭터가 MBTI 성격과 다르게 응답

**원인**: Few-shot 예시 부족 또는 시스템 프롬프트와 학습 데이터 불일치
**해결**:
- 해당 MBTI 그룹의 합성 데이터를 추가 생성
- build_system_prompt()의 MBTI 성격 설명 강화
- 파인튜닝 시 시스템 프롬프트를 학습 데이터에 포함했는지 확인

### 문제: 반복적인 응답 패턴

**원인**: 학습 데이터 다양성 부족
**해결**:
- 다양한 시나리오 카테고리의 합성 데이터 추가
- `check_diversity()` 경고 확인 후 해당 패턴 제외
- temperature 파라미터 미세 조정 (0.85 → 0.9)

### 문제: "insufficient_data" 에러

**원인**: 최소 10개의 학습 예시 필요
**해결**:
- 합성 데이터를 `synthetic_file` 파라미터로 보충
- 실제 대화를 더 축적한 후 재시도

---

## 10. 파일 참조

| 파일 | 역할 |
|------|------|
| `server/generate_synthetic_data.py` | 합성 데이터 생성 CLI |
| `server/app/finetune_service.py` | 파인튜닝 파이프라인 (준비, 업로드, 잡 생성, 모델 관리) |
| `server/app/quality_service.py` | 품질 평가 (score_response_async, quick_score, check_diversity) |
| `server/app/chat_service.py` | 모델 라우팅, 품질 게이트, 호감도 분석 |
| `server/app/prompts.py` | 시스템 프롬프트 빌더, Few-shot 예시 |
| `server/app/vector_store.py` | ChromaDB 벡터 스토어 (기억 + 에피소드) |
| `server/app/memory_service.py` | 대화 요약, 핵심 정보 추출, 에피소드 추출 |
| `server/evaluate.py` | 오프라인 품질 평가 (7개 카테고리) |
| `./finetune_models.json` | 캐릭터별 파인튜닝 모델 ID 매핑 |
