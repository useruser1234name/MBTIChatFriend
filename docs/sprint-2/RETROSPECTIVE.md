# Sprint 2 회고 - 일관성/접근성

> Sprint 기간: Week 2
> 작성일: 2026-03-11

---

## 목표 달성 현황

| 목표 | 상태 | 비고 |
|------|------|------|
| MBTI 그룹 분류 통일 | ✅ 완료 | SJ/SP → ST/SF, 서버와 일치 |
| 접근성 - 터치 타겟 48dp | ✅ 완료 | ChatScreen 피드백 버튼 |
| 접근성 - contentDescription | ✅ 주요 완료 | 9건/16건 해결 |
| 간이 MBTI 테스트 | ⏳ 이월 | 새 화면 구현 필요, Sprint 4로 이월 |

**Sprint 목표 달성률: 75% (3/4)**

---

## 잘한 점 (Keep)

1. **인지기능 기반 분류**: 기존 SJ/SP(기질론)에서 ST/SF(인지기능)로 변경하여, 서버의 Few-Shot 예시, 궁합 계산과 정확히 일치하게 됨
2. **캐릭터 재배치**: 단순 enum 변경이 아니라, 16개 캐릭터를 인지기능 기준으로 정확히 재분류 (예: ISTP는 기존 SP에서 ST로)
3. **참조 검증**: `MbtiGroup.SJ`/`SP` 참조가 다른 파일에 없음을 grep으로 확인하여 누락 변경 방지
4. **핵심 접근성 우선**: 가장 자주 사용되는 화면(Chat, Home, CharacterProfile)의 접근성을 우선 보완

---

## 개선할 점 (Try)

1. **MBTI 테스트 이월**: 간이 MBTI 테스트는 새 화면(16문항 + 결과 + 추천)이 필요하여, 1 스프린트 내에 완성하기 어려움 → 별도 스프린트에서 집중 구현 필요
2. **나머지 contentDescription**: Settings, Login, CreateCharacterSheet의 contentDescription 미수정분이 남아있음
3. **접근성 자동 테스트**: Espresso AccessibilityChecks 또는 Compose Testing의 접근성 검증을 CI에 통합하면, 향후 회귀 방지 가능

---

## 배운 점 (Learn)

1. **MBTI 분류 체계의 차이**: 기질론(SJ/SP/NF/NT)과 인지기능(ST/SF/NF/NT)은 다른 분류 체계. 앱 내에서 하나로 통일하지 않으면 Few-Shot, 궁합, 그룹 필터링 등에서 미묘한 불일치 발생
2. **Compose의 contentDescription**: 버튼 내부 아이콘은 버튼 텍스트가 있으면 null이어도 기능적으로 접근 가능하지만, 명시적으로 설명을 추가하는 것이 더 안전

---

## 다음 Sprint 준비

**Sprint 3 목표: 품질/안전**
1. 기본 단위 테스트 (핵심 비즈니스 로직)
2. 대화 기록 삭제 기능
3. 나머지 접근성 보완 (Settings, Login)

**의존성 확인:**
- 대화 기록 삭제: Room DB + 서버 API 양쪽 구현 필요
- 단위 테스트: content_filter, 호감도 계산 등 독립적 함수부터 시작
