# Sprint 3 회고 - 품질/안전

> Sprint 기간: Week 3
> 작성일: 2026-03-11

---

## 목표 달성 현황

| 목표 | 상태 | 비고 |
|------|------|------|
| 기본 단위 테스트 | ✅ 완료 | 42개 테스트 (필터, 검증, 분류) |
| 대화 기록 삭제 API | ✅ 완료 | 서버 5테이블 삭제 + 이벤트 로깅 |
| 대화 기록 삭제 모델 | ✅ 완료 | Pydantic 모델 + 엔드포인트 |

**Sprint 목표 달성률: 100% (3/3)**

---

## 잘한 점 (Keep)

1. **핵심 로직 우선 테스트**: content_filter, models, chat_service의 순수 함수를 먼저 테스트하여, 외부 의존성 없이 빠르게 42개 테스트 확보
2. **MBTI 16종 전체 검증**: `test_all_16_types_classified`로 모든 MBTI 유형이 정확한 그룹에 배치되는지 한번에 검증
3. **삭제 API 설계**: room_id / character_id 양쪽으로 삭제 가능하게 하여 유연성 확보
4. **삭제 이벤트 로깅**: 데이터 삭제도 metric_events에 기록하여 감사 추적 가능

---

## 개선할 점 (Try)

1. **ChromaDB 삭제 미구현**: 벡터 스토어에 저장된 에피소드/팩트 데이터 삭제가 아직 안 됨 → GDPR 완전 준수를 위해 필수
2. **Android 측 삭제**: Room DB의 messages, characters, diaries, memories 삭제 + 삭제 API 호출 연동 필요
3. **통합 테스트 부재**: 현재 단위 테스트만 있고, FastAPI TestClient를 사용한 엔드포인트 통합 테스트가 없음
4. **테스트 자동화**: CI/CD에 pytest 실행을 통합해야 함

---

## 배운 점 (Learn)

1. **Pydantic v2의 max_length**: `List[HistoryMessage] = Field(max_length=50)`으로 리스트 길이 제한이 가능
2. **삭제 API의 복잡성**: 5개 테이블 + ChromaDB + 인메모리 캐시 + 파인튜닝 데이터를 모두 정리하려면 트랜잭션 관리가 복잡 → 2단계로 나누어 구현하는 것이 현실적
3. **위기 감지는 차단이 아닌 개입**: 자살/자해 키워드를 "차단"하면 도움이 필요한 사용자를 외면하게 됨 → "개입"(상담 안내)이 올바른 접근

---

## 다음 Sprint 준비

**Sprint 4 목표: 최적화/측정**
1. 프롬프트 최적화 (안전 시스템 프롬프트 통합)
2. 호감도 후퇴 메커니즘 (전문가 합의안)
3. 비용 메트릭 수집 기반 구축

**의존성 확인:**
- 프롬프트 최적화: prompts.py + chat_service.py 수정
- 호감도 후퇴: chat_service.py의 affinity 로직 수정
