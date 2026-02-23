package com.example.mbtichatfriend.data.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

enum class SttState { IDLE, LISTENING, PROCESSING, ERROR }

class SpeechRecognizerManager(private val context: Context) {

    private var recognizer: SpeechRecognizer? = null

    private val _state = MutableStateFlow(SttState.IDLE)
    val state: StateFlow<SttState> = _state

    private val _partialResult = MutableStateFlow("")
    val partialResult: StateFlow<String> = _partialResult

    private var onFinalResult: ((String) -> Unit)? = null
    private var onErrorCallback: ((String) -> Unit)? = null

    val isAvailable: Boolean
        get() = SpeechRecognizer.isRecognitionAvailable(context)

    fun initialize() {
        if (!isAvailable) return
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(createListener())
        }
    }

    fun startListening(onResult: (String) -> Unit, onError: (String) -> Unit = {}) {
        if (!isAvailable) {
            onError("이 기기에서는 음성 인식을 사용할 수 없어요")
            return
        }
        onFinalResult = onResult
        onErrorCallback = onError
        _partialResult.value = ""

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ko-KR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        _state.value = SttState.LISTENING
        recognizer?.startListening(intent)
    }

    fun stopListening() {
        recognizer?.stopListening()
    }

    fun destroy() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun createListener() = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            _state.value = SttState.LISTENING
        }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {
            _state.value = SttState.PROCESSING
        }
        override fun onError(error: Int) {
            val msg = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH -> "음성을 인식하지 못했어요"
                SpeechRecognizer.ERROR_NETWORK,
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "네트워크 연결을 확인해주세요"
                SpeechRecognizer.ERROR_AUDIO -> "마이크 오류가 발생했어요"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "말씀을 듣지 못했어요"
                else -> "음성 인식 오류"
            }
            onErrorCallback?.invoke(msg)
            _state.value = SttState.IDLE
        }
        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val text = matches?.firstOrNull()?.trim() ?: ""
            _partialResult.value = text
            if (text.isNotEmpty()) {
                onFinalResult?.invoke(text)
            }
            _state.value = SttState.IDLE
        }
        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            _partialResult.value = matches?.firstOrNull() ?: ""
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
