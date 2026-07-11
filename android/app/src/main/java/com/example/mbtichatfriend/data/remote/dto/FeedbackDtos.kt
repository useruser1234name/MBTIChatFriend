package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class FeedbackRequest(
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "message_id") val messageId: String,
    @Json(name = "feedback_type") val feedbackType: String,
    @Json(name = "feedback_detail") val feedbackDetail: String = ""
)

// ── 세션 별점 피드백 (server/app/routers/quality.py SessionFeedbackRequest 스키마와 일치) ──

@JsonClass(generateAdapter = false)
data class SessionFeedbackRequest(
    @Json(name = "session_id") val sessionId: String,
    @Json(name = "room_id") val roomId: String,
    val rating: Int,
    val text: String? = null
)
