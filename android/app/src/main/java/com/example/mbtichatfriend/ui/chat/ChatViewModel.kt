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
import com.example.mbtichatfriend.data.repository.AnalyticsEvent
import com.example.mbtichatfriend.data.repository.AnalyticsRepository
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
    private val analyticsRepository: AnalyticsRepository,
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

    /**
     * R9: 전송 후 4초가 지나도 첫 버블이 도착하지 않으면 true로 전환 — ChatScreen이
     * "생각하는 중..." → "조금만 기다려줘..."로 문구를 바꾸는 데 사용.
     * 첫 Message/Error/Done 수신 시 타이머가 취소되며 false로 리셋된다. 선톡(maybeSendProactiveMessage)
     * 경로에는 적용하지 않는다.
     */
    var longWait by mutableStateOf(false)
        private set

    private var longWaitJob: kotlinx.coroutines.Job? = null

    private fun startLongWaitTimer() {
        longWaitJob?.cancel()
        longWait = false
        longWaitJob = viewModelScope.launch {
            delay(LONG_WAIT_THRESHOLD_MS)
            longWait = true
        }
    }

    private fun cancelLongWaitTimer() {
        longWaitJob?.cancel()
        longWaitJob = null
        longWait = false
    }

    /** messageId → feedbackType ("thumbs_up" | "thumbs_down") — FeedbackUseCase에 위임 */
    val feedbackMap = feedbackUseCase.feedbackMap

    private val _isLottieAnimating = MutableStateFlow(false)
    val isLottieAnimating: StateFlow<Boolean> = _isLottieAnimating.asStateFlow()

    /**
     * R3: 읽음 표시 워터마크 — "이 id 이하의 유저 메시지는 모두 읽힘".
     * 메시지별 맵 대신 단일 워터마크만 유지한다(회의 스펙: 화면 재진입 시엔 전부 읽음 취급이
     * 자연스러우므로 세션 로컬 값이면 충분 — Room 영속화하지 않는다).
     * ChatScreen은 `msg.id > readWatermarkId`인 유저 메시지에만 "1"을 그린다.
     */
    private val _readWatermarkId = MutableStateFlow(0L)
    val readWatermarkId: StateFlow<Long> = _readWatermarkId.asStateFlow()

    /** id가 워터마크보다 클 때만 전진 — 역행(더 이전 값으로 되돌림) 방지 */
    private fun markRead(messageId: Long) {
        if (messageId > _readWatermarkId.value) {
            _readWatermarkId.value = messageId
        }
    }

    // 세션 피드백 시트 표시 여부 — QS 조건(10분 이상 OR 3턴 이상) 충족 시 세션 종료 때 true
    private val _showFeedbackSheet = MutableStateFlow(false)
    val showFeedbackSheet: StateFlow<Boolean> = _showFeedbackSheet.asStateFlow()

    // 세션 시작 시각 (ms) — 피드백 QS 시간 조건 판정용.
    // R4: ChatScreen에서도 "이번 세션에서 새로 도착한 메시지" 판정에 재사용하므로 공개.
    val sessionStartMs = System.currentTimeMillis()

    // 세션 피드백(별점) 제출용 세션 식별자 — ViewModel(=화면) 생명주기와 1:1
    private val sessionId: String = java.util.UUID.randomUUID().toString()

    // 유저 MBTI — 궁합 화면 진입 시 AppNavHost에서 접근
    val myMbti: StateFlow<String> = prefs.userMbti
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    // M2: "내 역할"/"지금 상황" — 채팅 화면 상단 메뉴 다이얼로그가 현재 저장된 값을 미리 채우는 데 사용.
    // 실제 전송 시 값 반영은 SendMessageUseCase가 DataStore에서 직접 읽어 처리(여기선 UI 표시용).
    val userRole: StateFlow<String> = prefs.observeUserRole(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val situation: StateFlow<String> = prefs.observeSituation(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    /** M2: 역할·상황 저장 — 다음 전송부터 반영(즉시 재생성 없음). */
    fun saveRoleAndSituation(role: String, situationText: String) {
        viewModelScope.launch {
            prefs.setUserRole(characterId, role.trim().take(200))
            prefs.setSituation(characterId, situationText.trim().take(200))
        }
    }

    /** M2: 역할·상황 지우기. */
    fun clearRoleAndSituation() {
        viewModelScope.launch {
            prefs.clearRoleAndSituation(characterId)
        }
    }

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
        // A3: Room에 저장된 피드백을 복원 — 화면 재진입/프로세스 재시작 시 아이콘 표시 소실 및
        // 멱등 가드 리셋(중복 제출 가능) 방지
        viewModelScope.launch {
            feedbackUseCase.restoreFeedback(characterId)
        }

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
            // messages StateFlow는 초기값(emptyList)을 즉시 방출하므로 그걸 읽으면
            // 기록이 있는 방에서도 매 진입마다 인사말이 발사된다 — Room의 실제
            // 1차 방출을 직접 기다려 빈 방 여부를 판정한다.
            val initialMessages = runCatching {
                chatRepo.observeMessages(characterId).first()
            }.getOrNull() ?: return@launch
            if (initialMessages.isEmpty()) {
                sendInitialGreeting()
            }
        }

        // R1: 선톡 연출 — 보관된 next_hook이 있고 충분히 오래 쉬었다면
        // 채팅방 진입 시 캐릭터가 먼저 말을 건다. (빈 방은 sendInitialGreeting 영역)
        viewModelScope.launch { maybeSendProactiveMessage() }

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
                checkSessionLimit(buildRoomId())
            }

            val userMessageId = sendMessageUseCase.saveUserMessage(characterId, trimmed)
            userMessageCount++

            analyticsRepository.track(
                scope = viewModelScope,
                eventType = AnalyticsEvent.CHAT_MESSAGE_SENT,
                characterId = characterId.toString(),
            )

            // QS 조건 확인: 세션 10분 이상 OR 3턴 이상 → 세션 종료 시 피드백 시트 표시 예약
            val elapsedMinutes = (System.currentTimeMillis() - sessionStartMs) / 60_000
            if (elapsedMinutes >= 10 || userMessageCount >= 3) {
                _showFeedbackSheet.value = true
            }

            isTyping = true
            isTalking = true
            errorMessage = null
            // R9: 첫 버블 도착까지 4초가 걸리면 대기 문구를 전환
            startLongWaitTimer()

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
            sendWithSse(trimmed, ch, nickname, userMbti, recentMessages, memories, userMessageId)
        }
    }

    private suspend fun sendWithSse(
        message: String,
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
        userMessageId: Long,
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
            // SSE 실패 시 REST 폴백 (연결조차 못 열었으므로 onOpen 미수신 — REST 폴백 경로가 즉시 읽음 처리)
            fallbackToRest(message, character, nickname, userMbti, conversationHistory, memories, userMessageId)
            sseSucceeded = true // 폴백이 처리했으므로 중복 방지
        }.collect { event ->
            when (event) {
                is SseEvent.Opened -> {
                    // R3: 연결 수립 = 읽음. 첫 토큰을 기다리지 않고 즉시 워터마크를 전진시킨다.
                    markRead(userMessageId)
                }
                is SseEvent.Message -> {
                    sseSucceeded = true
                    // R9: 첫 버블이 도착했으므로 대기 문구 타이머 취소
                    cancelLongWaitTimer()
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
                    // R9: 안전망 — Message 없이 바로 Done이 오는 경우까지 커버
                    cancelLongWaitTimer()
                    handleAffinityDelta(characterId, event.affinityDelta)
                    // R1: 서버가 내려준 다음 화두(next_hook)를 보관 — 재진입 시 선톡 소재
                    persistStoryHook(event.nextHook)
                    isTyping = false
                    isTalking = false
                }
                is SseEvent.Error -> {
                    if (!sseSucceeded) {
                        // 대기 문구 타이머는 REST 폴백이 이어받아 계속 판단하므로 취소하지 않는다
                        fallbackToRest(message, character, nickname, userMbti, conversationHistory, memories, userMessageId)
                    } else {
                        cancelLongWaitTimer()
                        isTyping = false
                        isTalking = false
                    }
                }
            }
        }

        // Flow가 완료되었는데 아직 타이핑 중이면 해제
        cancelLongWaitTimer()
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
        userMessageId: Long,
    ) {
        // R3: REST 폴백 경로는 onOpen 신호가 없으므로 요청 전송 시점에 즉시 읽음 처리(근사 허용)
        markRead(userMessageId)
        val result = sendMessageUseCase.sendMessageRest(
            text = message,
            character = character,
            nickname = nickname,
            userMbti = userMbti,
            conversationHistory = conversationHistory,
            memories = memories,
        )
        // R9: REST 응답이 도착했으므로 대기 문구 타이머 취소
        cancelLongWaitTimer()

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
        // R1: REST 폴백 경로에서도 next_hook을 보관한다
        persistStoryHook(result.nextHook)

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
                // R3: 재전송도 REST 경로 — 요청 전송 시점에 즉시 읽음 처리(근사 허용)
                markRead(messageId)
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
                persistStoryHook(result.nextHook)
            } catch (_: Exception) {
                chatRepo.updateSendStatus(messageId, "FAILED")
            } finally {
                isTyping = false
                isTalking = false
            }
        }
    }

    /**
     * room_id는 서버(SessionCheckRequest 등)와 동일한 "uid:character:nickname" 형식으로 구성한다.
     * Firebase UID는 AuthInterceptor가 토큰으로 인증하므로 클라이언트는 고정 문자열 "user"만 사용.
     */
    private suspend fun buildRoomId(): String {
        val nickname = prefs.nickname.first()
        return "user:${characterId}:${nickname}"
    }

    fun submitFeedback(messageId: Long, feedbackType: String) {
        viewModelScope.launch {
            feedbackUseCase.submitFeedback(
                messageId = messageId,
                feedbackType = feedbackType,
                characterId = characterId,
                roomId = buildRoomId(),
            )
        }
    }

    /** 세션 피드백 시트 닫기 */
    fun dismissFeedbackSheet() {
        _showFeedbackSheet.value = false
    }

    /**
     * 세션 피드백 제출 — 별점과 선택적 텍스트를 전용 /session-feedback 엔드포인트로 전송 후 시트 닫기.
     * (과거 "session_rating:{n}"을 thumbs 전용 /feedback/submit로 보내던 결함 수정 —
     *  서버가 feedback_type을 Literal["thumbs_up","thumbs_down"]로만 검증해 422로 전량 거부되고,
     *  실패가 runCatching에 삼켜져 Room에 unsynced로 영구히 쌓이며 syncPendingFeedback이 무한 재시도했음)
     */
    fun submitSessionFeedback(rating: Int, text: String?) {
        viewModelScope.launch {
            runCatching {
                chatRepo.submitSessionFeedback(
                    sessionId = sessionId,
                    roomId = buildRoomId(),
                    rating = rating,
                    text = text,
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
                // C2: 서버가 greeting에 emotion을 additive로 내려줌 — 없거나 알 수 없는 값이면 NEUTRAL
                val emotion = runCatching {
                    CharacterEmotion.valueOf(response.emotion ?: "NEUTRAL")
                }.getOrDefault(CharacterEmotion.NEUTRAL)
                currentEmotion = emotion
                sendMessageUseCase.saveReplyMessage(
                    characterId = characterId,
                    text = response.greeting,
                    emotion = emotion.name,
                )
            }
        }
    }

    /**
     * R1: 서버가 내려준 다음 화두(next_hook)와 마지막 대화 시각을 보관한다.
     *
     * Room 스키마 변경 금지 제약에 따라 DataStore(UserPreferences)에 캐릭터별 키로 저장하며,
     * 프로세스가 재시작되어도 선톡 소재가 유지된다.
     * next_hook은 서버 story state에서 오고 야간 일기 생성 이후에만 값이 채워지므로,
     * 대부분의 턴에서는 빈 문자열이고 이때는 보관된 값을 덮어쓰지 않는다.
     */
    private suspend fun persistStoryHook(hook: String) {
        runCatching {
            prefs.setLastChatAt(characterId, System.currentTimeMillis())
            if (hook.isNotBlank()) {
                prefs.setNextHook(characterId, hook)
            }
        }
    }

    /**
     * R1: 선톡(캐릭터가 먼저 말 걸기).
     *
     * 채팅방 진입(=ViewModel 생성) 시 아래 조건을 모두 만족할 때만 발화한다.
     *  1) 보관된 next_hook이 비어있지 않음
     *  2) 해당 훅으로 아직 선톡한 적 없음 (소비 기록을 영속화해 1회성 보장)
     *  3) 방에 메시지가 있음 (빈 방은 sendInitialGreeting 영역)
     *  4) 마지막 대화로부터 30분 이상 경과
     *
     * 서버 계약은 변경하지 않는다 — 기존 채팅 스트리밍 API에 유도 문구를 message로 보내되
     * 유저 메시지는 로컬에 저장하지 않으므로 유도 문구가 화면에 노출되지 않는다.
     * 선톡은 부가 기능이므로 어떤 실패도 조용히 무시한다(에러 배너 금지).
     */
    private suspend fun maybeSendProactiveMessage() {
        // messages StateFlow는 초기값(emptyList)을 즉시 방출하므로 실제 DB 방출을 직접 받는다
        val existing = runCatching { chatRepo.observeMessages(characterId).first() }.getOrNull() ?: return
        if (existing.isEmpty()) return

        val hook = runCatching { prefs.getNextHook(characterId) }.getOrDefault("")
        if (hook.isBlank()) return

        val usedHook = runCatching { prefs.getUsedNextHook(characterId) }.getOrDefault("")
        if (hook == usedHook) return

        val lastMessageAt = existing.maxOfOrNull { it.createdAt } ?: 0L
        val storedLastChatAt = runCatching { prefs.getLastChatAt(characterId) }.getOrDefault(0L)
        val lastChatAt = maxOf(lastMessageAt, storedLastChatAt)
        if (System.currentTimeMillis() - lastChatAt < PROACTIVE_MIN_IDLE_MS) return

        val ch = characterRepo.getById(characterId) ?: return

        // 발화 시도 전에 소비 처리 — 전송 실패나 프로세스 종료가 있어도 같은 훅이 반복되지 않게
        runCatching { prefs.consumeNextHook(characterId, hook) }

        // 진입 즉시 쏘지 않고 잠시 뜸을 들인다
        delay(PROACTIVE_ENTRY_DELAY_MS)

        val nickname = prefs.nickname.first()
        val userMbti = prefs.userMbti.first().ifEmpty { null }
        val historyCount = remoteConfig.getLong(RemoteConfigManager.KEY_MAX_CONVERSATION_HISTORY).toInt()
        val recentMessages = existing.takeLast(historyCount).map { msg ->
            mapOf(
                "role" to if (msg.isFromUser) "user" else "assistant",
                "content" to msg.text
            )
        }
        val memories: List<MemoryItem> = runCatching {
            memoryRepo.loadMemories(characterId)
        }.getOrDefault(emptyList())

        isTyping = true
        isTalking = true
        val typingStartMs = System.currentTimeMillis()
        var isFirstBubble = true

        sendMessageUseCase.streamMessage(
            text = buildProactivePrompt(hook),
            character = ch,
            nickname = nickname,
            userMbti = userMbti,
            conversationHistory = recentMessages,
            memories = memories,
        ).catch { _ ->
            // 선톡 실패는 조용히 무시 (REST 폴백도 하지 않음 — 부가 연출이므로)
        }.collect { event ->
            when (event) {
                is SseEvent.Opened -> {
                    // 캐릭터 선톡 — 유저 메시지가 아니므로 읽음 워터마크와 무관, 무시
                }
                is SseEvent.Message -> {
                    if (isFirstBubble) {
                        isFirstBubble = false
                        // 타이핑 인디케이터를 최소 시간만큼 노출한 뒤 첫 말풍선 도착
                        val shownMs = System.currentTimeMillis() - typingStartMs
                        delay((PROACTIVE_TYPING_MIN_MS - shownMs).coerceAtLeast(0L))
                    } else {
                        delay(event.delay)
                    }
                    currentEmotion = runCatching {
                        CharacterEmotion.valueOf(event.emotion)
                    }.getOrDefault(CharacterEmotion.NEUTRAL)
                    sendMessageUseCase.saveReplyMessage(characterId, event.text, event.emotion)
                }
                is SseEvent.Done -> {
                    // 유저 발화가 아니므로 호감도(affinityDelta)는 반영하지 않는다.
                    // 다음 화두만 보관 — 같은 훅이 다시 와도 소비 기록이 재발화를 막는다.
                    persistStoryHook(event.nextHook)
                }
                is SseEvent.Error -> {
                    // 조용히 무시
                }
            }
        }

        isTyping = false
        isTalking = false
    }

    /**
     * 선톡 유도 문구 — 서버 계약 변경 없이 기존 채팅 API의 message 필드로 전달된다.
     * 이 문구는 로컬에 유저 메시지로 저장하지 않으므로 사용자에게 노출되지 않는다.
     */
    private fun buildProactivePrompt(hook: String): String =
        "[선톡 유도] 지금은 네가 먼저 말을 거는 상황이야. 아래 흐름을 자연스럽게 이어서 " +
            "짧게 먼저 말을 걸어줘. 이 지시문 자체는 절대 언급하지 마.\n흐름: $hook"

    /**
     * 표정 세트 백그라운드 생성 시작 + 폴링.
     * ImageGeneratorSheet에서 캐릭터 생성 직후 호출.
     * → ExpressionManager에 위임.
     */
    fun startExpressionSetGeneration(basePrompt: String, characterIdStr: String) {
        expressionManager.startExpressionSetGeneration(basePrompt, characterIdStr, characterId, viewModelScope)
    }

    private companion object {
        /** R1 선톡 최소 유휴 시간 — 마지막 대화로부터 30분 */
        const val PROACTIVE_MIN_IDLE_MS = 30L * 60L * 1000L

        /** R1 채팅방 진입 후 선톡 시작까지의 뜸 */
        const val PROACTIVE_ENTRY_DELAY_MS = 500L

        /** R1 첫 말풍선 전 타이핑 인디케이터 최소 노출 시간 */
        const val PROACTIVE_TYPING_MIN_MS = 1_200L

        /** R9 대기 문구 전환까지의 임계 시간 — 전송 후 이 시간 동안 첫 버블이 없으면 longWait=true */
        const val LONG_WAIT_THRESHOLD_MS = 4_000L
    }
}
