package com.example.mbtichatfriend.ui.home

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * HomeUiState.Success 단위 테스트.
 *
 * A-7에서 Boolean 17개를 BannerType enum + activeBanners 리스트로 교체하면서
 * 하위 호환 computed property(get() = BannerType.XXX in activeBanners)가
 * 올바르게 동작하는지 검증한다.
 *
 * 검증 대상:
 * 1. activeBanners 비어 있을 때 모든 computed Boolean == false
 * 2. activeBanners에 특정 BannerType 있을 때 해당 Boolean == true
 * 3. activeBanners에서 BannerType 제거(list subtraction) 후 Boolean == false
 * 4. 복수 배너 동시 활성화 시 각 Boolean 독립 동작
 */
class HomeUiStateTest {

    private fun emptySuccess() = HomeUiState.Success()

    // ------------------------------------------------------------------
    // 1. 빈 activeBanners → 모든 computed Boolean false
    // ------------------------------------------------------------------

    @Test
    fun `all computed banners are false when activeBanners is empty`() {
        val state = emptySuccess()
        assertFalse(state.openBetaBanner)
        assertFalse(state.dau10kBanner)
        assertFalse(state.showNewYearCard)
        assertFalse(state.showWhiteDay)
        assertFalse(state.showGratitudeCard)
        assertFalse(state.showLora8Banner)
        assertFalse(state.showGratitudeTeaser)
        assertFalse(state.showLora9Banner)
        assertFalse(state.showChildrenDay)
        assertFalse(state.showEsfp10Banner)
        assertFalse(state.showEntj11Banner)
        assertFalse(state.showIstj12Banner)
        assertFalse(state.showEstp13Banner)
        assertFalse(state.showSummerCard)
        assertFalse(state.showEnfj14Banner)
        assertFalse(state.showAllMbtiBanner)
    }

    // ------------------------------------------------------------------
    // 2. 단일 BannerType 활성화 → 해당 Boolean true, 나머지 false
    // ------------------------------------------------------------------

    @Test
    fun `openBetaBanner is true when OPEN_BETA is in activeBanners`() {
        val state = emptySuccess().copy(activeBanners = listOf(BannerType.OPEN_BETA))
        assertTrue(state.openBetaBanner)
        assertFalse(state.dau10kBanner)
        assertFalse(state.showAllMbtiBanner)
    }

    @Test
    fun `dau10kBanner is true when DAU_10K is in activeBanners`() {
        val state = emptySuccess().copy(activeBanners = listOf(BannerType.DAU_10K))
        assertTrue(state.dau10kBanner)
        assertFalse(state.openBetaBanner)
    }

    @Test
    fun `showSummerCard is true when SUMMER_CARD is in activeBanners`() {
        val state = emptySuccess().copy(activeBanners = listOf(BannerType.SUMMER_CARD))
        assertTrue(state.showSummerCard)
        assertFalse(state.showAllMbtiBanner)
    }

    @Test
    fun `showAllMbtiBanner is true when ALL_MBTI is in activeBanners`() {
        val state = emptySuccess().copy(activeBanners = listOf(BannerType.ALL_MBTI))
        assertTrue(state.showAllMbtiBanner)
        assertFalse(state.openBetaBanner)
    }

    @Test
    fun `showChildrenDay is true when CHILDREN_DAY is in activeBanners`() {
        val state = emptySuccess().copy(activeBanners = listOf(BannerType.CHILDREN_DAY))
        assertTrue(state.showChildrenDay)
        assertFalse(state.showSummerCard)
    }

    // ------------------------------------------------------------------
    // 3. dismiss 패턴 — list subtraction 후 Boolean false
    // ------------------------------------------------------------------

    @Test
    fun `openBetaBanner becomes false after removing OPEN_BETA from activeBanners`() {
        val initial = emptySuccess().copy(activeBanners = listOf(BannerType.OPEN_BETA, BannerType.DAU_10K))
        assertTrue(initial.openBetaBanner)

        val dismissed = initial.copy(activeBanners = initial.activeBanners - BannerType.OPEN_BETA)
        assertFalse(dismissed.openBetaBanner)
        // 나머지 배너는 영향 없음
        assertTrue(dismissed.dau10kBanner)
    }

    @Test
    fun `all banners dismissed one by one leaves empty list`() {
        var state = emptySuccess().copy(
            activeBanners = listOf(BannerType.OPEN_BETA, BannerType.DAU_10K, BannerType.ALL_MBTI)
        )
        state = state.copy(activeBanners = state.activeBanners - BannerType.OPEN_BETA)
        state = state.copy(activeBanners = state.activeBanners - BannerType.DAU_10K)
        state = state.copy(activeBanners = state.activeBanners - BannerType.ALL_MBTI)

        assertFalse(state.openBetaBanner)
        assertFalse(state.dau10kBanner)
        assertFalse(state.showAllMbtiBanner)
        assertTrue(state.activeBanners.isEmpty())
    }

    // ------------------------------------------------------------------
    // 4. 복수 배너 동시 활성화 — 각 Boolean 독립 동작
    // ------------------------------------------------------------------

    @Test
    fun `multiple banners can be active simultaneously and each Boolean is independent`() {
        val state = emptySuccess().copy(
            activeBanners = listOf(
                BannerType.OPEN_BETA,
                BannerType.SUMMER_CARD,
                BannerType.ALL_MBTI,
            )
        )
        assertTrue(state.openBetaBanner)
        assertTrue(state.showSummerCard)
        assertTrue(state.showAllMbtiBanner)
        assertFalse(state.dau10kBanner)
        assertFalse(state.showEnfj14Banner)
        assertFalse(state.showChildrenDay)
    }

    // ------------------------------------------------------------------
    // 5. BannerType enum exhaustiveness — 모든 16종 값이 존재하는지
    // ------------------------------------------------------------------

    @Test
    fun `BannerType enum has exactly 16 values`() {
        val expected = 16
        val actual = BannerType.entries.size
        org.junit.Assert.assertEquals(
            "BannerType should have exactly $expected values but had $actual",
            expected,
            actual
        )
    }

    @Test
    fun `activeBanners can hold all 16 BannerTypes`() {
        val allBanners = BannerType.entries.toList()
        val state = emptySuccess().copy(activeBanners = allBanners)

        assertTrue(state.openBetaBanner)
        assertTrue(state.dau10kBanner)
        assertTrue(state.showNewYearCard)
        assertTrue(state.showWhiteDay)
        assertTrue(state.showGratitudeCard)
        assertTrue(state.showLora8Banner)
        assertTrue(state.showGratitudeTeaser)
        assertTrue(state.showLora9Banner)
        assertTrue(state.showChildrenDay)
        assertTrue(state.showEsfp10Banner)
        assertTrue(state.showEntj11Banner)
        assertTrue(state.showIstj12Banner)
        assertTrue(state.showEstp13Banner)
        assertTrue(state.showSummerCard)
        assertTrue(state.showEnfj14Banner)
        assertTrue(state.showAllMbtiBanner)
    }
}
