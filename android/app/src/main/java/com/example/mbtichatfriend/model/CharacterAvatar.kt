package com.example.mbtichatfriend.model

import com.example.mbtichatfriend.R

enum class CharacterAvatar(
    val displayName: String,
    val description: String,
    val emoji: String,
    val colorHex: Long
) {
    BUNNY("토끼", "깜찍하고 발랄한", "\uD83D\uDC30", 0xFFFFB5C2),
    CAT("고양이", "도도하고 매력적인", "\uD83D\uDC31", 0xFFC9B1FF),
    BEAR("곰", "듬직하고 따뜻한", "\uD83D\uDC3B", 0xFFFFF3B0),
    FOX("여우", "영리하고 장난스러운", "\uD83E\uDD8A", 0xFFFFD4A8),
    PENGUIN("펭귄", "순수하고 사랑스러운", "\uD83D\uDC27", 0xFFB5E8D5),
    DOG("강아지", "충성스럽고 활발한", "\uD83D\uDC36", 0xFFFFE0B2),
    WOLF("늑대", "카리스마 넘치는", "\uD83D\uDC3A", 0xFFB8C5D6),
    DRAGON("용", "신비롭고 강인한", "\uD83D\uDC32", 0xFFD4A8FF),
    UNICORN("유니콘", "환상적이고 우아한", "\uD83E\uDD84", 0xFFFFD1EC),
    HAMSTER("햄스터", "귀엽고 엉뚱한", "\uD83D\uDC39", 0xFFFFE4C9),
    OWL("부엉이", "지적이고 신중한", "\uD83E\uDD89", 0xFFD4C5A9),
    DEER("사슴", "우아하고 순수한", "\uD83E\uDD8C", 0xFFC8E6C9);

    companion object {
        fun fromId(id: String): CharacterAvatar {
            return entries.find { it.name == id } ?: BUNNY
        }
    }
}
