package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.repository.CharacterRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * AffinityManager — 캐릭터 호감도(affinityLevel) 변화 전담 관리 클래스.
 *
 * 책임:
 * - 호감도 상승/하락 이벤트 StateFlow 보관
 * - handleAffinityDelta: DB 업데이트 + 레벨 변화 감지 → 이벤트 발행
 * - dismiss 메서드로 이벤트 초기화
 *
 * ChatViewModel은 이 클래스를 주입받아 1줄 위임으로 처리한다.
 */
@Singleton
class AffinityManager @Inject constructor(
    private val characterRepo: CharacterRepository,
) {
    private val _levelUpEvent = MutableStateFlow<Int?>(null)
    val levelUpEvent: StateFlow<Int?> = _levelUpEvent.asStateFlow()

    private val _levelDownEvent = MutableStateFlow<Int?>(null)
    val levelDownEvent: StateFlow<Int?> = _levelDownEvent.asStateFlow()

    fun dismissLevelUp() { _levelUpEvent.value = null }
    fun dismissLevelDown() { _levelDownEvent.value = null }

    suspend fun handleAffinityDelta(charId: Long, delta: Int) {
        if (delta == 0) return
        val before = characterRepo.getById(charId)?.affinityLevel ?: 1
        characterRepo.updateAffinity(charId, delta)
        val after = characterRepo.getById(charId)?.affinityLevel ?: 1
        if (after > before) _levelUpEvent.value = after
        else if (after < before) _levelDownEvent.value = after
    }
}
