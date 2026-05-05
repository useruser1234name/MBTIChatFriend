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

    private val _availableVoices = MutableStateFlow<List<TtsVoiceOption>>(emptyList())
    override val availableVoices: StateFlow<List<TtsVoiceOption>> = _availableVoices

    private var selectedVoiceId: String? = null
    private var pendingOnDone: (() -> Unit)? = null

    override fun initialize(onReady: () -> Unit, onError: (String) -> Unit) {
        tts = TextToSpeech(context) { status ->
            val engine = tts
            if (status == TextToSpeech.SUCCESS && engine != null) {
                engine.language = Locale.KOREAN
                refreshVoices(engine)
                selectedVoiceId?.let { setVoice(it) }
                engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        _state.value = TtsState.SPEAKING
                    }

                    override fun onDone(utteranceId: String?) {
                        completePending(TtsState.IDLE)
                    }

                    @Deprecated("Deprecated in Java")
                    override fun onError(utteranceId: String?) {
                        completePending(TtsState.ERROR)
                    }

                    override fun onError(utteranceId: String?, errorCode: Int) {
                        completePending(TtsState.ERROR)
                    }

                    override fun onStop(utteranceId: String?, interrupted: Boolean) {
                        completePending(TtsState.IDLE)
                    }
                })
                onReady()
            } else {
                _state.value = TtsState.ERROR
                onError("TTS 초기화에 실패했습니다.")
            }
        }
    }

    override fun speak(text: String, onDone: () -> Unit) {
        val engine = tts
        if (text.isBlank() || engine == null) {
            onDone()
            return
        }

        pendingOnDone = onDone
        val utteranceId = UUID.randomUUID().toString()
        val result = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        if (result == TextToSpeech.ERROR) {
            completePending(TtsState.ERROR)
        }
    }

    override fun stop() {
        tts?.stop()
        completePending(TtsState.IDLE)
    }

    override fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        _availableVoices.value = emptyList()
        completePending(TtsState.IDLE)
    }

    override fun setVoice(voiceId: String?) {
        selectedVoiceId = voiceId?.takeIf { it.isNotBlank() }
        val engine = tts ?: return
        val id = selectedVoiceId ?: run {
            engine.language = Locale.KOREAN
            return
        }

        val voice = engine.voices?.firstOrNull { it.name == id } ?: return
        engine.voice = voice
    }

    override fun setVoiceParams(pitch: Float, speed: Float) {
        tts?.setPitch(pitch)
        tts?.setSpeechRate(speed)
    }

    private fun refreshVoices(engine: TextToSpeech) {
        val voices = engine.voices.orEmpty()
            .filter { it.locale.language == Locale.KOREAN.language }
            .sortedWith(
                compareBy(
                    { it.isNetworkConnectionRequired },
                    { it.locale.toLanguageTag() },
                    { it.name }
                )
            )
            .map { voice ->
                TtsVoiceOption(
                    id = voice.name,
                    name = buildVoiceLabel(voice.name, voice.locale),
                    localeTag = voice.locale.toLanguageTag(),
                    quality = voice.quality,
                    latency = voice.latency,
                    requiresNetwork = voice.isNetworkConnectionRequired
                )
            }
        _availableVoices.value = voices
    }

    private fun buildVoiceLabel(name: String, locale: Locale): String {
        val language = locale.getDisplayLanguage(Locale.KOREAN).ifBlank { locale.toLanguageTag() }
        val country = locale.getDisplayCountry(Locale.KOREAN)
        return listOf(language, country, name)
            .filter { it.isNotBlank() }
            .joinToString(" / ")
    }

    private fun completePending(nextState: TtsState) {
        _state.value = nextState
        val callback = pendingOnDone
        pendingOnDone = null
        callback?.invoke()
    }
}
