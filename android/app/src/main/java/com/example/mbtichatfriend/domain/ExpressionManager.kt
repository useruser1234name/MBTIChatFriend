package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageSetRequest
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * ExpressionManager — 캐릭터 표정 세트(expressionSet) 전담 관리 클래스.
 *
 * ChatViewModel에서 분리된 단일 책임 클래스 (W1-3 스트랭글러 패턴 2단계).
 * ARCH-A 조성현 설계.
 *
 * 책임:
 * - expressionUrls 상태 관리
 * - 표정 세트 백그라운드 생성 및 폴링
 * - 기존 표정 세트 로드 (init 대리)
 * - JSON 파싱
 */
@Singleton
class ExpressionManager @Inject constructor(
    private val characterRepo: CharacterRepository,
    private val prefs: UserPreferences,
    private val chatApi: ChatApi,
    private val moshi: Moshi,
) {
    private val _expressionUrls = MutableStateFlow<Map<String, String>?>(null)
    val expressionUrls: StateFlow<Map<String, String>?> = _expressionUrls.asStateFlow()

    private var expressionSetTaskId: String? = null

    /**
     * ViewModel init 시점에 호출 — 기존 표정 세트 로드 또는 진행 중인 폴링 재개.
     *
     * @param characterId 대상 캐릭터 ID
     * @param scope ViewModel의 viewModelScope
     */
    fun loadExistingExpressionSet(characterId: Long, scope: CoroutineScope) {
        scope.launch {
            val ch = characterRepo.getById(characterId) ?: return@launch
            if (ch.expressionSetReady && ch.expressionSet != null) {
                _expressionUrls.value = parseExpressionSet(ch.expressionSet)
            } else if (ch.avatarId.startsWith("img:")) {
                val taskId = prefs.getExpressionSetTaskId(characterId)
                if (taskId != null) {
                    pollExpressionSetStatus(characterId, taskId)
                }
            }
        }
    }

    /**
     * 표정 세트 백그라운드 생성 시작 + 폴링.
     * ImageGeneratorSheet에서 캐릭터 생성 직후 호출.
     *
     * @param basePrompt 이미지 생성 기반 프롬프트
     * @param characterIdStr 캐릭터 ID 문자열
     * @param characterId 캐릭터 ID Long
     * @param scope ViewModel의 viewModelScope
     */
    fun startExpressionSetGeneration(
        basePrompt: String,
        characterIdStr: String,
        characterId: Long,
        scope: CoroutineScope,
    ) {
        scope.launch {
            try {
                val response = chatApi.generateImageSet(
                    ImageSetRequest(
                        basePrompt = basePrompt,
                        characterId = characterIdStr
                    )
                )
                expressionSetTaskId = response.taskId
                pollExpressionSetStatus(characterId, response.taskId)
            } catch (e: Exception) {
                android.util.Log.w("ExpressionManager", "Expression set generation failed", e)
            }
        }
    }

    /**
     * 표정 세트 생성 상태 폴링 (10초 간격, 최대 30회).
     */
    suspend fun pollExpressionSetStatus(characterId: Long, taskId: String) {
        val maxAttempts = 30
        var attempt = 0
        while (attempt < maxAttempts) {
            delay(10_000)
            attempt++
            try {
                val status = chatApi.getImageSetStatus(taskId)
                when (status.status) {
                    "completed" -> {
                        _expressionUrls.value = status.urls
                        val type = Types.newParameterizedType(Map::class.java, String::class.java, String::class.java)
                        val adapter = moshi.adapter<Map<String, String>>(type)
                        val json = adapter.toJson(status.urls)
                        characterRepo.updateExpressionSet(characterId, json)
                        prefs.clearExpressionSetTaskId(characterId)
                        return
                    }
                    "failed" -> {
                        prefs.clearExpressionSetTaskId(characterId)
                        return
                    }
                    // "processing" → 계속 폴링
                }
            } catch (_: Exception) {
                // 네트워크 오류 시 재시도
            }
        }
        prefs.clearExpressionSetTaskId(characterId)
        android.util.Log.w("ExpressionManager", "Expression set polling timed out after $maxAttempts attempts")
    }

    /**
     * expressionSet JSON 문자열을 Map으로 파싱.
     */
    fun parseExpressionSet(json: String): Map<String, String>? {
        return try {
            val type = Types.newParameterizedType(Map::class.java, String::class.java, String::class.java)
            val adapter = moshi.adapter<Map<String, String>>(type)
            adapter.fromJson(json)
        } catch (_: Exception) {
            null
        }
    }
}
