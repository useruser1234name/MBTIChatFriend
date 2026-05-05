package com.example.mbtichatfriend.ui.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.ContentFilter
import com.example.mbtichatfriend.data.local.NetworkObserver
import com.example.mbtichatfriend.data.local.NotificationHelper
import com.example.mbtichatfriend.data.local.OfflineMessageQueue
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
import com.example.mbtichatfriend.data.remote.SessionCheckRequest
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.MemoryRepository
import com.example.mbtichatfriend.domain.AffinityManager
import com.example.mbtichatfriend.domain.ExpressionManager
import com.example.mbtichatfriend.domain.FeedbackUseCase
import com.example.mbtichatfriend.domain.SendMessageUseCase
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ChatViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val chatRepo: ChatRepository,
    private val sendMessageUseCase: SendMessageUseCase,
    private val characterRepo: CharacterRepository,
    private val memoryRepo: MemoryRepository,
    private val prefs: UserPreferences,
    private val networkObserver: NetworkObserver,
    private val notificationHelper: NotificationHelper,
    private val remoteConfig: RemoteConfigManager,
    private val offlineMessageQueue: OfflineMessageQueue,
    private val expressionManager: ExpressionManager,
    private val affinityManager: AffinityManager,
    private val feedbackUseCase: FeedbackUseCase,
    private val chatApi: ChatApi,
) : ViewModel() {

    val characterId: Long = savedStateHandle.get<String>("characterId")?.toLongOrNull() ?: 0L

    private val character = characterRepo.observeById(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private val messages = chatRepo.observeMessages(characterId)
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

    private val isOnline = networkObserver.isOnline
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

    val expressionUrls: Map<String, String>?
        get() = expressionManager.expressionUrls.value

    var isTalking by mutableStateOf(false)
        private set

    /** messageId → feedbackType ("thumbs_up" | "thumbs_down") — FeedbackUseCase에 위임 */
    val feedbackMap = feedbackUseCase.feedbackMap

    private val _isLottieAnimating = MutableStateFlow(false)
    val isLottieAnimating: StateFlow<Boolean> = _isLottieAnimating.asStateFlow()

    // 세션 피드백 시트 표시 여부 — QS 조건(10분 이상 OR 3턴 이상) 충족 시 세션 종료 때 true
    private val _showFeedbackSheet = MutableStateFlow(false)
    val showFeedbackSheet: StateFlow<Boolean> = _showFeedbackSheet.asStateFlow()

    // 세션 시작 시각 (ms) — 피드백 QS 시간 조건 판정용
    private val sessionStartMs = System.currentTimeMillis()

    // 유저 MBTI — 궁합 화면 진입 시 AppNavHost에서 접근
    val myMbti: StateFlow<String> = prefs.userMbti
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    // MVI 통합 UiState — 9차 스프린트 (1단계: 추가만, 기존 StateFlow 유지)
    private val _uiState = MutableStateFlow<ChatUiState>(ChatUiState.Loading)
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    /**
     * messages, character, isTyping, isLottieAnimating 등이 변경될 때
     * _uiState를 ChatUiState.Success로 동기화.
     * 기존 개별 StateFlow/mutableStateOf는 ChatScreen 점진적 마이그레이션 완료 전까지 유지.
     */
    private fun syncUiState() {
        val currentMessages = messages.value
        val currentCharacter = character.value
        _uiState.value = ChatUiState.Success(
            messages = currentMessages,
            character = currentCharacter,
            isStreaming = isTyping,
            isLottieAnimating = isLottieAnimating.value,
            sessionWarning = sessionWarnMessage,
            affinityLevel = currentCharacter?.affinityLevel ?: 1,
            error = errorMessage,
            isOnline = isOnline.value,
        )
    }

    /**
     * Self-Regulation: 세션 경고 메시지.
     * - null: 경고 없음
     * - non-null: 사용 시간 초과 또는 7일 연속 접속 유도 메시지
     * UI 팀에서 이 값을 관찰해 인앱 배너/다이얼로그로 표시.
     * PSY-B 최은혜 + PM-B 손민준 설계 (4차 회의 합의).
     */
    var sessionWarnMessage by mutableStateOf<String?>(null)
        private set

    fun dismissSessionWarn() {
        sessionWarnMessage = null
    }

    private suspend fun handleAffinityDelta(charId: Long, delta: Int) =
        affinityManager.handleAffinityDelta(charId, delta)

    /**
     * Self-Regulation: 서버에 세션 사용 시간 및 연속 접속 점검 요청.
     * - 90분(미성년자 60분) 초과 시 sessionWarnMessage 설정
     * - 7일 연속 접속 시 현실 관계 유도 메시지 설정 (nudge_message 우선)
     * - FOMO 기반 알림 전면 금지: 이 함수는 푸시를 발송하지 않음
     * PSY-B 최은혜 + PM-B 손민준 설계 (4차 회의 합의).
     */
    private suspend fun checkSessionLimit(roomId: String) {
        val ch = characterRepo.getById(characterId) ?: return
        try {
            val response = chatRepo.checkSession(
                SessionCheckRequest(roomId = roomId)
            )
            val warn = buildString {
                if (response.shouldShowRealityNudge && response.nudgeMessage.isNotBlank()) {
                    append(response.nudgeMessage)
                } else if (response.shouldWarn && response.message.isNotBlank()) {
                    append(response.message)
                }
            }.ifBlank { null }
            sessionWarnMessage = warn
        } catch (_: Exception) {
            // 세션 점검 실패 시 사용자 경험을 방해하지 않고 조용히 무시
        }
    }

    private var userMessageCount = 0

    init {
        // 기존 expressionSet 로드 또는 진행 중인 생성 작업 폴링 → ExpressionManager에 위임
        expressionManager.loadExistingExpressionSet(characterId, viewModelScope)

        // AffinityManager StateFlow → Compose mutableState 동기화
        viewModelScope.launch {
            affinityManager.levelUpEvent.collect { levelUpEvent = it }
        }
        viewModelScope.launch {
            affinityManager.levelDownEvent.collect { levelDownEvent = it }
        }

        // 레벨업 이벤트 발생 시 Lottie 애니메이션 트리거
        viewModelScope.launch {
            affinityManager.levelUpEvent.collect { level ->
                if (level != null) {
                    _isLottieAnimating.value = true
                    delay(2000) // 애니메이션 재생 시간
                    _isLottieAnimating.value = false
                    affinityManager.dismissLevelUp()
                }
            }
        }

        // messages / character / isOnline → uiState 동기화
        viewModelScope.launch { messages.collect { syncUiState() } }
        viewModelScope.launch { character.collect { syncUiState() } }
        viewModelScope.launch { isOnline.collect { syncUiState() } }
        viewModelScope.launch { _isLottieAnimating.collect { syncUiState() } }

        // 신규 채팅방 진입 시 온보딩 첫 인사 (메시지 목록이 비어있을 때만, 중복 방지)
        viewModelScope.launch {
            // messages StateFlow가 초기값(emptyList)을 방출할 때까지 대기
            val initialMessages = messages.first()
            if (initialMessages.isEmpty()) {
                sendInitialGreeting()
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
                            val ch = characterRepo.getById(pendingMessage.characterId) ?: return@flushPendingMessages false
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
                                memoryRepo.loadMemories(pendingMessage.characterId)
                            }.getOrDefault(emptyList())

                            val result = sendMessageUseCase.sendMessageRest(
                                text = pendingMessage.text,
                                character = ch,
                                nickname = nickname,
                                userMbti = userMbti,
                                conversationHistory = recentMessages,
                                memories = memories,
                            )

                            for (reply in result.replies) {
                                sendMessageUseCase.saveReplyMessage(
                                    characterId = pendingMessage.characterId,
                                    text = reply.text,
                                    emotion = reply.emotion,
                                )
                            }

                            if (result.affinityDelta != 0) {
                                characterRepo.updateAffinity(pendingMessage.characterId, result.affinityDelta)
                            }

                            true
                        } catch (_: Exception) {
                            false
                        }
                    }
                }
        }
    }

    fun dismissLevelUp() = affinityManager.dismissLevelUp()

    fun dismissLevelDown() = affinityManager.dismissLevelDown()

    // 화면이 보이는지 추적 (ChatScreen에서 설정)
    var isScreenVisible by mutableStateOf(true)

    fun dismissError() {
        errorMessage = null
    }

    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return

        val maxLength = remoteConfig.getLong(RemoteConfigManager.KEY_MAX_MESSAGE_LENGTH).toInt()
        if (trimmed.length > maxLength) {
            errorMessage = "메시지는 ${maxLength}자 이내로 입력해주세요!"
            return
        }

        val contentFilterEnabled = remoteConfig.getBoolean(RemoteConfigManager.KEY_CONTENT_FILTER_ENABLED)
        if (contentFilterEnabled) {
            val filterResult = ContentFilter.check(trimmed)
            if (!filterResult.isSafe) {
                errorMessage = filterResult.reason
                return
            }
        }

        viewModelScope.launch {
            if (!isOnline.value) {
                sendMessageUseCase.savePendingMessage(characterId, trimmed)
                return@launch
            }

            // Self-Regulation: 메시지 전송 직전 세션 사용 시간 점검
            // room_id는 "uid:character:nickname" 형식으로 서버와 동일하게 구성
            val ch0 = characterRepo.getById(characterId)
            if (ch0 != null) {
                val nickname0 = prefs.nickname.first()
                val uid0 = "user" // Firebase UID는 AuthInterceptor에서 토큰으로 인증됨
                val roomId0 = "${uid0}:${characterId}:${nickname0}"
                checkSessionLimit(roomId0)
            }

            sendMessageUseCase.saveUserMessage(characterId, trimmed)
            userMessageCount++

            // QS 조건 확인: 세션 10분 이상 OR 3턴 이상 → 세션 종료 시 피드백 시트 표시 예약
            val elapsedMinutes = (System.currentTimeMillis() - sessionStartMs) / 60_000
            if (elapsedMinutes >= 10 || userMessageCount >= 3) {
                _showFeedbackSheet.value = true
            }

            isTyping = true
            isTalking = true
            errorMessage = null

            val ch = characterRepo.getById(characterId) ?: return@launch
            val nickname = prefs.nickname.first()
            val userMbti = prefs.userMbti.first().ifEmpty { null }

            val historyCount = remoteConfig.getLong(RemoteConfigManager.KEY_MAX_CONVERSATION_HISTORY).toInt()
            val recentMessages = messages.value.takeLast(historyCount).map { msg ->
                mapOf(
                    "role" to if (msg.isFromUser) "user" else "assistant",
                    "content" to msg.text
                )
            }

            // 5번마다 또는 이전 실패 시 장기 기억 추출 (백그라운드)
            val shouldExtract = userMessageCount % 5 == 0 || memoryRepo.hasPendingExtraction(characterId)
            if (shouldExtract) {
                launch {
                    memoryRepo.extractAndSave(
                        characterId = characterId,
                        characterName = ch.name,
                        nickname = nickname,
                        conversationHistory = recentMessages
                    )
                }
            }

            // 현재 저장된 기억 로드
            val memories: List<MemoryItem> = runCatching {
                memoryRepo.loadMemories(characterId)
            }.getOrDefault(emptyList())

            // SSE 스트리밍 시도
            sendWithSse(trimmed, ch, nickname, userMbti, recentMessages, memories)
        }
    }

    private suspend fun sendWithSse(
        message: String,
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
    ) {
        var sseSucceeded = false

        sendMessageUseCase.streamMessage(
            text = message,
            character = character,
            nickname = nickname,
            userMbti = userMbti,
            conversationHistory = conversationHistory,
            memories = memories,
        ).catch { _ ->
            // SSE 실패 시 REST 폴백
            fallbackToRest(message, character, nickname, userMbti, conversationHistory, memories)
            sseSucceeded = true // 폴백이 처리했으므로 중복 방지
        }.collect { event ->
            when (event) {
                is SseEvent.Message -> {
                    sseSucceeded = true
                    // 서버 딜레이와 별도로, 클라이언트에서도 버블 간 텀 적용
                    delay(event.delay)
                    val emotion = try {
                        CharacterEmotion.valueOf(event.emotion)
                    } catch (_: Exception) {
                        CharacterEmotion.NEUTRAL
                    }
                    currentEmotion = emotion
                    sendMessageUseCase.saveReplyMessage(characterId, event.text, event.emotion)
                    // 화면이 안 보일 때 알림
                    if (!isScreenVisible) {
                        notificationHelper.showChatNotification(character.name, event.text, characterId)
                    }
                }
                is SseEvent.Done -> {
                    handleAffinityDelta(characterId, event.affinityDelta)
                    isTyping = false
                    isTalking = false
                }
                is SseEvent.Error -> {
                    if (!sseSucceeded) {
                        fallbackToRest(message, character, nickname, userMbti, conversationHistory, memories)
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
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
    ) {
        val result = sendMessageUseCase.sendMessageRest(
            text = message,
            character = character,
            nickname = nickname,
            userMbti = userMbti,
            conversationHistory = conversationHistory,
            memories = memories,
        )

        for (reply in result.replies) {
            delay(reply.delay)
            val emotion = try {
                CharacterEmotion.valueOf(reply.emotion)
            } catch (_: Exception) {
                CharacterEmotion.NEUTRAL
            }
            currentEmotion = emotion
            sendMessageUseCase.saveReplyMessage(characterId, reply.text, reply.emotion)
        }

        handleAffinityDelta(characterId, result.affinityDelta)

        isTyping = false
        isTalking = false
    }

    fun retrySend(messageId: Long) {
        viewModelScope.launch {
            val pending = messages.value.find { it.id == messageId } ?: return@launch
            // PENDING 상태로 되돌리고 retryCount 초기화
            chatRepo.updateSendStatus(messageId, "PENDING")

            if (!isOnline.value) return@launch

            val ch = characterRepo.getById(characterId) ?: return@launch
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
                memoryRepo.loadMemories(characterId)
            }.getOrDefault(emptyList())

            try {
                isTyping = true
                val result = sendMessageUseCase.sendMessageRest(
                    text = pending.text,
                    character = ch,
                    nickname = nickname,
                    userMbti = userMbti,
                    conversationHistory = recentMessages,
                    memories = memories,
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
                    sendMessageUseCase.saveReplyMessage(characterId, reply.text, reply.emotion)
                }

                handleAffinityDelta(characterId, result.affinityDelta)
            } catch (_: Exception) {
                chatRepo.updateSendStatus(messageId, "FAILED")
            } finally {
                isTyping = false
                isTalking = false
            }
        }
    }

    fun submitFeedback(messageId: Long, feedbackType: String) {
        viewModelScope.launch {
            feedbackUseCase.submitFeedback(
                messageId = messageId,
                feedbackType = feedbackType,
                characterId = characterId,
            )
        }
    }

    /** 세션 피드백 시트 닫기 */
    fun dismissFeedbackSheet() {
        _showFeedbackSheet.value = false
    }

    /**
     * 세션 피드백 제출 — 별점과 선택적 텍스트를 서버로 전송 후 시트 닫기.
     * feedback_type 은 "session_rating:{rating}" 형식, detail 에 텍스트를 담는다.
     */
    fun submitSessionFeedback(rating: Int, text: String?) {
        viewModelScope.launch {
            runCatching {
                feedbackUseCase.submitFeedback(
                    messageId = -1L, // 세션 전체 피드백이므로 메시지 ID 없음
                    feedbackType = "session_rating:$rating",
                    characterId = characterId,
                )
            }
            dismissFeedbackSheet()
        }
    }

    fun clearChat() {
        viewModelScope.launch {
            chatRepo.clearMessages(characterId)
        }
    }

    /**
     * 온보딩 첫 인사 — 신규 채팅방 진입 시 1회만 호출.
     * 서버에서 캐릭터 MBTI에 맞는 첫 인사를 받아 캐릭터 메시지로 저장.
     * 실패 시 사용자 경험을 방해하지 않고 조용히 무시.
     */
    private suspend fun sendInitialGreeting() {
        val ch = characterRepo.getById(characterId) ?: return
        runCatching {
            val response = chatApi.sendGreeting(
                mapOf("character_mbti" to ch.mbti, "character_name" to ch.name)
            )
            if (response.greeting.isNotBlank()) {
                sendMessageUseCase.saveReplyMessage(
                    characterId = characterId,
                    text = response.greeting,
                    emotion = "NEUTRAL",
                )
            }
        }
    }

    /**
     * 표정 세트 백그라운드 생성 시작 + 폴링.
     * ImageGeneratorSheet에서 캐릭터 생성 직후 호출.
     * → ExpressionManager에 위임.
     */
    fun startExpressionSetGeneration(basePrompt: String, characterIdStr: String) {
        expressionManager.startExpressionSetGeneration(basePrompt, characterIdStr, characterId, viewModelScope)
    }
}
