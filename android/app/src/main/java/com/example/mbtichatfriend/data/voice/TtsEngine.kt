package com.example.mbtichatfriend.data.voice

import kotlinx.coroutines.flow.StateFlow

enum class TtsState { IDLE, SPEAKING, ERROR }

/**
 * TTS 엔진 추상화 인터페이스
 * 현재: AndroidTtsEngine (내장 TTS)
 * 추후: OpenAiTtsEngine 으로 교체 가능
 */
interface TtsEngine {
    val state: StateFlow<TtsState>

    fun initialize(onReady: () -> Unit = {}, onError: (String) -> Unit = {})
    fun speak(text: String, onDone: () -> Unit = {})
    fun stop()
    fun shutdown()
    fun setVoiceParams(pitch: Float = 1.0f, speed: Float = 1.0f)
}
