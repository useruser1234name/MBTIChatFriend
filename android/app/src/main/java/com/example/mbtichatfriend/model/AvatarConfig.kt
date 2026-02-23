package com.example.mbtichatfriend.model

import androidx.compose.ui.graphics.Color

/**
 * Compose 아바타 빌더 설정 데이터 클래스.
 *
 * toId() → "v2:0,0,0,0,true,0,0" 형태로 직렬화.
 * fromId() → 역직렬화. "v2:" 접두사 없는 값은 구형 CharacterAvatar enum.
 */
data class AvatarConfig(
    val skinTone: Int = 0,       // 0-4
    val hairStyle: Int = 0,      // 0-5
    val hairColor: Int = 0,      // 0-7
    val eyeStyle: Int = 0,       // 0-3
    val blushEnabled: Boolean = true,
    val accessory: Int = 0,      // 0-5  (0 = 없음)
    val bgColorIndex: Int = 0    // 0-7
) {
    companion object {
        val SKIN_TONES = listOf(
            Color(0xFFFDE8D0), Color(0xFFF5CBA7),
            Color(0xFFE8B89A), Color(0xFFCA8A5B), Color(0xFF8D5524)
        )
        val SKIN_TONE_NAMES = listOf("연한 피부", "밝은 피부", "보통 피부", "갈색 피부", "진한 피부")

        val HAIR_COLORS = listOf(
            Color(0xFF1A1A1A), Color(0xFF5C3317),
            Color(0xFFD4A017), Color(0xFFCC3300),
            Color(0xFFFF69B4), Color(0xFF4169E1),
            Color(0xFF8B5CF6), Color(0xFFF0F0F0)
        )
        val HAIR_COLOR_NAMES = listOf("검정", "갈색", "금발", "빨강", "핑크", "블루", "보라", "흰색")

        val HAIR_STYLE_NAMES = listOf("긴 생머리", "단발", "트윈테일", "포니테일", "짧은 머리", "올림머리")
        val EYE_STYLE_NAMES  = listOf("기본 눈", "큰 눈", "반달 눈", "별 눈")
        val ACCESSORY_NAMES  = listOf("없음", "리본", "왕관", "안경", "고양이귀", "꽃")

        val BG_COLORS = listOf(
            0xFFFFB5C2L, 0xFFC9B1FFL, 0xFFFFF3B0L, 0xFFFFD4A8L,
            0xFFB5E8D5L, 0xFFB8D4FFL, 0xFFB8C5D6L, 0xFFD4A8FFL
        )
        val BG_COLOR_NAMES = listOf("핑크", "퍼플", "옐로우", "오렌지", "민트", "스카이", "아이보리", "라벤더")

        fun fromId(id: String): AvatarConfig {
            if (!id.startsWith("v2:")) return AvatarConfig()
            val parts = id.removePrefix("v2:").split(",")
            if (parts.size < 7) return AvatarConfig()
            return try {
                AvatarConfig(
                    skinTone      = parts[0].toInt(),
                    hairStyle     = parts[1].toInt(),
                    hairColor     = parts[2].toInt(),
                    eyeStyle      = parts[3].toInt(),
                    blushEnabled  = parts[4] == "true",
                    accessory     = parts[5].toInt(),
                    bgColorIndex  = parts[6].toInt()
                )
            } catch (_: Exception) { AvatarConfig() }
        }

        /** avatarId가 구형이든 신형이든 배경 색상(Long)을 반환 */
        fun bgColorLong(avatarId: String): Long {
            return when {
                avatarId.startsWith("img:") -> 0xFFB8D4FFL
                avatarId.startsWith("v2:") -> fromId(avatarId).bgColor
                else -> CharacterAvatar.fromId(avatarId).colorHex
            }
        }
    }

    fun toId(): String = "v2:$skinTone,$hairStyle,$hairColor,$eyeStyle,$blushEnabled,$accessory,$bgColorIndex"

    val skinColor   get() = SKIN_TONES[skinTone.coerceIn(0, SKIN_TONES.lastIndex)]
    val hairColorValue get() = HAIR_COLORS[hairColor.coerceIn(0, HAIR_COLORS.lastIndex)]
    val bgColor     get() = BG_COLORS[bgColorIndex.coerceIn(0, BG_COLORS.lastIndex)]
}
