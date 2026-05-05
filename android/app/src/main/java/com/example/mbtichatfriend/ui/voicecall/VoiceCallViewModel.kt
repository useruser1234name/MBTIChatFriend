package com.example.mbtichatfriend.ui.voicecall

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.MemoryRepository
import com.example.mbtichatfriend.data.voice.SpeechRecognizerManager
import com.example.mbtichatfriend.data.voice.TtsEngine
import com.example.mbtichatfriend.model.CharacterEmotion
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import javax.inject.Inject

enum class VoiceCallState {
    IDLE,
    LISTENING,
    PROCESSING,
    SPEAKING
}

@HiltViewModel
class VoiceCallViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val chatRepo: ChatRepository,
    private val characterRepo: CharacterRepository,
    private val memoryRepo: MemoryRepository,
    private val prefs: UserPreferences,
    private val ttsEngine: TtsEngine,
    private val sttManager: SpeechRecognizerManager
) : ViewModel() {

    val characterId: Long = savedStateHandle.get<String>("characterId")?.toLongOrNull() ?: 0L

    val character = characterRepo.observeById(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val messages = chatRepo.observeMessages(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    var callState by mutableStateOf(VoiceCallState.IDLE)
        private set

    var currentEmotion by mutableStateOf(CharacterEmotion.NEUTRAL)
        private set

    var characterSubtitle by mutableStateOf("")
        private set

    val userSpeechText = sttManager.partialResult

    var errorMessage by mutableStateOf<String?>(null)
        private set

    var levelUpEvent by mutableStateOf<Int?>(null)
        private set

    val ttsState = ttsEngine.state
    val sttState = sttManager.state

    init {
        ttsEngine.initialize(
            onReady = { applyVoiceParams() },
            onError = { errorMessage = it }
        )
        sttManager.initialize()

        viewModelScope.launch {
            character.collect { ch ->
                if (ch != null) {
                    applyVoiceParams()
                }
            }
        }
    }

    private fun applyVoiceParams() {
        val ch = character.value ?: return
        when (ch.speechStyle) {
            "SWEET" -> ttsEngine.setVoiceParams(pitch = 1.25f, speed = 0.9f)
            "TSUNDERE" -> ttsEngine.setVoiceParams(pitch = 1.1f, speed = 1.05f)
            "FORMAL" -> ttsEngine.setVoiceParams(pitch = 0.95f, speed = 0.95f)
            else -> ttsEngine.setVoiceParams(pitch = 1.0f, speed = 1.0f)
        }
    }

    fun startListening() {
        if (callState != VoiceCallState.IDLE) return
        callState = VoiceCallState.LISTENING
        characterSubtitle = ""

        sttManager.startListening(
            onResult = { text ->
                if (text.isNotEmpty()) {
                    sendVoiceMessage(text)
                } else {
                    callState = VoiceCallState.IDLE
                }
            },
            onError = { msg ->
                errorMessage = msg
                callState = VoiceCallState.IDLE
            }
        )
    }

    fun stopListening() {
        sttManager.stopListening()
    }

    private fun sendVoiceMessage(text: String) {
        viewModelScope.launch {
            callState = VoiceCallState.PROCESSING

            val userMessageId = chatRepo.saveMessage(
                characterId = characterId,
                text = text,
                isFromUser = true,
                sendStatus = "PENDING"
            )

            val ch = characterRepo.getById(characterId) ?: run {
                chatRepo.deleteMessage(userMessageId)
                callState = VoiceCallState.IDLE
                return@launch
            }

            val nickname = prefs.nickname.first()
            val userMbti = prefs.userMbti.first().ifEmpty { null }
            val history = messages.value.takeLast(20).map { msg ->
                mapOf(
                    "role" to if (msg.isFromUser) "user" else "assistant",
                    "content" to msg.text
                )
            }
            val memories = runCatching { memoryRepo.loadMemories(characterId) }.getOrDefault(emptyList())
            var replyReceived = false

            chatRepo.streamMessage(
                message = text,
                mbti = ch.mbti,
                speechStyle = ch.speechStyle,
                relationship = ch.relationship,
                nickname = nickname,
                affinityLevel = ch.affinityLevel,
                conversationHistory = history,
                userMbti = userMbti,
                characterName = ch.name,
                characterId = ch.id.toString(),
                personaRaw = ch.personaRaw,
                personaSummary = ch.personaSummary,
                dialoguePrompt = ch.dialoguePrompt,
                visualPrompt = ch.visualPrompt,
                memories = memories
            ).catch { error ->
                chatRepo.updateSendStatus(userMessageId, "FAILED")
                errorMessage = error.message ?: "연결 오류"
                callState = VoiceCallState.IDLE
            }.collect { event ->
                when (event) {
                    is SseEvent.Message -> {
                        if (!replyReceived) {
                            chatRepo.updateSendStatus(userMessageId, "SENT")
                            replyReceived = true
                        }

                        val emotion = try {
                            CharacterEmotion.valueOf(event.emotion)
                        } catch (_: Exception) {
                            CharacterEmotion.NEUTRAL
                        }
                        currentEmotion = emotion
                        characterSubtitle = event.text

                        chatRepo.saveMessage(
                            characterId = characterId,
                            text = event.text,
                            isFromUser = false,
                            emotion = event.emotion
                        )

                        callState = VoiceCallState.SPEAKING
                        withContext(Dispatchers.Main) {
                            speakAndWait(event.text)
                        }
                    }

                    is SseEvent.Done -> {
                        if (!replyReceived) {
                            chatRepo.updateSendStatus(userMessageId, "SENT")
                            replyReceived = true
                        }

                        if (event.affinityDelta != 0) {
                            val before = characterRepo.getById(characterId)?.affinityLevel ?: 1
                            characterRepo.updateAffinity(characterId, event.affinityDelta)
                            val after = characterRepo.getById(characterId)?.affinityLevel ?: 1
                            if (after > before) {
                                levelUpEvent = after
                            }
                        }
                    }

                    is SseEvent.Error -> {
                        if (event.statusCode in 400..499) {
                            chatRepo.deleteMessage(userMessageId)
                        } else {
                            chatRepo.updateSendStatus(userMessageId, "FAILED")
                        }
                        errorMessage = event.message
                        if (callState == VoiceCallState.PROCESSING) {
                            callState = VoiceCallState.IDLE
                        }
                    }
                }
            }

            if (callState == VoiceCallState.PROCESSING) {
                callState = VoiceCallState.IDLE
            }
        }
    }

    private suspend fun speakAndWait(text: String) {
        suspendCancellableCoroutine<Unit> { cont ->
            ttsEngine.speak(text) {
                if (cont.isActive) {
                    cont.resume(Unit)
                }
            }
            cont.invokeOnCancellation { ttsEngine.stop() }
        }

        if (callState == VoiceCallState.SPEAKING) {
            callState = VoiceCallState.IDLE
        }
    }

    fun endCall() {
        ttsEngine.stop()
        sttManager.stopListening()
        callState = VoiceCallState.IDLE
        characterSubtitle = ""
    }

    fun dismissError() {
        errorMessage = null
    }

    fun dismissLevelUp() {
        levelUpEvent = null
    }

    override fun onCleared() {
        ttsEngine.shutdown()
        sttManager.destroy()
    }
}
