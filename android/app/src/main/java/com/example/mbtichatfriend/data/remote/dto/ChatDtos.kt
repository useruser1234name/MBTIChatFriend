package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class MemoryItem(
    val key: String,
    val value: String
)

@JsonClass(generateAdapter = false)
data class MemoryExtractRequest(
    @Json(name = "character_name") val characterName: String = "",
    @Json(name = "character_id") val characterId: String = "",
    val nickname: String = "",
    @Json(name = "conversation_history") val conversationHistory: List<Map<String, String>> = emptyList()
)

@JsonClass(generateAdapter = false)
data class MemoryExtractResponse(
    val memories: List<MemoryItem>
)

@JsonClass(generateAdapter = false)
data class ChatRequest(
    val message: String,
    @Json(name = "mbti") val mbti: String,
    @Json(name = "speech_style") val speechStyle: String,
    @Json(name = "relationship") val relationship: String,
    @Json(name = "nickname") val nickname: String,
    @Json(name = "affinity_level") val affinityLevel: Int = 1,
    @Json(name = "conversation_history") val conversationHistory: List<Map<String, String>> = emptyList(),
    @Json(name = "user_mbti") val userMbti: String? = null,
    @Json(name = "character_name") val characterName: String = "",
    @Json(name = "character_id") val characterId: String = "",
    val memories: List<MemoryItem> = emptyList(),
    // M2: "내 역할"/"지금 상황" — 채팅 화면 상단 메뉴에서 캐릭터별로 설정. 빈 문자열이면 서버가 무시.
    @Json(name = "user_role") val userRole: String = "",
    @Json(name = "situation") val situation: String = ""
)

// R1: 선톡(캐릭터 선발화) 전용 요청 — /api/v1/chat/proactive.
// ChatRequest와 필드 구성은 거의 같지만 message 대신 hook(다음 대화 흐름 힌트)만
// 보낸다. 유도 문구 합성은 서버 책임(routers/chat.build_proactive_message).
@JsonClass(generateAdapter = false)
data class ProactiveChatRequest(
    val hook: String,
    @Json(name = "mbti") val mbti: String,
    @Json(name = "speech_style") val speechStyle: String,
    @Json(name = "relationship") val relationship: String,
    @Json(name = "nickname") val nickname: String,
    @Json(name = "affinity_level") val affinityLevel: Int = 1,
    @Json(name = "conversation_history") val conversationHistory: List<Map<String, String>> = emptyList(),
    @Json(name = "user_mbti") val userMbti: String? = null,
    @Json(name = "character_name") val characterName: String = "",
    @Json(name = "character_id") val characterId: String = "",
    val memories: List<MemoryItem> = emptyList(),
    @Json(name = "user_role") val userRole: String = "",
    @Json(name = "situation") val situation: String = ""
)

@JsonClass(generateAdapter = false)
data class ChatResponse(
    val replies: List<ReplyPart>,
    @Json(name = "affinity_delta") val affinityDelta: Int = 0,
    @Json(name = "night_diary_generated") val nightDiaryGenerated: Boolean = false,
    @Json(name = "next_hook") val nextHook: String = "",
    @Json(name = "next_goal") val nextGoal: String = ""
)

@JsonClass(generateAdapter = false)
data class ReplyPart(
    val text: String,
    val emotion: String = "NEUTRAL",
    val delay: Long = 500
)

// ── 관계 히스토리 & 기억 앨범 모델 (UX-B 안현우 + UI-C 정수아, 5차 회의 합의) ──

@JsonClass(generateAdapter = false)
data class MemoryMomentRequest(
    @Json(name = "character_id") val characterId: String,
    @Json(name = "message_text") val messageText: String,
    @Json(name = "moment_type") val momentType: String = "special",
    @Json(name = "user_note") val userNote: String = ""
)

@JsonClass(generateAdapter = false)
data class MemoryMomentItem(
    val id: Long? = null,
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "user_id") val userId: String = "",
    @Json(name = "message_text") val messageText: String = "",
    @Json(name = "moment_type") val momentType: String = "special",
    @Json(name = "user_note") val userNote: String = "",
    @Json(name = "created_at") val createdAt: String = ""
)

@JsonClass(generateAdapter = false)
data class MemoryAlbumResponse(
    val album: List<MemoryMomentItem> = emptyList()
)

@JsonClass(generateAdapter = false)
data class RelationshipSummaryResponse(
    @Json(name = "total_messages") val totalMessages: Int = 0,
    @Json(name = "total_sessions") val totalSessions: Int = 0,
    @Json(name = "days_together") val daysTogether: Int = 0,
    @Json(name = "affinity_journey") val affinityJourney: List<List<Any>> = emptyList(),
    @Json(name = "top_topics") val topTopics: List<String> = emptyList(),
    @Json(name = "first_chat_date") val firstChatDate: String = ""
)

// ── Self-Regulation 모델 (PSY-B 최은혜 + PM-B 손민준, 4차 회의 합의) ────────

@JsonClass(generateAdapter = false)
data class SessionCheckRequest(
    @Json(name = "room_id") val roomId: String,
    @Json(name = "user_birth_year") val userBirthYear: Int? = null
)

@JsonClass(generateAdapter = false)
data class SessionCheckResponse(
    @Json(name = "should_warn") val shouldWarn: Boolean = false,
    @Json(name = "elapsed_minutes") val elapsedMinutes: Int = 0,
    @Json(name = "limit_minutes") val limitMinutes: Int = 90,
    val message: String = "",
    @Json(name = "consecutive_days") val consecutiveDays: Int = 0,
    @Json(name = "should_show_reality_nudge") val shouldShowRealityNudge: Boolean = false,
    @Json(name = "nudge_message") val nudgeMessage: String = ""
)

// ── 온보딩 첫 인사 모델 (26차 스프린트) ──────────────────────────────────────

@JsonClass(generateAdapter = false)
data class GreetingResponse(
    val greeting: String,
    @Json(name = "character_mbti") val characterMbti: String,
    val emotion: String? = null
)
