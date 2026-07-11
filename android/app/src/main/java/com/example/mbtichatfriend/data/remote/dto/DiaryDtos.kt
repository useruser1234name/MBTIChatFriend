package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class DiaryRequest(
    @Json(name = "character_name") val characterName: String = "",
    val mbti: String,
    @Json(name = "speech_style") val speechStyle: String = "CASUAL",
    val nickname: String = "",
    @Json(name = "affinity_level") val affinityLevel: Int = 1,
    @Json(name = "conversation_history") val conversationHistory: List<Map<String, String>> = emptyList()
)

@JsonClass(generateAdapter = false)
data class DiaryResponse(
    val diary: String,
    val emotion: String = "NEUTRAL"
)

// ── 다이어리 직접 입력 모델 (32차 스프린트) ───────────────────────────────────

@JsonClass(generateAdapter = false)
data class DiaryEntryRequest(
    val content: String,
    val tags: List<String> = emptyList()
)

@JsonClass(generateAdapter = false)
data class DiaryEntry(
    val id: Long = 0,
    val content: String,
    val tags: List<String> = emptyList(),
    @Json(name = "created_at") val createdAt: String = ""
)

@JsonClass(generateAdapter = false)
data class DiaryWeeklyReport(
    @Json(name = "emotion_counts") val emotionCounts: Map<String, Int> = emptyMap(),
    val summary: String = ""
)
