package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class FinetuneStartRequest(
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "character_name") val characterName: String = "",
    val mbti: String,
    @Json(name = "speech_style") val speechStyle: String,
    val relationship: String,
    val nickname: String,
    @Json(name = "affinity_level") val affinityLevel: Int = 1,
    val conversations: List<Map<String, String>> = emptyList()
)

@JsonClass(generateAdapter = false)
data class FinetuneStartResponse(
    @Json(name = "job_id") val jobId: String = "",
    val status: String,
    @Json(name = "training_count") val trainingCount: Int = 0,
    val model: String = "",
    val error: String = ""
)

@JsonClass(generateAdapter = false)
data class FinetuneStatusResponse(
    @Json(name = "job_id") val jobId: String,
    val status: String,
    @Json(name = "fine_tuned_model") val fineTunedModel: String = "",
    val error: String = ""
)

@JsonClass(generateAdapter = false)
data class FinetuneActivateRequest(
    @Json(name = "character_id") val characterId: String,
    @Json(name = "model_id") val modelId: String
)
