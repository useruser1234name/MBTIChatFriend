package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.FeedbackDao
import com.example.mbtichatfriend.data.local.FeedbackEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.MessageEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ChatRequest
import com.example.mbtichatfriend.data.remote.FeedbackRequest
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.ReplyPart
import com.example.mbtichatfriend.data.remote.SessionCheckRequest
import com.example.mbtichatfriend.data.remote.SessionCheckResponse
import com.example.mbtichatfriend.data.remote.SseClient
import com.example.mbtichatfriend.data.remote.SseEvent
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

data class ChatResult(
    val replies: List<ReplyPart>,
    val affinityDelta: Int,
    val nightDiaryGenerated: Boolean = false,
    val nextHook: String = "",
    val nextGoal: String = ""
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
    ) {
        dao.insert(
            MessageEntity(
                characterId = characterId,
                text = text,
                isFromUser = isFromUser,
                emotion = emotion,
                sendStatus = sendStatus
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
            ChatResult(
                replies = response.replies,
                affinityDelta = response.affinityDelta,
                nightDiaryGenerated = response.nightDiaryGenerated,
                nextHook = response.nextHook,
                nextGoal = response.nextGoal,
            )
        } catch (e: Exception) {
            ChatResult(
                replies = listOf(
                    ReplyPart(
                        text = "음... 잠깐 생각할게요! 다시 말해줄래요?",
                        emotion = "NEUTRAL",
                        delay = 500
                    )
                ),
                affinityDelta = 0
            )
        }
    }

    suspend fun updateSendStatus(messageId: Long, status: String) {
        dao.updateSendStatus(messageId, status)
    }

    suspend fun clearMessages(characterId: Long) {
        dao.deleteByCharacter(characterId)
    }

    /** 피드백 제출: 로컬 저장 → 서버 동기화 (오프라인 우선) */
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
            if (entity != null) feedbackDao.markSynced(entity.id)
        } catch (_: Exception) {
            // 서버 실패 시 로컬만 저장, 나중에 재시도
        }
    }

    /** 특정 메시지의 로컬 피드백 조회 */
    suspend fun getFeedbackForMessage(messageId: Long): String? {
        return feedbackDao.getByMessageId(messageId)?.feedbackType
    }

    /**
     * Self-Regulation: 세션 사용 시간 및 연속 접속 점검.
     * PSY-B 최은혜 + PM-B 손민준 설계 (4차 회의 합의).
     */
    suspend fun checkSession(req: SessionCheckRequest): SessionCheckResponse =
        api.checkSession(req)

    /** 미동기화 피드백 서버 전송 재시도 */
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
                // 다음 시도에서 재시도
            }
        }
    }
}
