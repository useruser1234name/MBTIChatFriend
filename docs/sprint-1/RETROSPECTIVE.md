# Sprint 1 회고 - 보안/안정성

> Sprint 기간: Week 1
> 작성일: 2026-03-11

---

## 목표 달성 현황

| 목표 | 상태 | 비고 |
|------|------|------|
| 콘텐츠 필터 활성화 (서버) | ✅ 완료 | 위기감지 + 허용목록 추가 |
| 콘텐츠 필터 활성화 (Android) | ✅ 완료 | 허용목록 추가 |
| 위기 개입 프로토콜 | ✅ 완료 | Tier1(즉시)/Tier2(부드러운) 분리 |
| PostgreSQL asyncpg 전환 | ✅ 완료 | 커넥션 풀 + 동기 폴백 유지 |
| API 인증 강제 | ✅ 완료 | REQUIRE_AUTH 기본 True |
| 입력 크기 제한 강화 | ✅ 완료 | message 2000자, history 50턴 |

**Sprint 목표 달성률: 100% (6/6)**

---

## 잘한 점 (Keep)

1. **오탐 방지 설계**: 콘텐츠 필터에 허용목록(allowlist)을 함께 구현하여, "죽여주는 맛", "영화에서 살인" 등 오탐을 사전 방지
2. **위기 개입 2단계 분리**: Tier1(즉시 상담 안내)과 Tier2(부드러운 확인) 분리로 과잉 개입 방지
3. **하위 호환성 유지**: asyncpg 도입 시 기존 psycopg 동기 API를 폴백으로 유지하여, 점진적 마이그레이션 가능
4. **안전 시스템 프롬프트 복원**: `get_safety_system_prompt()`에 구체적 가이드라인 추가

---

## 개선할 점 (Try)

1. **기존 동기 호출부 전환**: `story_state_store.py`, `metrics_service.py`, `quality_service.py` 등에서 여전히 동기 `execute()`/`fetchone()` 사용 중 → Sprint 2-3에서 점진적 async 전환
2. **콘텐츠 필터 로깅**: 현재 `logger.info`로만 기록 → 별도 테이블이나 메트릭으로 필터링 통계 수집 필요
3. **위기 키워드 확장**: 현재 한국어만 지원 → 영어 키워드 추가 고려
4. **REQUIRE_AUTH 마이그레이션 안내**: 기존 개발 환경에서 갑자기 인증이 강제되므로, README나 .env.example 업데이트 필요

---

## 배운 점 (Learn)

1. **psycopg3은 이미 비동기 지원**: `psycopg[binary]==3.2.3`은 `psycopg.AsyncConnection`을 제공하지만, asyncpg가 성능과 풀 관리에서 더 성숙함
2. **위기 감지와 콘텐츠 필터는 별개 관심사**: 자살/자해 키워드는 "차단"이 아니라 "개입"이 필요하므로, `check_content()`와 `check_crisis()`를 분리한 것이 적절
3. **허용목록은 초기에 작게 시작**: 허용 패턴이 너무 많으면 실제 유해 콘텐츠가 통과할 위험 → 오탐 보고 기반으로 점진적 확장

---

## 다음 Sprint 준비

**Sprint 2 목표: 일관성/접근성**
1. MBTI 그룹 분류 통일 (Android SJ/SP → ST/SF)
2. 간이 MBTI 테스트 기능 구현
3. 접근성 기본 보완 (contentDescription, 터치 타겟 48dp)

**의존성 확인:**
- Sprint 2의 MBTI 그룹 통일은 서버/Android 양쪽 동시 변경 필요
- MBTI 테스트는 새로운 UI 화면 추가 → Navigation 변경 수반
