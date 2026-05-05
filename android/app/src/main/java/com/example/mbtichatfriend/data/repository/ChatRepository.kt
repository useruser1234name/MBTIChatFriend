package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.FeedbackDao
import com.example.mbtichatfriend.data.local.FeedbackEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.MessageEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ChatRequest
import com.example.mbtichatfriend.data.remote.FeedbackRequest
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.SseClient
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.remote.toApiErrorException
import kotlinx.coroutines.flow.Flow
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

data class ChatResult(
    val replies: List<com.example.mbtichatfriend.data.remote.ReplyPart>,
    val affinityDelta: Int
)

@Singleton
class ChatRepository @Inject constructor(
    private val dao: MessageDao,
    private val feedbackDao: FeedbackDao,
    private val api: ChatApi,
    private val sseClient: SseClient
) {
    fun observeMessages(characterId: Long): Flow<List<MessageEntity>> =
        dao.observeByCharacter(characterId)

    suspend fun saveMessage(
        characterId: Long,
        text: String,
        isFromUser: Boolean,
        emotion: String? = null,
        sendStatus: String = "SENT"
    ): Long {
        return dao.insert(
            MessageEntity(
                characterId = characterId,
                text = text,
                isFromUser = isFromUser,
                emotion = emotion,
                sendStatus = sendStatus
            )
        )
    }

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
        personaRaw: String = "",
        personaSummary: String = "",
        dialoguePrompt: String = "",
        visualPrompt: String = "",
        memories: List<MemoryItem> = emptyList(),
        roomId: String = "",
        endOfSession: Boolean = false,
        clientLocalHour: Int? = null,
        mood: String? = null
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
                personaRaw = personaRaw,
                personaSummary = personaSummary,
                dialoguePrompt = dialoguePrompt,
                visualPrompt = visualPrompt,
                memories = memories,
                roomId = roomId,
                endOfSession = endOfSession,
                clientLocalHour = clientLocalHour,
                mood = mood
            )
        )
    }

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
        personaRaw: String = "",
        personaSummary: String = "",
        dialoguePrompt: String = "",
        visualPrompt: String = "",
        memories: List<MemoryItem> = emptyList(),
        roomId: String = "",
        endOfSession: Boolean = false,
        clientLocalHour: Int? = null,
        mood: String? = null
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
                    personaRaw = personaRaw,
                    personaSummary = personaSummary,
                    dialoguePrompt = dialoguePrompt,
                    visualPrompt = visualPrompt,
                    memories = memories,
                    roomId = roomId,
                    endOfSession = endOfSession,
                    clientLocalHour = clientLocalHour,
                    mood = mood
                )
            )
            ChatResult(replies = response.replies, affinityDelta = response.affinityDelta)
        } catch (error: HttpException) {
            throw toApiErrorException(error, "메시지 전송에 실패했습니다.")
        }
    }

    suspend fun updateSendStatus(messageId: Long, status: String) {
        dao.updateSendStatus(messageId, status)
    }

    suspend fun deleteMessage(messageId: Long) {
        dao.deleteById(messageId)
    }

    suspend fun clearMessages(characterId: Long) {
        dao.deleteByCharacter(characterId)
    }

    suspend fun submitFeedback(messageId: Long, characterId: Long, feedbackType: String) {
        feedbackDao.insert(
            FeedbackEntity(
                messageId = messageId,
                characterId = characterId,
                feedbackType = feedbackType,
            )
        )
        try {
            api.submitFeedback(
                FeedbackRequest(
                    characterId = characterId.toString(),
                    messageId = messageId.toString(),
                    feedbackType = feedbackType,
                )
            )
            val entity = feedbackDao.getByMessageId(messageId)
            if (entity != null) {
                feedbackDao.markSynced(entity.id)
            }
        } catch (_: Exception) {
        }
    }

    suspend fun getFeedbackForMessage(messageId: Long): String? {
        return feedbackDao.getByMessageId(messageId)?.feedbackType
    }

    suspend fun syncPendingFeedback() {
        val unsynced = feedbackDao.getUnsynced()
        for (fb in unsynced) {
            try {
                api.submitFeedback(
                    FeedbackRequest(
                        characterId = fb.characterId.toString(),
                        messageId = fb.messageId.toString(),
                        feedbackType = fb.feedbackType,
                    )
                )
                feedbackDao.markSynced(fb.id)
            } catch (_: Exception) {
            }
        }
    }
}
