# Sprint 2 QA Report - 일관성/접근성

> Sprint 기간: Week 2
> 테스트일: 2026-03-11

---

## 1. MBTI 그룹 분류 통일

### 1.1 Android `PresetCharacters.kt`

| MBTI | 기존 그룹 | 변경 그룹 | 기준 | 상태 |
|------|-----------|-----------|------|------|
| ISTJ | SJ | **ST** | S+T | ✅ |
| ISTP | SP | **ST** | S+T | ✅ |
| ESTJ | SJ | **ST** | S+T | ✅ |
| ESTP | SP | **ST** | S+T | ✅ |
| ISFJ | SJ | **SF** | S+F | ✅ |
| ISFP | SP | **SF** | S+F | ✅ |
| ESFJ | SJ | **SF** | S+F | ✅ |
| ESFP | SP | **SF** | S+F | ✅ |
| NT 4종 | NT | NT (변경 없음) | N+T | ✅ |
| NF 4종 | NF | NF (변경 없음) | N+F | ✅ |

### 1.2 서버-Android 일치 확인

| 항목 | Server (`chat_service.py`) | Android (`PresetCharacters.kt`) | 일치 |
|------|---------------------------|--------------------------------|------|
| INTJ | NT | NT | ✅ |
| INFP | NF | NF | ✅ |
| ISTJ | ST | ST | ✅ |
| ISFJ | SF | SF | ✅ |
| ESTP | ST | ST | ✅ |
| ESFP | SF | SF | ✅ |

### 1.3 참조 검증

| 검증 항목 | 결과 |
|-----------|------|
| `MbtiGroup.SJ` 참조 없음 | ✅ (grep 결과 0건) |
| `MbtiGroup.SP` 참조 없음 | ✅ (grep 결과 0건) |
| 문자열 "SJ"/"SP" 직접 참조 없음 | ✅ |
| enum 값 `ST`, `SF` 정상 정의 | ✅ |

---

## 2. 접근성 보완

### 2.1 터치 타겟 확대

| 파일 | 컴포넌트 | 기존 | 변경 | 상태 |
|------|----------|------|------|------|
| ChatScreen.kt:788 | 좋아요 IconButton | 28dp | **48dp** | ✅ |
| ChatScreen.kt:808 | 아쉬워요 IconButton | 28dp | **48dp** | ✅ |

### 2.2 contentDescription 추가

| 파일 | 라인 | 아이콘 | 추가된 설명 | 상태 |
|------|------|--------|-------------|------|
| CharacterProfileScreen.kt:314 | Delete | "캐릭터 삭제" | ✅ |
| CharacterProfileScreen.kt:326 | Phone | "음성 통화" | ✅ |
| CharacterProfileScreen.kt:338 | MenuBook | "일기 보기" | ✅ |
| CharacterProfileScreen.kt:352 | Chat | "대화하기" | ✅ |
| HomeScreen.kt:403 | ArrowForward | "갤러리로 이동" | ✅ |
| HomeScreen.kt:440 | ArrowForward | "이상형 만들기" | ✅ |
| HomeScreen.kt:484 | Add | "캐릭터 선택" | ✅ |
| DiaryScreen.kt:296 | Refresh | "다시 생성" | ✅ |
| DiaryScreen.kt:314,342 | AutoAwesome | "일기 생성" | ✅ |

### 2.3 접근성 수준 평가

| WCAG 기준 | 기존 | 개선 후 |
|-----------|------|---------|
| 1.1.1 비텍스트 콘텐츠 | ❌ 16건 미비 | ✅ 주요 9건 해결 |
| 2.5.5 터치 타겟 크기 | ❌ 28dp 존재 | ✅ 48dp 이상 |

---

## 3. 변경 파일 목록

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `PresetCharacters.kt` | 수정 | MbtiGroup SJ/SP → ST/SF, 캐릭터 재분류 |
| `ChatScreen.kt` | 수정 | 피드백 버튼 28dp → 48dp |
| `CharacterProfileScreen.kt` | 수정 | contentDescription 4건 추가 |
| `HomeScreen.kt` | 수정 | contentDescription 3건 추가 |
| `DiaryScreen.kt` | 수정 | contentDescription 3건 추가 |

---

## 4. 미완료 항목

| 항목 | 사유 | 후속 조치 |
|------|------|-----------|
| 간이 MBTI 테스트 UI | 새 화면 구현 필요 (대규모 작업) | Sprint 3-4에서 별도 진행 |
| SettingsScreen contentDescription | 2건 | Sprint 3에서 보완 |
| LoginScreen contentDescription | 1건 | Sprint 3에서 보완 |
