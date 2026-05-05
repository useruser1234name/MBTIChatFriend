package com.example.mbtichatfriend.ui.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.ContentFilter
import com.example.mbtichatfriend.data.local.NetworkObserver
import com.example.mbtichatfriend.data.local.NotificationHelper
import com.example.mbtichatfriend.data.local.OfflineMessageQueue
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ApiErrorException
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageSetRequest
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
import com.example.mbtichatfriend.data.remote.SessionStartRequest
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.MemoryRepository
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneOffset
import javax.inject.Inject

@HiltViewModel
class ChatViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val chatRepo: ChatRepository,
    private val characterRepo: CharacterRepository,
    private val memoryRepo: MemoryRepository,
    private val prefs: UserPreferences,
    private val networkObserver: NetworkObserver,
    private val notificationHelper: NotificationHelper,
    private val remoteConfig: RemoteConfigManager,
    private val offlineMessageQueue: OfflineMessageQueue,
    private val chatApi: ChatApi,
    private val moshi: Moshi
) : ViewModel() {

    val characterId: Long = savedStateHandle.get<String>("characterId")?.toLongOrNull() ?: 0L

    val character = characterRepo.observeById(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val messages = chatRepo.observeMessages(characterId)
        .map { entities ->
            entities.map { entity ->
                ChatMessage(
                    id = entity.id,
                    text = entity.text,
                    isFromUser = entity.isFromUser,
                    emotion = entity.emotion?.let {
                        try { CharacterEmotion.valueOf(it) } catch (_: Exception) { null }
                    },
                    createdAt = entity.createdAt,
                    sendStatus = entity.sendStatus
                )
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val isOnline = networkObserver.isOnline
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), true)

    var isTyping by mutableStateOf(false)
        private set

    var currentEmotion by mutableStateOf(CharacterEmotion.NEUTRAL)
        private set

    var errorMessage by mutableStateOf<String?>(null)
        private set

    var levelUpEvent by mutableStateOf<Int?>(null)
        private set

    var levelDownEvent by mutableStateOf<Int?>(null)
        private set

    var expressionUrls by mutableStateOf<Map<String, String>?>(null)
        private set

    var isTalking by mutableStateOf(false)
        private set

    /** messageId → feedbackType ("thumbs_up" | "thumbs_down") */
    val feedbackMap = mutableStateMapOf<Long, String>()

    /** 세션 시작 시 복귀 보너스 등 알림 메시지 */
    var sessionMessage by mutableStateOf<String?>(null)
        private set

    fun dismissSessionMessage() {
        sessionMessage = null
    }

    private suspend fun handleAffinityDelta(charId: Long, delta: Int) {
        if (delta == 0) return
        val before = characterRepo.getById(charId)?.affinityLevel ?: 1
        characterRepo.updateAffinity(charId, delta)
        val after = characterRepo.getById(charId)?.affinityLevel ?: 1
        if (after > before) levelUpEvent = after
        else if (after < before) levelDownEvent = after
    }

    private fun toIsoUtc(timestampMs: Long?): String? {
        if (timestampMs == null) return null
        return Instant.ofEpochMilli(timestampMs).atOffset(ZoneOffset.UTC).toString()
    }

    private var expressionSetTaskId: String? = null

    private var userMessageCount = 0

    /** 메시지 전송에 필요한 공통 파라미터를 준비한다 */
    private data class ChatParams(
        val nickname: String,
        val userMbti: String?,
        val history: List<Map<String, String>>,
        val memories: List<MemoryItem>,
    )

    private suspend fun buildChatParams(charId: Long): ChatParams {
        val nickname = prefs.nickname.first()
        val userMbti = prefs.userMbti.first().ifEmpty { null }
        val historyCount = remoteConfig.getLong(RemoteConfigManager.KEY_MAX_CONVERSATION_HISTORY).toInt()
        val recentMessages = messages.value.takeLast(historyCount).map { msg ->
            mapOf(
                "role" to if (msg.isFromUser) "user" else "assistant",
                "content" to msg.text
            )
        }
        val memories: List<MemoryItem> = runCatching {
            memoryRepo.loadMemories(charId)
        }.getOrDefault(emptyList())
        return ChatParams(nickname, userMbti, recentMessages, memories)
    }

    init {
        // 기존 expressionSet 로드 또는 진행 중인 생성 작업 폴링
        viewModelScope.launch {
            val ch = characterRepo.getById(characterId)
            if (ch == null) {
                return@launch
            }
            if (ch.expressionSetReady && ch.expressionSet != null) {
                expressionUrls = parseExpressionSet(ch.expressionSet)
            } else if (ch.avatarId.startsWith("img:")) {
                // 진행 중인 표정 세트 생성 작업이 있는지 확인
                val taskId = waitForExpressionSetTaskId()
                if (taskId != null) {
                    expressionSetTaskId = taskId
                    pollExpressionSetStatus(taskId)
                }
            }
        }

        // 세션 시작: 호감도 감쇠/복귀 보너스 처리
        viewModelScope.launch {
            try {
                val currentCharacter = characterRepo.getById(characterId) ?: return@launch
                val lastChatIso = toIsoUtc(characterRepo.getLastMessageAt(characterId))
                val response = chatApi.startSession(
                    SessionStartRequest(
                        characterId = characterId.toString(),
                        currentAffinityScore = currentCharacter.affinityScore,
                        currentAffinityLevel = currentCharacter.affinityLevel,
                        lastChatIso = lastChatIso
                    )
                )
                val delta = response.adjustedScore - response.originalScore
                if (delta != 0) {
                    handleAffinityDelta(characterId, delta)
                }
                if (response.returnBonus > 0 && response.daysInactive > 0) {
                    sessionMessage = "${response.daysInactive}일 만에 돌아왔네요! 복귀 보너스 +${response.returnBonus} 💕"
                } else if (response.adjustedScore < response.originalScore) {
                    sessionMessage = "오랫동안 연락이 없어서 호감도가 ${response.originalScore - response.adjustedScore} 감소했어요..."
                }
            } catch (_: Exception) {
                // 세션 시작 실패는 치명적이지 않으므로 무시
            }
        }

        // 네트워크 복구 시 대기 중인 메시지 전송
        viewModelScope.launch {
            networkObserver.isOnline
                .distinctUntilChanged()
                .filter { it }
                .collect {
                    offlineMessageQueue.flushPendingMessages { pendingMessage ->
                        try {
                            val ch = characterRepo.getById(pendingMessage.characterId)
                                ?: return@flushPendingMessages OfflineMessageQueue.FlushResult.FAILED
                            val params = buildChatParams(pendingMessage.characterId)

                            val result = chatRepo.sendMessage(
                                message = pendingMessage.text,
                                mbti = ch.mbti,
                                speechStyle = ch.speechStyle,
                                relationship = ch.relationship,
                                nickname = params.nickname,
                                affinityLevel = ch.affinityLevel,
                                conversationHistory = params.history,
                                userMbti = params.userMbti,
                                characterName = ch.name,
                                characterId = pendingMessage.characterId.toString(),
                                personaRaw = ch.personaRaw,
                                personaSummary = ch.personaSummary,
                                dialoguePrompt = ch.dialoguePrompt,
                                visualPrompt = ch.visualPrompt,
                                memories = params.memories
                            )

                            for (reply in result.replies) {
                                chatRepo.saveMessage(
                                    characterId = pendingMessage.characterId,
                                    text = reply.text,
                                    isFromUser = false,
                                    emotion = reply.emotion
                                )
                            }

                            if (result.affinityDelta != 0) {
                                characterRepo.updateAffinity(pendingMessage.characterId, result.affinityDelta)
                            }

                            OfflineMessageQueue.FlushResult.SENT
                        } catch (e: ApiErrorException) {
                            if (e.statusCode in 400..499) {
                                OfflineMessageQueue.FlushResult.FAILED
                            } else {
                                OfflineMessageQueue.FlushResult.RETRY
                            }
                        } catch (_: Exception) {
                            OfflineMessageQueue.FlushResult.RETRY
                        }
                    }

                    // 미동기화 피드백 서버 전송
                    chatRepo.syncPendingFeedback()
                }
        }
    }

    fun dismissLevelUp() {
        levelUpEvent = null
    }

    fun dismissLevelDown() {
        levelDownEvent = null
    }

    // 화면이 보이는지 추적 (ChatScreen에서 설정)
    var isScreenVisible by mutableStateOf(true)

    fun dismissError() {
        errorMessage = null
    }

    fun send(text: String) {
        val trimmed = text.trim()

        val maxLength = remoteConfig.getLong(RemoteConfigManager.KEY_MAX_MESSAGE_LENGTH).toInt()
        val validation = ContentFilter.check(trimmed, maxLength)
        if (!validation.isSafe) {
            errorMessage = validation.reason
            return
        }

        viewModelScope.launch {
            if (!isOnline.value) {
                chatRepo.saveMessage(
                    characterId = characterId,
                    text = trimmed,
                    isFromUser = true,
                    sendStatus = "PENDING"
                )
                return@launch
            }

            val userMessageId = chatRepo.saveMessage(
                characterId = characterId,
                text = trimmed,
                isFromUser = true,
                sendStatus = "PENDING"
            )
            userMessageCount++

            isTyping = true
            isTalking = true
            errorMessage = null

            val ch = characterRepo.getById(characterId)
            if (ch == null) {
                chatRepo.deleteMessage(userMessageId)
                isTyping = false
                isTalking = false
                return@launch
            }
            val params = buildChatParams(characterId)

            // 5번마다 또는 이전 실패 시 장기 기억 추출 (백그라운드)
            val shouldExtract = userMessageCount % 10 == 0 || memoryRepo.hasPendingExtraction(characterId)
            if (shouldExtract) {
                launch {
                    memoryRepo.extractAndSave(
                        characterId = characterId,
                        characterName = ch.name,
                        nickname = params.nickname,
                        conversationHistory = params.history
                    )
                }
            }

            // SSE 스트리밍 시도
            sendWithSse(
                message = trimmed,
                mbti = ch.mbti,
                speechStyle = ch.speechStyle,
                relationship = ch.relationship,
                nickname = params.nickname,
                affinityLevel = ch.affinityLevel,
                conversationHistory = params.history,
                pendingMessageId = userMessageId,
                userMbti = params.userMbti,
                characterName = ch.name,
                charId = characterId.toString(),
                personaRaw = ch.personaRaw,
                personaSummary = ch.personaSummary,
                dialoguePrompt = ch.dialoguePrompt,
                visualPrompt = ch.visualPrompt,
                memories = params.memories
            )
        }
    }

    private suspend fun sendWithSse(
        message: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>>,
        pendingMessageId: Long,
        userMbti: String? = null,
        characterName: String = "",
        charId: String = "",
        personaRaw: String = "",
        personaSummary: String = "",
        dialoguePrompt: String = "",
        visualPrompt: String = "",
        memories: List<MemoryItem> = emptyList()
    ) {
        var sseSucceeded = false

        chatRepo.streamMessage(
            message = message,
            mbti = mbti,
            speechStyle = speechStyle,
            relationship = relationship,
            nickname = nickname,
            affinityLevel = affinityLevel,
            conversationHistory = conversationHistory,
            userMbti = userMbti,
            characterName = characterName,
            characterId = charId,
            personaRaw = personaRaw,
            personaSummary = personaSummary,
            dialoguePrompt = dialoguePrompt,
            visualPrompt = visualPrompt,
            memories = memories
        ).catch { e ->
            // SSE 실패 시 REST 폴백
            fallbackToRest(
                message = message,
                mbti = mbti,
                speechStyle = speechStyle,
                relationship = relationship,
                nickname = nickname,
                affinityLevel = affinityLevel,
                conversationHistory = conversationHistory,
                pendingMessageId = pendingMessageId,
                userMbti = userMbti,
                characterName = characterName,
                charId = charId,
                personaRaw = personaRaw,
                personaSummary = personaSummary,
                dialoguePrompt = dialoguePrompt,
                visualPrompt = visualPrompt,
                memories = memories
            )
            sseSucceeded = true // 폴백이 처리했으므로 중복 방지
        }.collect { event ->
            when (event) {
                is SseEvent.Message -> {
                    if (!sseSucceeded) {
                        chatRepo.updateSendStatus(pendingMessageId, "SENT")
                    }
                    sseSucceeded = true
                    // 서버 딜레이와 별도로, 클라이언트에서도 버블 간 텀 적용
                    delay(event.delay)
                    val emotion = try {
                        CharacterEmotion.valueOf(event.emotion)
                    } catch (_: Exception) {
                        CharacterEmotion.NEUTRAL
                    }
                    currentEmotion = emotion
                    chatRepo.saveMessage(
                        characterId = characterId,
                        text = event.text,
                        isFromUser = false,
                        emotion = event.emotion
                    )
                    // 화면이 안 보일 때 알림
                    if (!isScreenVisible) {
                        val name = character.value?.name ?: "캐릭터"
                        notificationHelper.showChatNotification(name, event.text, characterId)
                    }
                }
                is SseEvent.Done -> {
                    if (!sseSucceeded) {
                        chatRepo.updateSendStatus(pendingMessageId, "SENT")
                        sseSucceeded = true
                    }
                    handleAffinityDelta(characterId, event.affinityDelta)
                    isTyping = false
                    isTalking = false
                }
                is SseEvent.Error -> {
                    if (!sseSucceeded) {
                        if (event.statusCode in 400..499) {
                            chatRepo.deleteMessage(pendingMessageId)
                            errorMessage = event.message
                            isTyping = false
                            isTalking = false
                        } else {
                            fallbackToRest(
                                message = message,
                                mbti = mbti,
                                speechStyle = speechStyle,
                                relationship = relationship,
                                nickname = nickname,
                                affinityLevel = affinityLevel,
                                conversationHistory = conversationHistory,
                                pendingMessageId = pendingMessageId,
                                userMbti = userMbti,
                                characterName = characterName,
                                charId = charId,
                                personaRaw = personaRaw,
                                personaSummary = personaSummary,
                                dialoguePrompt = dialoguePrompt,
                                visualPrompt = visualPrompt,
                                memories = memories
                            )
                        }
                    } else {
                        isTyping = false
                        isTalking = false
                    }
                }
            }
        }

        // Flow가 완료되었는데 아직 타이핑 중이면 해제
        isTyping = false
        isTalking = false
    }

    private suspend fun fallbackToRest(
        message: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>>,
        pendingMessageId: Long,
        userMbti: String? = null,
        characterName: String = "",
        charId: String = "",
        personaRaw: String = "",
        personaSummary: String = "",
        dialoguePrompt: String = "",
        visualPrompt: String = "",
        memories: List<MemoryItem> = emptyList()
    ) {
        try {
            val result = chatRepo.sendMessage(
                message = message,
                mbti = mbti,
                speechStyle = speechStyle,
                relationship = relationship,
                nickname = nickname,
                affinityLevel = affinityLevel,
                conversationHistory = conversationHistory,
                userMbti = userMbti,
                characterName = characterName,
                characterId = charId,
                personaRaw = personaRaw,
                personaSummary = personaSummary,
                dialoguePrompt = dialoguePrompt,
                visualPrompt = visualPrompt,
                memories = memories
            )
            chatRepo.updateSendStatus(pendingMessageId, "SENT")

            for (reply in result.replies) {
                delay(reply.delay)
                val emotion = try {
                    CharacterEmotion.valueOf(reply.emotion)
                } catch (_: Exception) {
                    CharacterEmotion.NEUTRAL
                }
                currentEmotion = emotion
                chatRepo.saveMessage(
                    characterId = characterId,
                    text = reply.text,
                    isFromUser = false,
                    emotion = reply.emotion
                )
            }

            handleAffinityDelta(characterId, result.affinityDelta)
        } catch (e: ApiErrorException) {
            if (e.statusCode in 400..499) {
                chatRepo.deleteMessage(pendingMessageId)
            } else {
                chatRepo.updateSendStatus(pendingMessageId, "FAILED")
            }
            errorMessage = e.message
        } catch (e: Exception) {
            chatRepo.updateSendStatus(pendingMessageId, "FAILED")
            errorMessage = e.message ?: "메시지 전송에 실패했습니다."
        } finally {
            isTyping = false
            isTalking = false
        }
    }

    fun retrySend(messageId: Long) {
        viewModelScope.launch {
            val pending = messages.value.find { it.id == messageId } ?: return@launch
            // PENDING 상태로 되돌리고 retryCount 초기화
            chatRepo.updateSendStatus(messageId, "PENDING")

            if (!isOnline.value) return@launch

            val ch = characterRepo.getById(characterId) ?: return@launch
            val params = buildChatParams(characterId)

            try {
                isTyping = true
                val result = chatRepo.sendMessage(
                    message = pending.text,
                    mbti = ch.mbti,
                    speechStyle = ch.speechStyle,
                    relationship = ch.relationship,
                    nickname = params.nickname,
                    affinityLevel = ch.affinityLevel,
                    conversationHistory = params.history,
                    userMbti = params.userMbti,
                    characterName = ch.name,
                    characterId = characterId.toString(),
                    personaRaw = ch.personaRaw,
                    personaSummary = ch.personaSummary,
                    dialoguePrompt = ch.dialoguePrompt,
                    visualPrompt = ch.visualPrompt,
                    memories = params.memories
                )
                chatRepo.updateSendStatus(messageId, "SENT")

                for (reply in result.replies) {
                    delay(reply.delay)
                    val emotion = try {
                        CharacterEmotion.valueOf(reply.emotion)
                    } catch (_: Exception) {
                        CharacterEmotion.NEUTRAL
                    }
                    currentEmotion = emotion
                    chatRepo.saveMessage(
                        characterId = characterId,
                        text = reply.text,
                        isFromUser = false,
                        emotion = reply.emotion
                    )
                }

                handleAffinityDelta(characterId, result.affinityDelta)
            } catch (e: ApiErrorException) {
                errorMessage = e.message
                chatRepo.updateSendStatus(messageId, "FAILED")
            } catch (e: Exception) {
                errorMessage = e.message ?: "메시지 재전송에 실패했습니다."
                chatRepo.updateSendStatus(messageId, "FAILED")
            } finally {
                isTyping = false
                isTalking = false
            }
        }
    }

    fun submitFeedback(messageId: Long, feedbackType: String) {
        if (feedbackMap.containsKey(messageId)) return
        feedbackMap[messageId] = feedbackType
        viewModelScope.launch {
            chatRepo.submitFeedback(messageId, characterId, feedbackType)
        }
    }

    fun clearChat() {
        viewModelScope.launch {
            chatRepo.clearMessages(characterId)
        }
    }

    /**
     * 표정 세트 백그라운드 생성 시작 + 폴링.
     * ImageGeneratorSheet에서 캐릭터 생성 직후 호출.
     */
    fun startExpressionSetGeneration(basePrompt: String, characterIdStr: String) {
        viewModelScope.launch {
            try {
                val response = chatApi.generateImageSet(
                    ImageSetRequest(
                        basePrompt = basePrompt,
                        characterId = characterIdStr
                    )
                )
                expressionSetTaskId = response.taskId
                pollExpressionSetStatus(response.taskId)
            } catch (e: Exception) {
                // 표정 세트 생성 실패는 치명적이지 않으므로 로그만
                android.util.Log.w("ChatViewModel", "Expression set generation failed", e)
            }
        }
    }

    private suspend fun pollExpressionSetStatus(taskId: String) {
        val maxAttempts = 30 // 최대 30회 (약 5분)
        var attempt = 0
        while (attempt < maxAttempts) {
            delay(10_000) // 10초 간격 폴링
            attempt++
            try {
                val status = chatApi.getImageSetStatus(taskId)
                when (status.status) {
                    "completed" -> {
                        expressionUrls = status.urls
                        val type = Types.newParameterizedType(Map::class.java, String::class.java, String::class.java)
                        val adapter = moshi.adapter<Map<String, String>>(type)
                        val json = adapter.toJson(status.urls)
                        characterRepo.updateExpressionSet(characterId, json)
                        prefs.clearExpressionSetTaskId(characterId)
                        return
                    }
                    "failed" -> {
                        prefs.clearExpressionSetTaskId(characterId)
                        return
                    }
                    // "processing" → 계속 폴링
                }
            } catch (e: Exception) {
                android.util.Log.w("ChatViewModel", "Expression poll error (attempt $attempt)", e)
                if (attempt >= maxAttempts) break
            }
        }
        // 최대 시도 초과 시 정리 — taskId 보존하여 다음 세션에서 재시도 가능
        android.util.Log.w("ChatViewModel", "Expression set polling timed out after $maxAttempts attempts")
    }

    private suspend fun waitForExpressionSetTaskId(): String? {
        repeat(8) {
            val taskId = prefs.getExpressionSetTaskId(characterId)
            if (taskId != null) {
                return taskId
            }
            delay(500)
        }
        return null
    }

    private fun parseExpressionSet(json: String): Map<String, String>? {
        return try {
            val type = Types.newParameterizedType(Map::class.java, String::class.java, String::class.java)
            val adapter = moshi.adapter<Map<String, String>>(type)
            adapter.fromJson(json)
        } catch (_: Exception) {
            null
        }
    }
}
