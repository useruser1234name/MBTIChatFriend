package com.example.mbtichatfriend.data.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale
import java.util.UUID

class AndroidTtsEngine(private val context: Context) : TtsEngine {

    private var tts: TextToSpeech? = null

    private val _state = MutableStateFlow(TtsState.IDLE)
    override val state: StateFlow<TtsState> = _state

    private var pendingOnDone: (() -> Unit)? = null

    override fun initialize(onReady: () -> Unit, onError: (String) -> Unit) {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.KOREAN
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        _state.value = TtsState.SPEAKING
                    }
                    override fun onDone(utteranceId: String?) {
                        _state.value = TtsState.IDLE
                        val cb = pendingOnDone
                        pendingOnDone = null
                        cb?.invoke()
                    }
                    @Deprecated("Deprecated in Java")
                    override fun onError(utteranceId: String?) {
                        _state.value = TtsState.ERROR
                        pendingOnDone = null
                    }
                })
                onReady()
            } else {
                onError("TTS 초기화 실패")
            }
        }
    }

    override fun speak(text: String, onDone: () -> Unit) {
        pendingOnDone = onDone
        val utteranceId = UUID.randomUUID().toString()
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }

    override fun stop() {
        tts?.stop()
        _state.value = TtsState.IDLE
        pendingOnDone = null
    }

    override fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
    }

    override fun setVoiceParams(pitch: Float, speed: Float) {
        tts?.setPitch(pitch)
        tts?.setSpeechRate(speed)
    }
}
