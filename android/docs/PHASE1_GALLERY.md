# Phase 1: 16 MBTI 캐릭터 갤러리

## 개요

16가지 MBTI 유형의 사전 제작 캐릭터를 갤러리에서 탐색하고 내 캐릭터로 추가하는 기능입니다.

## 아키텍처

```
model/PresetCharacters.kt      ← 16개 프리셋 캐릭터 정의
ui/gallery/GalleryScreen.kt    ← 갤러리 화면 (LazyVerticalGrid)
ui/gallery/GalleryViewModel.kt ← 갤러리 ViewModel
data/repository/CharacterRepository.kt  ← addFromPreset()
navigation/Routes.kt           ← Gallery 라우트
```

## 주요 구성 요소

### PresetCharacter 모델

```kotlin
data class PresetCharacter(
    val name: String,
    val mbti: String,
    val speechStyle: String,    // CASUAL, SWEET, TSUNDERE 등
    val relationship: String,   // FRIEND, LOVER, SENIOR_JUNIOR 등
    val avatarId: String,       // "v2:skin,hair,eye,acc,blush,outfit,bg"
    val concept: String         // 캐릭터 소개 문구
)
```

### MbtiGroup 필터

```kotlin
enum class MbtiGroup(val label: String, val emoji: String) {
    NT("분석형", "🔍"),  // INTJ, INTP, ENTJ, ENTP
    NF("외교형", "💫"),  // INFJ, INFP, ENFJ, ENFP
    SJ("관리형", "🛡️"), // ISTJ, ISFJ, ESTJ, ESFJ
    SP("탐험형", "⚡")  // ISTP, ISFP, ESTP, ESFP
}
```

## 사용법

### 사용자 플로우

1. 홈 화면 → **갤러리 배너** 클릭 또는 **+ 버튼** → 빈 상태의 "갤러리에서 고르기" 버튼
2. 갤러리 화면: MBTI 그룹(NT/NF/SJ/SP)으로 필터링 가능
3. 캐릭터 카드 클릭 → 상세 정보 바텀시트 표시
4. **"내 캐릭터로 추가하기"** 버튼 → Room DB에 저장 → 채팅 화면으로 이동

### 개발자 - 새 프리셋 캐릭터 추가

`model/PresetCharacters.kt`에 `PRESET_CHARACTERS` 리스트에 항목 추가:

```kotlin
PresetCharacter(
    name = "지유",
    mbti = "ENFJ",
    speechStyle = "SWEET",
    relationship = "FRIEND",
    avatarId = "v2:2,3,1,0,true,2,5",
    concept = "따뜻한 리더형 NF, 모두를 챙기는 든든한 언니"
)
```

### AvatarId 형식

`v2:skin,hair,eye,acc,blush,outfit,bg`

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| skin | Int (0~3) | 피부색 |
| hair | Int (0~4) | 헤어 스타일 |
| eye | Int (0~3) | 눈 색 |
| acc | Int (0~3) | 액세서리 |
| blush | Boolean | 볼터치 여부 |
| outfit | Int (0~3) | 의상 |
| bg | Int (0~7) | 배경색 |

## API (서버)

갤러리는 클라이언트 전용 기능으로 서버 API 없이 동작합니다.
캐릭터는 Android Room DB에만 저장됩니다.

## 초기 데이터 시딩

앱 최초 설치 시 `CharacterRepository.seedPresetsIfEmpty()`가 자동으로
ENFP / INTJ / ISFJ / ESTP 4개 캐릭터를 생성합니다.
