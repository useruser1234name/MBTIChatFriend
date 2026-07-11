package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── 커뮤니티 모델 (19차 스프린트) ────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class CommunityPost(
    val id: Long,
    val mbti: String,
    val content: String,
    @Json(name = "anonymous_name") val anonymousName: String,
    @Json(name = "empathy_count") val empathyCount: Int,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "comment_count") val commentCount: Int = 0,
)

@JsonClass(generateAdapter = false)
data class CreatePostRequest(
    @Json(name = "user_id") val userId: String,
    val mbti: String,
    val content: String,
)

@JsonClass(generateAdapter = false)
data class EmpathyToggleRequest(
    @Json(name = "user_id") val userId: String,
    @Json(name = "anonymous_name") val anonymousName: String = "익명",
)

@JsonClass(generateAdapter = false)
data class EmpathyToggleResponse(
    val empathized: Boolean,
)

// ── 커뮤니티 댓글 모델 (20차 스프린트) ──────────────────────────────────────

@JsonClass(generateAdapter = false)
data class CommunityComment(
    val id: Long,
    val mbti: String,
    val content: String,
    @Json(name = "anonymous_name") val anonymousName: String,
    @Json(name = "created_at") val createdAt: String,
)

@JsonClass(generateAdapter = false)
data class CreateCommentRequest(
    @Json(name = "user_id") val userId: String,
    val mbti: String,
    val content: String,
)

// ── 트렌딩 게시글 모델 (22차 스프린트) ───────────────────────────────────────

@JsonClass(generateAdapter = false)
data class TrendingPostUi(
    val id: Long,
    @Json(name = "mbti_type") val mbtiType: String,
    val content: String,
    @Json(name = "empathy_count") val empathyCount: Int,
    @Json(name = "comment_count") val commentCount: Int,
)

// ── 커뮤니티 신고 모델 (25차 스프린트) ───────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReportRequest(val reason: String)

@JsonClass(generateAdapter = false)
data class ReportResponse(val ok: Boolean)
