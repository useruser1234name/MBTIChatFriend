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
import com.example.mbtichatfriend.data.voice.SpeechRecognizerManager
import com.example.mbtichatfriend.data.voice.SttState
import com.example.mbtichatfriend.data.voice.TtsEngine
import com.example.mbtichatfriend.model.CharacterEmotion
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

/** 음성 대화 상태 머신 */
enum class VoiceCallState {
    IDLE,           // 대기 중 (마이크 버튼 활성)
    LISTENING,      // 사용자 음성 듣는 중
    PROCESSING,     // 서버 응답 대기 중
    SPEAKING        // TTS 재생 중
}

@HiltViewModel
class VoiceCallViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val chatRepo: ChatRepository,
    private val characterRepo: CharacterRepository,
    private val prefs: UserPreferences,
    private val ttsEngine: TtsEngine,
    private val sttManager: SpeechRecognizerManager
) : ViewModel() {

    val characterId: Long = savedStateHandle.get<String>("characterId")?.toLongOrNull() ?: 0L

    val character = characterRepo.observeById(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val messages = chatRepo.observeMessages(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    // ── UI 상태 ──────────────────────────────────────────────
    var callState by mutableStateOf(VoiceCallState.IDLE)
        private set

    var currentEmotion by mutableStateOf(CharacterEmotion.NEUTRAL)
        private set

    /** 캐릭터가 말하는 자막 (현재 ReplyPart 텍스트) */
    var characterSubtitle by mutableStateOf("")
        private set

    /** 사용자 STT 결과 (partial 포함) */
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

        // 캐릭터가 로드되면 음성 파라미터 적용
        viewModelScope.launch {
            character.collect { ch ->
                if (ch != null) applyVoiceParams()
            }
        }
    }

    private fun applyVoiceParams() {
        val ch = character.value ?: return
        when (ch.speechStyle) {
            "SWEET"     -> ttsEngine.setVoiceParams(pitch = 1.25f, speed = 0.9f)
            "TSUNDERE"  -> ttsEngine.setVoiceParams(pitch = 1.1f,  speed = 1.05f)
            "FORMAL"    -> ttsEngine.setVoiceParams(pitch = 0.95f, speed = 0.95f)
            else        -> ttsEngine.setVoiceParams(pitch = 1.0f,  speed = 1.0f)
        }
    }

    // ── STT ──────────────────────────────────────────────────

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

    // ── 메시지 송수신 ─────────────────────────────────────────

    private fun sendVoiceMessage(text: String) {
        viewModelScope.launch {
            callState = VoiceCallState.PROCESSING

            // 사용자 메시지 저장
            chatRepo.saveMessage(characterId, text, isFromUser = true)

            val ch = characterRepo.getById(characterId) ?: run {
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

            // SSE 스트리밍으로 응답 수신
            chatRepo.streamMessage(
                message = text,
                mbti = ch.mbti,
                speechStyle = ch.speechStyle,
                relationship = ch.relationship,
                nickname = nickname,
                affinityLevel = ch.affinityLevel,
                conversationHistory = history,
                userMbti = userMbti,
                characterName = ch.name
            ).catch { e ->
                errorMessage = "연결 오류: ${e.message}"
                callState = VoiceCallState.IDLE
            }.collect { event ->
                when (event) {
                    is SseEvent.Message -> {
                        val emotion = try {
                            CharacterEmotion.valueOf(event.emotion)
                        } catch (_: Exception) { CharacterEmotion.NEUTRAL }

                        currentEmotion = emotion
                        characterSubtitle = event.text

                        // DB 저장
                        chatRepo.saveMessage(
                            characterId = characterId,
                            text = event.text,
                            isFromUser = false,
                            emotion = event.emotion
                        )

                        // TTS 재생 (메인 스레드에서 호출 필요)
                        callState = VoiceCallState.SPEAKING
                        withContext(Dispatchers.Main) {
                            speakAndWait(event.text)
                        }
                    }
                    is SseEvent.Done -> {
                        if (event.affinityDelta != 0) {
                            val before = characterRepo.getById(characterId)?.affinityLevel ?: 1
                            characterRepo.updateAffinity(characterId, event.affinityDelta)
                            val after = characterRepo.getById(characterId)?.affinityLevel ?: 1
                            if (after > before) levelUpEvent = after
                        }
                        // TTS가 끝날 때까지 기다린 후 IDLE로 전환은 speakAndWait에서 처리
                    }
                    is SseEvent.Error -> {
                        if (callState == VoiceCallState.PROCESSING) {
                            callState = VoiceCallState.IDLE
                        }
                    }
                }
            }

            // Flow 완료 후 TTS가 이미 끝났으면 IDLE
            if (callState == VoiceCallState.PROCESSING) {
                callState = VoiceCallState.IDLE
            }
        }
    }

    /**
     * TTS 재생 후 완료될 때까지 suspend.
     * speak()의 onDone 콜백을 코루틴으로 변환.
     */
    private suspend fun speakAndWait(text: String) {
        suspendCancellableCoroutine<Unit> { cont ->
            ttsEngine.speak(text) {
                if (cont.isActive) cont.resume(Unit)
            }
            cont.invokeOnCancellation { ttsEngine.stop() }
        }
        // 이 ReplyPart TTS 완료 → 다음 이벤트 대기 or IDLE
        if (callState == VoiceCallState.SPEAKING) {
            callState = VoiceCallState.IDLE
        }
    }

    // ── 종료 ─────────────────────────────────────────────────

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
