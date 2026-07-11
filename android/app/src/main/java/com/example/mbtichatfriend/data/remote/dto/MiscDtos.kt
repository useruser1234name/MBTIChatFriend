package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class FcmTokenRequest(
    val token: String,
    @Json(name = "user_id") val userId: String = ""
)

// ── 편지 모델 ────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class LetterResponse(
    @Json(name = "has_letter") val has_letter: Boolean,
    @Json(name = "content") val content: String,
    @Json(name = "generated_date") val generated_date: String,
)

// ── 분석 이벤트 모델 (PM 로드맵) ─────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ClientEventDto(
    @Json(name = "event_type") val eventType: String,
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "character_id") val characterId: String = "",
    val payload: Map<String, Any?> = emptyMap(),
)

@JsonClass(generateAdapter = false)
data class EventBatchRequest(
    val events: List<ClientEventDto>,
)

@JsonClass(generateAdapter = false)
data class EventBatchResponse(
    val accepted: Int = 0,
    val skipped: List<String> = emptyList(),
)

// ── 궁합 모델 (21차 스프린트) ────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class CompatibilityResult(
    @Json(name = "mbti_a") val mbtiA: String,
    @Json(name = "mbti_b") val mbtiB: String,
    val type: String,
    val title: String,
    val description: String,
    val tips: List<String>,
)

// ── 알림 모델 (21차 스프린트) ────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class AppNotification(
    val id: Long,
    val type: String,
    val title: String,
    val body: String,
    @Json(name = "is_read") val isRead: Boolean,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "deep_link") val deepLink: String? = null,
)

@JsonClass(generateAdapter = false)
data class UnreadCountResponse(val count: Int)

// ── 연말 대화 리포트 모델 (22차 스프린트) ─────────────────────────────────────

@JsonClass(generateAdapter = false)
data class YearReportResponse(
    @Json(name = "total_messages") val totalMessages: Int,
    @Json(name = "top_character") val topCharacter: String?,
    @Json(name = "top_post_summary") val topPostSummary: String?,
    @Json(name = "top_post_empathy") val topPostEmpathy: Int,
)

// ── 발렌타인 궁합 특집 모델 (24차 스프린트) ───────────────────────────────────

@JsonClass(generateAdapter = false)
data class ValentineMessage(
    val mbti: String,
    val message: String,
)

// ── 가정의 달 감사 카드 모델 (26차 스프린트) ──────────────────────────────────

@JsonClass(generateAdapter = false)
data class GratitudeMessage(
    val mbti: String,
    val message: String
)

// ── 여름 궁합 메시지 모델 (35차 스프린트) ─────────────────────────────────────

@JsonClass(generateAdapter = false)
data class SummerMessageResponse(
    val mbti: String,
    val message: String
)

// ── 16종 전체 완성 메시지 모델 (37차 스프린트) ────────────────────────────────

@JsonClass(generateAdapter = false)
data class AllCompleteResponse(
    val mbti: String,
    val message: String
)
