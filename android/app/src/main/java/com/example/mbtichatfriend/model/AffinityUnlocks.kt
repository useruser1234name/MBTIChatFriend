package com.example.mbtichatfriend.model

object AffinityUnlocks {
    data class UnlockItem(
        val level: Int,
        val title: String,
        val description: String,
        val icon: String
    )

    val unlocks = listOf(
        UnlockItem(1, "첫 만남", "기본 대화가 가능해요", "\uD83D\uDC4B"),
        UnlockItem(2, "별명 부르기", "캐릭터가 별명으로 불러줘요", "\uD83D\uDCAC"),
        UnlockItem(2, "일기 열람", "캐릭터의 일기를 볼 수 있어요", "\uD83D\uDCD4"),
        UnlockItem(3, "음성 통화", "캐릭터와 통화할 수 있어요", "\uD83D\uDCDE"),
        UnlockItem(3, "깊은 대화", "고민 상담이 가능해요", "\uD83D\uDCAD"),
        UnlockItem(4, "특별 이모지", "전용 감정 표현이 해금돼요", "\u2728"),
        UnlockItem(4, "기억 열람", "캐릭터가 기억하는 것을 볼 수 있어요", "\uD83E\uDDE0"),
        UnlockItem(5, "특별 이벤트", "캐릭터와의 특별한 순간", "\uD83D\uDC95"),
    )

    fun getUnlockedItems(level: Int): List<UnlockItem> = unlocks.filter { it.level <= level }
    fun getNextUnlocks(level: Int): List<UnlockItem> = unlocks.filter { it.level == level + 1 }
    fun getLevelName(level: Int): String = when (level) {
        1 -> "낯선 사이"
        2 -> "지인"
        3 -> "친구"
        4 -> "절친"
        5 -> "연인"
        else -> "낯선 사이"
    }
    fun getLevelEmoji(level: Int): String = when (level) {
        1 -> "\uD83D\uDC4B"
        2 -> "\uD83D\uDE0A"
        3 -> "\uD83E\uDD1D"
        4 -> "\uD83C\uDF1F"
        5 -> "\uD83D\uDC96"
        else -> "\uD83D\uDC4B"
    }
}
