package com.example.mbtichatfriend.data.voice

import kotlinx.coroutines.flow.StateFlow

enum class TtsState { IDLE, SPEAKING, ERROR }

data class TtsVoiceOption(
    val id: String,
    val name: String,
    val localeTag: String,
    val quality: Int,
    val latency: Int,
    val requiresNetwork: Boolean
)

/**
 * TTS 엔진 추상화.
 * 현재는 Android 내장 TTS를 사용하며, 이후 OpenAI/클라우드 TTS 엔진으로 교체 가능하게 둔다.
 */
interface TtsEngine {
    val state: StateFlow<TtsState>
    val availableVoices: StateFlow<List<TtsVoiceOption>>

    fun initialize(onReady: () -> Unit = {}, onError: (String) -> Unit = {})
    fun speak(text: String, onDone: () -> Unit = {})
    fun stop()
    fun shutdown()
    fun setVoice(voiceId: String?)
    fun setVoiceParams(pitch: Float = 1.0f, speed: Float = 1.0f)
}
