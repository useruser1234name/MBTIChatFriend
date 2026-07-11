package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class ImageGenerateRequest(
    val prompt: String,
    val size: String = "1024x1024",
    val quality: String = "standard"
)

@JsonClass(generateAdapter = false)
data class ImageGenerateResponse(
    val url: String,
    @Json(name = "revised_prompt") val revisedPrompt: String? = null
)

@JsonClass(generateAdapter = false)
data class ImageSetRequest(
    @Json(name = "base_prompt") val basePrompt: String,
    @Json(name = "character_id") val characterId: String,
    val size: String = "1024x1024"
)

@JsonClass(generateAdapter = false)
data class ImageSetResponse(
    val status: String,
    @Json(name = "task_id") val taskId: String
)

@JsonClass(generateAdapter = false)
data class ImageSetStatusResponse(
    val status: String,
    val completed: Int = 0,
    val total: Int = 15,
    val urls: Map<String, String> = emptyMap()
)
