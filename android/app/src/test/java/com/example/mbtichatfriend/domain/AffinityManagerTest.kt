package com.example.mbtichatfriend.domain

import android.util.Log
import app.cash.turbine.test
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.repository.CharacterRepository
import io.mockk.Runs
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.just
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.slot
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * AffinityManager 단위 테스트.
 *
 * 검증 대상:
 * 1. 레벨 경계값 — affinityScore 0/20/21/40/41/60/61/80/81/100 → affinityLevel 1~5
 * 2. handleAffinityDelta — 레벨 상승 시 levelUpEvent 발행
 * 3. handleAffinityDelta — 레벨 하락 시 levelDownEvent 발행
 * 4. handleAffinityDelta — 레벨 변화 없으면 이벤트 null
 * 5. handleAffinityDelta — delta == 0 이면 아무것도 하지 않음
 * 6. dismissLevelUp / dismissLevelDown — 이벤트 초기화
 */
class AffinityManagerTest {

    private lateinit var characterRepo: CharacterRepository
    private lateinit var chatApi: ChatApi
    private lateinit var manager: AffinityManager

    @Before
    fun setUp() {
        // android.util.Log 정적 메서드를 mock으로 대체 (JVM 테스트용)
        mockkStatic(Log::class)
        every { Log.w(any(), any<String>(), any()) } returns 0
        every { Log.w(any(), any<String>()) } returns 0

        characterRepo = mockk()
        chatApi = mockk()
        manager = AffinityManager(characterRepo, chatApi)

        // syncAffinityToServer는 fire-and-forget — 기본 stub
        coEvery { chatApi.syncAffinity(any()) } returns mockk(relaxed = true)
    }

    // ------------------------------------------------------------------
    // 1. affinityLevel 경계값 (CharacterEntity 순수 로직)
    // ------------------------------------------------------------------

    @Test
    fun `affinityLevel is 1 when score is 0`() {
        assertEquals(1, entity(score = 0).affinityLevel)
    }

    @Test
    fun `affinityLevel is 1 when score is 20`() {
        assertEquals(1, entity(score = 20).affinityLevel)
    }

    @Test
    fun `affinityLevel is 2 when score is 21`() {
        assertEquals(2, entity(score = 21).affinityLevel)
    }

    @Test
    fun `affinityLevel is 2 when score is 40`() {
        assertEquals(2, entity(score = 40).affinityLevel)
    }

    @Test
    fun `affinityLevel is 3 when score is 41`() {
        assertEquals(3, entity(score = 41).affinityLevel)
    }

    @Test
    fun `affinityLevel is 3 when score is 60`() {
        assertEquals(3, entity(score = 60).affinityLevel)
    }

    @Test
    fun `affinityLevel is 4 when score is 61`() {
        assertEquals(4, entity(score = 61).affinityLevel)
    }

    @Test
    fun `affinityLevel is 4 when score is 80`() {
        assertEquals(4, entity(score = 80).affinityLevel)
    }

    @Test
    fun `affinityLevel is 5 when score is 81`() {
        assertEquals(5, entity(score = 81).affinityLevel)
    }

    @Test
    fun `affinityLevel is 5 when score is 100`() {
        assertEquals(5, entity(score = 100).affinityLevel)
    }

    // ------------------------------------------------------------------
    // 2. handleAffinityDelta — 레벨 상승 이벤트
    // ------------------------------------------------------------------

    @Test
    fun `handleAffinityDelta emits levelUpEvent when level increases`() = runTest {
        val charId = 1L
        // before: score=20 → level=1, after: score=21 → level=2
        coEvery { characterRepo.getById(charId) } returnsMany listOf(
            entity(id = charId, score = 20),   // before (first call)
            entity(id = charId, score = 21),   // after (second call)
        )
        coEvery { characterRepo.updateAffinity(charId, 1) } just Runs

        manager.levelUpEvent.test {
            assertNull(awaitItem())             // 초기값 null

            manager.handleAffinityDelta(charId, 1)

            assertEquals(2, awaitItem())        // level=2 이벤트 발행
            cancelAndIgnoreRemainingEvents()
        }
    }

    // ------------------------------------------------------------------
    // 3. handleAffinityDelta — 레벨 하락 이벤트
    // ------------------------------------------------------------------

    @Test
    fun `handleAffinityDelta emits levelDownEvent when level decreases`() = runTest {
        val charId = 2L
        // before: score=21 → level=2, after: score=20 → level=1
        coEvery { characterRepo.getById(charId) } returnsMany listOf(
            entity(id = charId, score = 21),
            entity(id = charId, score = 20),
        )
        coEvery { characterRepo.updateAffinity(charId, -1) } just Runs

        manager.levelDownEvent.test {
            assertNull(awaitItem())

            manager.handleAffinityDelta(charId, -1)

            assertEquals(1, awaitItem())
            cancelAndIgnoreRemainingEvents()
        }
    }

    // ------------------------------------------------------------------
    // 4. handleAffinityDelta — 레벨 변화 없으면 이벤트 없음
    // ------------------------------------------------------------------

    @Test
    fun `handleAffinityDelta does not emit event when level unchanged`() = runTest {
        val charId = 3L
        // before: score=30 → level=2, after: score=35 → level=2
        coEvery { characterRepo.getById(charId) } returnsMany listOf(
            entity(id = charId, score = 30),
            entity(id = charId, score = 35),
        )
        coEvery { characterRepo.updateAffinity(charId, 5) } just Runs

        manager.levelUpEvent.test {
            assertNull(awaitItem())
            manager.handleAffinityDelta(charId, 5)
            // 레벨 변화 없으면 이벤트가 오지 않아야 함
            expectNoEvents()
            cancelAndIgnoreRemainingEvents()
        }
    }

    // ------------------------------------------------------------------
    // 5. handleAffinityDelta — delta == 0 시 early return
    // ------------------------------------------------------------------

    @Test
    fun `handleAffinityDelta does nothing when delta is zero`() = runTest {
        val charId = 4L

        manager.handleAffinityDelta(charId, 0)

        // getById 호출 자체가 없어야 함
        coVerify(exactly = 0) { characterRepo.getById(any()) }
    }

    // ------------------------------------------------------------------
    // 6. dismiss 메서드
    // ------------------------------------------------------------------

    @Test
    fun `dismissLevelUp resets levelUpEvent to null`() = runTest {
        val charId = 5L
        coEvery { characterRepo.getById(charId) } returnsMany listOf(
            entity(id = charId, score = 20),
            entity(id = charId, score = 21),
        )
        coEvery { characterRepo.updateAffinity(charId, 1) } just Runs

        manager.handleAffinityDelta(charId, 1)
        assertEquals(2, manager.levelUpEvent.value)

        manager.dismissLevelUp()
        assertNull(manager.levelUpEvent.value)
    }

    @Test
    fun `dismissLevelDown resets levelDownEvent to null`() = runTest {
        val charId = 6L
        coEvery { characterRepo.getById(charId) } returnsMany listOf(
            entity(id = charId, score = 21),
            entity(id = charId, score = 20),
        )
        coEvery { characterRepo.updateAffinity(charId, -1) } just Runs

        manager.handleAffinityDelta(charId, -1)
        assertEquals(1, manager.levelDownEvent.value)

        manager.dismissLevelDown()
        assertNull(manager.levelDownEvent.value)
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------

    private fun entity(id: Long = 1L, score: Int): CharacterEntity =
        CharacterEntity(
            id = id,
            name = "TestChar",
            mbti = "ENFP",
            speechStyle = "친근",
            relationship = "친구",
            affinityScore = score,
        )
}
