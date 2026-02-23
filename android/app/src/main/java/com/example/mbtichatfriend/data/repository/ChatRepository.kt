package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.MessageEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ChatRequest
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.ReplyPart
import com.example.mbtichatfriend.data.remote.SseClient
import com.example.mbtichatfriend.data.remote.SseEvent
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

data class ChatResult(
    val replies: List<ReplyPart>,
    val affinityDelta: Int
)

@Singleton
class ChatRepository @Inject constructor(
    private val dao: MessageDao,
    private val api: ChatApi,
    private val sseClient: SseClient
) {
    fun observeMessages(characterId: Long): Flow<List<MessageEntity>> =
        dao.observeByCharacter(characterId)

    suspend fun saveMessage(
        characterId: Long,
        text: String,
        isFromUser: Boolean,
        emotion: String? = null
    ) {
        dao.insert(
            MessageEntity(
                characterId = characterId,
                text = text,
                isFromUser = isFromUser,
                emotion = emotion
            )
        )
    }

    /**
     * SSE 스트리밍으로 메시지 수신
     * 각 메시지 파트가 실시간으로 Flow를 통해 전달됨
     */
    fun streamMessage(
        message: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>> = emptyList(),
        userMbti: String? = null,
        characterName: String = "",
        characterId: String = "",
        memories: List<MemoryItem> = emptyList()
    ): Flow<SseEvent> {
        return sseClient.streamChat(
            ChatRequest(
                message = message,
                mbti = mbti,
                speechStyle = speechStyle,
                relationship = relationship,
                nickname = nickname,
                affinityLevel = affinityLevel,
                conversationHistory = conversationHistory,
                userMbti = userMbti,
                characterName = characterName,
                characterId = characterId,
                memories = memories
            )
        )
    }

    /**
     * REST 방식 (폴백용)
     */
    suspend fun sendMessage(
        message: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>> = emptyList(),
        userMbti: String? = null,
        characterName: String = "",
        characterId: String = "",
        memories: List<MemoryItem> = emptyList()
    ): ChatResult {
        return try {
            val response = api.chat(
                ChatRequest(
                    message = message,
                    mbti = mbti,
                    speechStyle = speechStyle,
                    relationship = relationship,
                    nickname = nickname,
                    affinityLevel = affinityLevel,
                    conversationHistory = conversationHistory,
                    userMbti = userMbti,
                    characterName = characterName,
                    characterId = characterId,
                    memories = memories
                )
            )
            ChatResult(replies = response.replies, affinityDelta = response.affinityDelta)
        } catch (e: Exception) {
            ChatResult(
                replies = listOf(
                    ReplyPart(
                        text = "음... 잠깐 생각할게요! 다시 말해줄래요? \uD83D\uDE4F",
                        emotion = "NEUTRAL",
                        delay = 500
                    )
                ),
                affinityDelta = 0
            )
        }
    }

    suspend fun clearMessages(characterId: Long) {
        dao.deleteByCharacter(characterId)
    }
}
