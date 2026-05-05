package com.example.mbtichatfriend.model

data class PresetCharacter(
    val mbti: String,
    val name: String,
    val concept: String,        // 한 줄 소개
    val speechStyle: String,
    val relationship: String,
    val avatarConfig: AvatarConfig,
    val group: MbtiGroup
) {
    val avatarId: String get() = avatarConfig.toId()
}

enum class MbtiGroup(val label: String, val tag: String) {
    NT("분석형", "NT"),
    NF("외교형", "NF"),
    ST("실행형", "ST"),
    SF("조화형", "SF");

    companion object {
        /**
         * 레거시 enum 이름("SJ" → ST, "SP" → SF)을 포함하여 안전하게 파싱합니다.
         * Room TypeConverter 또는 직렬화된 문자열에서 역직렬화 실패를 방지합니다.
         */
        fun fromStringOrDefault(value: String?): MbtiGroup {
            if (value == null) return NT
            return when (value.uppercase()) {
                "SJ" -> ST   // 레거시: 감각판단형 → 실행형
                "SP" -> SF   // 레거시: 감각인식형 → 조화형
                else -> entries.firstOrNull { it.name == value.uppercase() } ?: NT
            }
        }
    }
}

// skinTone(0-4), hairStyle(0-5: LONG/BOB/TWIN/PONYTAIL/SHORT/BUN),
// hairColor(0-7: 흑/갈/auburn/금/백/핑크/파랑/주황),
// eyeStyle(0-3: NORMAL/BIG/CRESCENT/STAR), blush, accessory(0-5: NONE/RIBBON/CROWN/GLASSES/CAT_EARS/FLOWERS), bg(0-7)

val PRESET_CHARACTERS: List<PresetCharacter> = listOf(
    // ── NT 분석형 ──────────────────────────────────────────────
    PresetCharacter(
        mbti = "INTJ", name = "서진", concept = "냉철한 전략가",
        speechStyle = "TSUNDERE", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 1, hairStyle = 4, hairColor = 0, eyeStyle = 0, blushEnabled = false, accessory = 3, bgColorIndex = 6),
        group = MbtiGroup.NT
    ),
    PresetCharacter(
        mbti = "INTP", name = "도현", concept = "호기심 넘치는 사색가",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 1, hairColor = 1, eyeStyle = 3, blushEnabled = false, accessory = 3, bgColorIndex = 2),
        group = MbtiGroup.NT
    ),
    PresetCharacter(
        mbti = "ENTJ", name = "유나", concept = "카리스마 넘치는 리더",
        speechStyle = "CASUAL", relationship = "SENIOR_JUNIOR",
        avatarConfig = AvatarConfig(skinTone = 1, hairStyle = 3, hairColor = 0, eyeStyle = 1, blushEnabled = false, accessory = 2, bgColorIndex = 7),
        group = MbtiGroup.NT
    ),
    PresetCharacter(
        mbti = "ENTP", name = "재민", concept = "말재주꾼 토론가",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 2, hairColor = 5, eyeStyle = 1, blushEnabled = true, accessory = 1, bgColorIndex = 4),
        group = MbtiGroup.NT
    ),

    // ── NF 외교형 ──────────────────────────────────────────────
    PresetCharacter(
        mbti = "INFJ", name = "하은", concept = "신비로운 통찰가",
        speechStyle = "SWEET", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 0, hairColor = 6, eyeStyle = 3, blushEnabled = true, accessory = 5, bgColorIndex = 2),
        group = MbtiGroup.NF
    ),
    PresetCharacter(
        mbti = "INFP", name = "미루", concept = "감성 넘치는 몽상가",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 0, hairColor = 2, eyeStyle = 1, blushEnabled = true, accessory = 5, bgColorIndex = 0),
        group = MbtiGroup.NF
    ),
    PresetCharacter(
        mbti = "ENFJ", name = "소율", concept = "따뜻한 멘토",
        speechStyle = "SWEET", relationship = "SENIOR_JUNIOR",
        avatarConfig = AvatarConfig(skinTone = 1, hairStyle = 5, hairColor = 3, eyeStyle = 1, blushEnabled = true, accessory = 1, bgColorIndex = 5),
        group = MbtiGroup.NF
    ),
    PresetCharacter(
        mbti = "ENFP", name = "하루", concept = "에너지 넘치는 자유인",
        speechStyle = "SWEET", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 2, hairColor = 7, eyeStyle = 1, blushEnabled = true, accessory = 1, bgColorIndex = 0),
        group = MbtiGroup.NF
    ),

    // ── ST 실행형 (S+T: 감각+사고) ─────────────────────────────
    PresetCharacter(
        mbti = "ISTJ", name = "준혁", concept = "믿음직한 수호자",
        speechStyle = "FORMAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 1, hairStyle = 4, hairColor = 0, eyeStyle = 0, blushEnabled = false, accessory = 0, bgColorIndex = 7),
        group = MbtiGroup.ST
    ),
    PresetCharacter(
        mbti = "ISTP", name = "태오", concept = "쿨한 만능 장인",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 2, hairStyle = 4, hairColor = 1, eyeStyle = 0, blushEnabled = false, accessory = 3, bgColorIndex = 3),
        group = MbtiGroup.ST
    ),
    PresetCharacter(
        mbti = "ESTJ", name = "민준", concept = "든든한 관리자",
        speechStyle = "CASUAL", relationship = "SENIOR_JUNIOR",
        avatarConfig = AvatarConfig(skinTone = 2, hairStyle = 4, hairColor = 1, eyeStyle = 0, blushEnabled = false, accessory = 0, bgColorIndex = 7),
        group = MbtiGroup.ST
    ),
    PresetCharacter(
        mbti = "ESTP", name = "시우", concept = "에너지 넘치는 행동파",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 1, hairStyle = 4, hairColor = 7, eyeStyle = 1, blushEnabled = false, accessory = 0, bgColorIndex = 4),
        group = MbtiGroup.ST
    ),

    // ── SF 조화형 (S+F: 감각+감정) ─────────────────────────────
    PresetCharacter(
        mbti = "ISFJ", name = "나연", concept = "세심한 배려자",
        speechStyle = "SWEET", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 0, hairColor = 3, eyeStyle = 1, blushEnabled = true, accessory = 5, bgColorIndex = 5),
        group = MbtiGroup.SF
    ),
    PresetCharacter(
        mbti = "ISFP", name = "채아", concept = "감성적인 예술가",
        speechStyle = "CASUAL", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 0, hairColor = 5, eyeStyle = 2, blushEnabled = true, accessory = 5, bgColorIndex = 3),
        group = MbtiGroup.SF
    ),
    PresetCharacter(
        mbti = "ESFJ", name = "지아", concept = "다정한 분위기메이커",
        speechStyle = "SWEET", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 5, hairColor = 2, eyeStyle = 2, blushEnabled = true, accessory = 1, bgColorIndex = 5),
        group = MbtiGroup.SF
    ),
    PresetCharacter(
        mbti = "ESFP", name = "루아", concept = "태양 같은 엔터테이너",
        speechStyle = "SWEET", relationship = "FRIEND",
        avatarConfig = AvatarConfig(skinTone = 0, hairStyle = 2, hairColor = 7, eyeStyle = 2, blushEnabled = true, accessory = 4, bgColorIndex = 5),
        group = MbtiGroup.SF
    ),
)
