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
import com.example.mbtichatfriend.data.remote.SessionFeedbackRequest
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
    suspend fun submitFeedback(
        messageId: Long,
        characterId: Long,
        feedbackType: String,
        roomId: String = "",
    ) {
        feedbackDao.insert(
            FeedbackEntity(
                messageId = messageId,
                characterId = characterId,
                feedbackType = feedbackType,
                roomId = roomId,
            )
        )
        try {
            val response = api.submitFeedback(
                FeedbackRequest(
                    roomId = roomId,
                    characterId = characterId.toString(),
                    messageId = messageId.toString(),
                    feedbackType = feedbackType,
                )
            )
            if (response.isSuccessful || response.code() in 400..499) {
                // 성공, 또는 4xx(검증 실패 등 영구적 거부) → 재시도 큐에서 제외.
                // 5xx/네트워크 예외만 재시도 대상으로 남긴다.
                val entity = feedbackDao.getByMessageId(messageId)
                if (entity != null) feedbackDao.markSynced(entity.id)
            }
        } catch (_: Exception) {
            // 네트워크 예외(IOException 등) — 로컬만 저장, 나중에 재시도
        }
    }

    /** 특정 메시지의 로컬 피드백 조회 */
    suspend fun getFeedbackForMessage(messageId: Long): String? {
        return feedbackDao.getByMessageId(messageId)?.feedbackType
    }

    /**
     * A3: 채팅방(캐릭터) 단위로 저장된 피드백을 messageId → feedbackType 맵으로 일괄 조회.
     * 화면 재진입/프로세스 재시작 시 FeedbackUseCase.feedbackMap을 복원하는 용도.
     */
    suspend fun getFeedbackForCharacter(characterId: Long): Map<Long, String> {
        return feedbackDao.getByCharacterId(characterId).associate { it.messageId to it.feedbackType }
    }

    /**
     * Self-Regulation: 세션 사용 시간 및 연속 접속 점검.
     * PSY-B 최은혜 + PM-B 손민준 설계 (4차 회의 합의).
     */
    suspend fun checkSession(req: SessionCheckRequest): SessionCheckResponse =
        api.checkSession(req)

    /**
     * 세션 종료 시 별점 + 텍스트 피드백 제출. 전용 /session-feedback 엔드포인트로 전송한다.
     * (구 방식: "session_rating:{n}"을 /feedback/submit thumbs 전용 엔드포인트로 보내던 결함 수정 —
     * 서버가 Literal["thumbs_up","thumbs_down"]만 허용해 422로 전량 거부되고 있었음)
     */
    suspend fun submitSessionFeedback(sessionId: String, roomId: String, rating: Int, text: String?) {
        api.submitSessionFeedback(
            SessionFeedbackRequest(
                sessionId = sessionId,
                roomId = roomId,
                rating = rating,
                text = text,
            )
        )
    }

    /** 미동기화 피드백 서버 전송 재시도 */
    suspend fun syncPendingFeedback() {
        val unsynced = feedbackDao.getUnsynced()
        for (fb in unsynced) {
            try {
                val response = api.submitFeedback(
                    FeedbackRequest(
                        roomId = fb.roomId,
                        characterId = fb.characterId.toString(),
                        messageId = fb.messageId.toString(),
                        feedbackType = fb.feedbackType,
                    )
                )
                if (response.isSuccessful || response.code() in 400..499) {
                    // 성공, 또는 4xx 영구 거부 → 무한 재시도 루프 방지 위해 재시도 큐에서 제외
                    feedbackDao.markSynced(fb.id)
                }
                // 5xx: 아무 것도 하지 않음 → 다음 sync에서 재시도
            } catch (_: Exception) {
                // 네트워크 예외 — 다음 시도에서 재시도
            }
        }
    }
}
