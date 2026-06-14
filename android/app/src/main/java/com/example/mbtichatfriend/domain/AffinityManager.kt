package com.example.mbtichatfriend.domain

import android.util.Log
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.AffinitySyncRequest
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.repository.CharacterRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * AffinityManager — 캐릭터 호감도(affinityLevel) 변화 전담 관리 클래스.
 *
 * 책임:
 * - 호감도 상승/하락 이벤트 StateFlow 보관
 * - handleAffinityDelta: DB 업데이트 + 레벨 변화 감지 → 이벤트 발행 + 서버 동기화
 * - dismiss 메서드로 이벤트 초기화
 * - restoreFromServer: 채팅 시작 시 서버 값으로 복구 (TODO S-7 계약 확정 후 활성화)
 *
 * ChatViewModel은 이 클래스를 주입받아 1줄 위임으로 처리한다.
 */
@Singleton
class AffinityManager @Inject constructor(
    private val characterRepo: CharacterRepository,
    private val chatApi: ChatApi,
    private val prefs: UserPreferences,
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
        val character = characterRepo.getById(charId) ?: return
        val after = character.affinityLevel
        if (after > before) _levelUpEvent.value = after
        else if (after < before) _levelDownEvent.value = after

        // 서버 동기화 — fire-and-forget, 실패해도 로컬 값은 유효
        syncAffinityToServer(charId, character.affinityScore, character.affinityLevel)
    }

    /**
     * 채팅 시작 시 서버 호감도로 로컬 복구 (재설치 복구용).
     * room_id는 내부에서 "{uid}:{charId}" 형식으로 구성한다(서버 소유권 검증과 일치).
     * 실패 무시 (로컬 우선).
     */
    suspend fun restoreAffinityFromServer(charId: Long) {
        val roomId = roomIdFor(charId)
        runCatching {
            val response = chatApi.restoreAffinity(roomId = roomId)
            if (response.isSuccessful) {
                val body = response.body() ?: return
                val character = characterRepo.getById(charId) ?: return
                if (body.score != character.affinityScore) {
                    val delta = body.score - character.affinityScore
                    characterRepo.updateAffinity(charId, delta)
                }
            }
        }.onFailure { e ->
            Log.w(TAG, "restoreAffinityFromServer failed for charId=$charId roomId=$roomId", e)
        }
    }

    private suspend fun syncAffinityToServer(charId: Long, score: Int, level: Int) {
        val roomId = roomIdFor(charId)
        runCatching {
            chatApi.syncAffinity(
                AffinitySyncRequest(
                    roomId = roomId,
                    characterId = charId.toString(),
                    score = score,
                    level = level,
                )
            )
        }.onFailure { e ->
            Log.w(TAG, "syncAffinityToServer failed for charId=$charId", e)
        }
    }

    /**
     * 서버 affinity 엔드포인트의 소유권 검증(room_id.startswith(uid))과 일치하도록
     * 실제 Firebase uid를 접두사로 사용해 유저별 고유 키를 만든다.
     * uid가 없으면(개발 모드 등) charId 기반 폴백.
     */
    private suspend fun roomIdFor(charId: Long): String {
        val uid = prefs.firebaseUid.first()
        return if (uid.isNotEmpty()) "$uid:$charId" else "char:$charId"
    }

    companion object {
        private const val TAG = "AffinityManager"
    }
}
