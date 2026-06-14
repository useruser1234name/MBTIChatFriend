package com.example.mbtichatfriend.ui.home

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.remote.TrendingPostUi

data class MemoryShortcutState(
    val memoryCount: Int = 0,
    val latestMemoryTitle: String = ""
)

/**
 * A-7: 배너 유형 열거 — Boolean 17개 대신 enum 1줄+조건 1줄로 신규 배너 추가.
 * activeBanners: List<BannerType>으로 활성 배너 목록 관리.
 * 기존 Boolean 프로퍼티는 activeBanners에서 파생(하위 호환).
 */
enum class BannerType {
    OPEN_BETA,
    DAU_10K,
    NEW_YEAR_CARD,
    WHITE_DAY,
    GRATITUDE_CARD,
    LORA_8,
    GRATITUDE_TEASER,
    LORA_9,
    CHILDREN_DAY,
    ESFP_10,
    ENTJ_11,
    ISTJ_12,
    ESTP_13,
    SUMMER_CARD,
    ENFJ_14,
    ALL_MBTI,
}

sealed class HomeUiState {
    object Loading : HomeUiState()
    data class Success(
        val characters: List<CharacterEntity> = emptyList(),
        val selectedCharacter: CharacterEntity? = null,
        val memoryShortcut: MemoryShortcutState = MemoryShortcutState(),
        val hasLetter: Boolean = false,
        val trendingPosts: List<TrendingPostUi> = emptyList(),
        val eventTrendingPosts: List<com.example.mbtichatfriend.ui.community.CommunityPostUi> = emptyList(),
        // A-7: 활성 배너 목록 — 이 목록만 보고 HomeScreen이 렌더링 결정
        val activeBanners: List<BannerType> = emptyList(),
    ) : HomeUiState() {
        // 하위 호환 프로퍼티 — Boolean 직접 참조하는 기존 HomeScreen 코드와의 점진적 마이그레이션 지원
        val openBetaBanner: Boolean get() = BannerType.OPEN_BETA in activeBanners
        val dau10kBanner: Boolean get() = BannerType.DAU_10K in activeBanners
        val showNewYearCard: Boolean get() = BannerType.NEW_YEAR_CARD in activeBanners
        val showWhiteDay: Boolean get() = BannerType.WHITE_DAY in activeBanners
        val showGratitudeCard: Boolean get() = BannerType.GRATITUDE_CARD in activeBanners
        val showLora8Banner: Boolean get() = BannerType.LORA_8 in activeBanners
        val showGratitudeTeaser: Boolean get() = BannerType.GRATITUDE_TEASER in activeBanners
        val showLora9Banner: Boolean get() = BannerType.LORA_9 in activeBanners
        val showChildrenDay: Boolean get() = BannerType.CHILDREN_DAY in activeBanners
        val showEsfp10Banner: Boolean get() = BannerType.ESFP_10 in activeBanners
        val showEntj11Banner: Boolean get() = BannerType.ENTJ_11 in activeBanners
        val showIstj12Banner: Boolean get() = BannerType.ISTJ_12 in activeBanners
        val showEstp13Banner: Boolean get() = BannerType.ESTP_13 in activeBanners
        val showSummerCard: Boolean get() = BannerType.SUMMER_CARD in activeBanners
        val showEnfj14Banner: Boolean get() = BannerType.ENFJ_14 in activeBanners
        val showAllMbtiBanner: Boolean get() = BannerType.ALL_MBTI in activeBanners
    }
    data class Error(val message: String) : HomeUiState()
}
