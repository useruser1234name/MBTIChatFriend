package com.example.mbtichatfriend.data.repository

import android.util.Log
import com.example.mbtichatfriend.data.local.MemoryDao
import com.example.mbtichatfriend.data.local.MemoryEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.MemoryExtractRequest
import com.example.mbtichatfriend.data.remote.MemoryItem
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MemoryRepository @Inject constructor(
    private val dao: MemoryDao,
    private val api: ChatApi
) {
    // 실패한 추출 요청을 추적하여 다음 기회에 재시도
    private val pendingExtractions = mutableMapOf<Long, PendingExtraction>()

    private data class PendingExtraction(
        val characterName: String,
        val nickname: String,
        val retryCount: Int = 0
    )

    suspend fun loadMemories(characterId: Long): List<MemoryItem> {
        return dao.getByCharacter(characterId).map {
            MemoryItem(key = it.key, value = it.value)
        }
    }

    fun hasPendingExtraction(characterId: Long): Boolean {
        return pendingExtractions.containsKey(characterId)
    }

    suspend fun extractAndSave(
        characterId: Long,
        characterName: String,
        nickname: String,
        conversationHistory: List<Map<String, String>>
    ) {
        try {
            val response = api.extractMemories(
                MemoryExtractRequest(
                    characterName = characterName,
                    characterId = characterId.toString(),
                    nickname = nickname,
                    conversationHistory = conversationHistory
                )
            )
            if (response.memories.isNotEmpty()) {
                // 기존 기억 삭제 후 새 기억 저장 (최신 상태 유지)
                dao.deleteByCharacter(characterId)
                dao.insertAll(
                    response.memories.map { item ->
                        MemoryEntity(
                            characterId = characterId,
                            key = item.key,
                            value = item.value
                        )
                    }
                )
            }
            // 성공 시 pending 제거
            pendingExtractions.remove(characterId)
        } catch (e: Exception) {
            Log.w("MemoryRepository", "메모리 추출 실패, 재시도 예약: ${e.message}")
            val existing = pendingExtractions[characterId]
            val retryCount = (existing?.retryCount ?: 0) + 1
            if (retryCount <= 3) {
                pendingExtractions[characterId] = PendingExtraction(
                    characterName = characterName,
                    nickname = nickname,
                    retryCount = retryCount
                )
            } else {
                // 3회 실패 시 포기
                Log.w("MemoryRepository", "메모리 추출 3회 실패, 포기: characterId=$characterId")
                pendingExtractions.remove(characterId)
            }
        }
    }

    fun clearPending(characterId: Long) {
        pendingExtractions.remove(characterId)
    }
}
