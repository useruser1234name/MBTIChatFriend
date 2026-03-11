package com.example.mbtichatfriend.ui.home

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.remote.TrendingPostUi

data class MemoryShortcutState(
    val memoryCount: Int = 0,
    val latestMemoryTitle: String = ""
)

sealed class HomeUiState {
    object Loading : HomeUiState()
    data class Success(
        val characters: List<CharacterEntity> = emptyList(),
        val selectedCharacter: CharacterEntity? = null,
        val memoryShortcut: MemoryShortcutState = MemoryShortcutState(),
        val hasLetter: Boolean = false,
        val openBetaBanner: Boolean = false,
        val dau10kBanner: Boolean = false,
        val trendingPosts: List<TrendingPostUi> = emptyList(),
        // 신년 바이럴 카드: 2027년 1월 1일~10일 기간에만 노출
        val showNewYearCard: Boolean = false,
        // 화이트데이 특집 배너: 3월 13~14일에만 노출 (25차 스프린트)
        val showWhiteDay: Boolean = false,
        // 가정의 달 감사 카드: 4월 24일~5월 8일에만 노출 (26차 스프린트)
        val showGratitudeCard: Boolean = false,
        // 8종 LoRA 완성 배너 (27차 스프린트)
        val showLora8Banner: Boolean = false,
        // 가정의 달 사전 홍보 배너: 2027년 4월 10일~23일에만 노출 (28차 스프린트)
        val showGratitudeTeaser: Boolean = false,
        // 9종 LoRA 완성 배너 (30차 스프린트)
        val showLora9Banner: Boolean = false,
        // 이벤트 트렌딩 게시글 (30차 스프린트)
        val eventTrendingPosts: List<com.example.mbtichatfriend.ui.community.CommunityPostUi> = emptyList(),
        // 어린이날 시즌 카드 (31차 스프린트): 2027년 5월 1일~5일에만 노출
        val showChildrenDay: Boolean = false,
        // ESFP 10종 완성 배너 (33차 스프린트)
        val showEsfp10Banner: Boolean = false,
        // ENTJ 11종 완성 배너 (34차 스프린트)
        val showEntj11Banner: Boolean = false,
        // ISTJ 12종 완성 배너 (34차 스프린트)
        val showIstj12Banner: Boolean = false,
        // ESTP 13종 완성 배너 (35차 스프린트)
        val showEstp13Banner: Boolean = false,
        // 여름 바이럴 카드 섹션 (34차 스프린트): 6~8월에만 노출
        val showSummerCard: Boolean = false,
        // ENFJ 14종 완성 배너 (36차 스프린트)
        val showEnfj14Banner: Boolean = false,
        // 16종 전체 완성 배너 (37차 스프린트)
        val showAllMbtiBanner: Boolean = false,
    ) : HomeUiState()
    data class Error(val message: String) : HomeUiState()
}
