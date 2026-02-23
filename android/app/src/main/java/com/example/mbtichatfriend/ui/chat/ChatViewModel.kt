package com.example.mbtichatfriend.ui.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.ContentFilter
import com.example.mbtichatfriend.data.local.NetworkObserver
import com.example.mbtichatfriend.data.local.NotificationHelper
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.MemoryRepository
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
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
    private val remoteConfig: RemoteConfigManager
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
                    createdAt = entity.createdAt
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

    private var userMessageCount = 0

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
            chatRepo.saveMessage(characterId = characterId, text = trimmed, isFromUser = true)
            userMessageCount++

            if (!isOnline.value) {
                errorMessage = "네트워크에 연결되어 있지 않아요. 연결 후 다시 시도해주세요!"
                return@launch
            }

            isTyping = true
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
            sendWithSse(trimmed, ch.mbti, ch.speechStyle, ch.relationship, nickname, ch.affinityLevel, recentMessages, userMbti, ch.name, characterId.toString(), memories)
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
        userMbti: String? = null,
        characterName: String = "",
        charId: String = "",
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
            memories = memories
        ).catch { e ->
            // SSE 실패 시 REST 폴백
            fallbackToRest(message, mbti, speechStyle, relationship, nickname, affinityLevel, conversationHistory, userMbti, characterName, charId, memories)
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
                    if (event.affinityDelta != 0) {
                        val before = characterRepo.getById(characterId)?.affinityLevel ?: 1
                        characterRepo.updateAffinity(characterId, event.affinityDelta)
                        val after = characterRepo.getById(characterId)?.affinityLevel ?: 1
                        if (after > before) {
                            levelUpEvent = after
                        } else if (after < before) {
                            levelDownEvent = after
                        }
                    }
                    isTyping = false
                }
                is SseEvent.Error -> {
                    if (!sseSucceeded) {
                        fallbackToRest(message, mbti, speechStyle, relationship, nickname, affinityLevel, conversationHistory, userMbti, characterName, charId, memories)
                    } else {
                        isTyping = false
                    }
                }
            }
        }

        // Flow가 완료되었는데 아직 타이핑 중이면 해제
        isTyping = false
    }

    private suspend fun fallbackToRest(
        message: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>>,
        userMbti: String? = null,
        characterName: String = "",
        charId: String = "",
        memories: List<MemoryItem> = emptyList()
    ) {
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
            memories = memories
        )

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

        if (result.affinityDelta != 0) {
            val before = characterRepo.getById(characterId)?.affinityLevel ?: 1
            characterRepo.updateAffinity(characterId, result.affinityDelta)
            val after = characterRepo.getById(characterId)?.affinityLevel ?: 1
            if (after > before) {
                levelUpEvent = after
            } else if (after < before) {
                levelDownEvent = after
            }
        }

        isTyping = false
    }

    fun clearChat() {
        viewModelScope.launch {
            chatRepo.clearMessages(characterId)
        }
    }
}
