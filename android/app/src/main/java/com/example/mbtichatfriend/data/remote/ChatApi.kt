package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

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
    val memories: List<MemoryItem> = emptyList()
)

@JsonClass(generateAdapter = false)
data class ChatResponse(
    val replies: List<ReplyPart>,
    @Json(name = "affinity_delta") val affinityDelta: Int = 0
)

@JsonClass(generateAdapter = false)
data class ReplyPart(
    val text: String,
    val emotion: String = "NEUTRAL",
    val delay: Long = 500
)

@JsonClass(generateAdapter = false)
data class FcmTokenRequest(
    val token: String,
    @Json(name = "user_id") val userId: String = ""
)

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

@JsonClass(generateAdapter = false)
data class FeedbackRequest(
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "message_id") val messageId: String,
    @Json(name = "feedback_type") val feedbackType: String,
    @Json(name = "feedback_detail") val feedbackDetail: String = ""
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

// ── Play Billing 결제 검증 모델 ──────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class PurchaseVerifyRequest(
    @Json(name = "user_id") val userId: String,
    @Json(name = "purchase_token") val purchaseToken: String,
    @Json(name = "order_id") val orderId: String,
    @Json(name = "product_id") val productId: String,
)

@JsonClass(generateAdapter = false)
data class PurchaseVerifyResponse(
    val success: Boolean,
    val plan: String,
    @Json(name = "user_id") val userId: String,
)

// ── 편지 모델 ────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class LetterResponse(
    @Json(name = "has_letter") val has_letter: Boolean,
    @Json(name = "content") val content: String,
    @Json(name = "generated_date") val generated_date: String,
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

interface ChatApi {
    @POST("api/v1/chat/send")
    suspend fun chat(@Body req: ChatRequest): ChatResponse

    @POST("api/v1/fcm/register")
    suspend fun registerFcmToken(@Body req: FcmTokenRequest): Response<Unit>

    @POST("api/v1/diary/generate")
    suspend fun generateDiary(@Body req: DiaryRequest): DiaryResponse

    @POST("api/v1/memory/extract")
    suspend fun extractMemories(@Body req: MemoryExtractRequest): MemoryExtractResponse

    @POST("api/v1/finetune/start")
    suspend fun startFinetune(@Body req: FinetuneStartRequest): FinetuneStartResponse

    @GET("api/v1/finetune/status/{jobId}")
    suspend fun getFinetuneStatus(@Path("jobId") jobId: String): FinetuneStatusResponse

    @POST("api/v1/finetune/activate")
    suspend fun activateFinetune(@Body req: FinetuneActivateRequest): Response<Unit>

    @POST("api/v1/image/generate")
    suspend fun generateImage(@Body req: ImageGenerateRequest): ImageGenerateResponse

    @POST("api/v1/image/generate-set")
    suspend fun generateImageSet(@Body req: ImageSetRequest): ImageSetResponse

    @GET("api/v1/image/set-status/{taskId}")
    suspend fun getImageSetStatus(@Path("taskId") taskId: String): ImageSetStatusResponse

    @POST("api/v1/feedback/submit")
    suspend fun submitFeedback(@Body req: FeedbackRequest): Response<Unit>

    @POST("api/v1/session/check")
    suspend fun checkSession(@Body req: SessionCheckRequest): SessionCheckResponse

    // ── 관계 히스토리 & 기억 앨범 (UX-B 안현우 + UI-C 정수아, 5차 회의 합의) ──

    @GET("api/v1/relationship/{roomId}/summary")
    suspend fun getRelationshipSummary(
        @Path("roomId") roomId: String,
        @retrofit2.http.Query("character_id") characterId: String = ""
    ): RelationshipSummaryResponse

    @POST("api/v1/relationship/{roomId}/memory")
    suspend fun saveMemoryMoment(
        @Path("roomId") roomId: String,
        @Body request: MemoryMomentRequest
    ): Response<Unit>

    @GET("api/v1/relationship/{roomId}/album")
    suspend fun getMemoryAlbum(
        @Path("roomId") roomId: String,
        @retrofit2.http.Query("character_id") characterId: String = ""
    ): MemoryAlbumResponse

    @POST("api/v1/billing/verify-purchase")
    suspend fun verifyPurchase(@Body req: PurchaseVerifyRequest): PurchaseVerifyResponse

    // ── 분석 이벤트 로깅 (PM 로드맵 — 최소 계측) ──────────────────────────────

    @POST("api/v1/events/batch")
    suspend fun logEvents(@Body batch: EventBatchRequest): Response<EventBatchResponse>

    // ── 편지 ─────────────────────────────────────────────────────────────────

    @GET("api/v1/letter/latest")
    suspend fun getLatestLetter(
        @Query("room_id") roomId: String,
        @Query("character_id") characterId: String,
    ): LetterResponse

    // ── 레퍼럴 (17차 스프린트) ───────────────────────────────────────────────

    @POST("api/v1/referral/redeem")
    suspend fun redeemReferralCode(@Body req: ReferralRedeemRequest): Response<ReferralRedeemResponse>

    // ── 커뮤니티 (19차 스프린트) ─────────────────────────────────────────────

    @GET("api/v1/community/posts")
    suspend fun getCommunityPosts(@Query("mbti") mbti: String? = null): Response<List<CommunityPost>>

    @POST("api/v1/community/posts")
    suspend fun createPost(@Body body: CreatePostRequest): Response<CommunityPost>

    @POST("api/v1/community/posts/{postId}/empathy")
    suspend fun toggleEmpathy(
        @Path("postId") postId: Long,
        @Body body: EmpathyToggleRequest,
    ): Response<EmpathyToggleResponse>

    @GET("api/v1/community/posts/{postId}/comments")
    suspend fun getComments(@Path("postId") postId: Long): Response<List<CommunityComment>>

    @POST("api/v1/community/posts/{postId}/comments")
    suspend fun createComment(
        @Path("postId") postId: Long,
        @Body body: CreateCommentRequest,
    ): Response<CommunityComment>

    // ── 궁합 (21차 스프린트) ──────────────────────────────────────────────────

    @GET("api/v1/compatibility/{mbtiA}/{mbtiB}")
    suspend fun getCompatibility(
        @Path("mbtiA") mbtiA: String,
        @Path("mbtiB") mbtiB: String,
    ): Response<CompatibilityResult>

    // ── 알림 (21차 스프린트) ──────────────────────────────────────────────────

    @GET("api/v1/notifications/{userId}")
    suspend fun getNotifications(@Path("userId") userId: String): Response<List<AppNotification>>

    @GET("api/v1/notifications/{userId}/unread-count")
    suspend fun getUnreadCount(@Path("userId") userId: String): Response<UnreadCountResponse>

    @POST("api/v1/notifications/{userId}/mark-read")
    suspend fun markAllRead(@Path("userId") userId: String): Response<Unit>

    // ── 트렌딩 게시글 (22차 스프린트) ────────────────────────────────────────

    @GET("api/v1/community/posts/trending")
    suspend fun getTrendingPosts(@Query("limit") limit: Int = 3): List<TrendingPostUi>

    // ── 연말 대화 리포트 (22차 스프린트) ─────────────────────────────────────

    @GET("api/v1/report/year/{userId}")
    suspend fun getYearReport(@Path("userId") userId: String): YearReportResponse

    // ── 발렌타인 궁합 특집 (24차 스프린트) ───────────────────────────────────

    @GET("api/v1/compatibility/valentine/{mbti}")
    suspend fun getValentineMessage(@Path("mbti") mbti: String): ValentineMessage

    // ── 커뮤니티 신고 (25차 스프린트) ────────────────────────────────────────

    @POST("api/v1/community/posts/{postId}/report")
    suspend fun reportPost(
        @Path("postId") postId: Long,
        @Body request: ReportRequest,
    ): ReportResponse

    // ── 온보딩 첫 인사 (26차 스프린트) ───────────────────────────────────────

    @POST("api/v1/chat/greeting")
    suspend fun sendGreeting(@Body body: Map<String, String>): GreetingResponse

    // ── 가정의 달 감사 카드 (26차 스프린트) ──────────────────────────────────

    @GET("api/v1/compatibility/gratitude/{mbti}")
    suspend fun getGratitudeMessage(@Path("mbti") mbti: String): GratitudeMessage

    // ── 레퍼럴 V2 통계 (27차 스프린트) ───────────────────────────────────────
    @GET("api/v1/referral/stats")
    suspend fun getReferralStats(): ReferralStatsResponse

    // ── 레퍼럴 V3 딥링크 (29차 스프린트) ─────────────────────────────────────
    @POST("api/v1/referral/link")
    suspend fun generateReferralLink(): ReferralLinkResponse

    // 서버에는 /redeem 단일 엔드포인트만 존재(A4: {code} JSON body + 인증토큰 uid). redeem-v3는 서버에 없음.
    @POST("api/v1/referral/redeem")
    suspend fun redeemReferral(@Body req: RedeemRequest): Response<ReferralRedeemResponse>

    // ── 커뮤니티 고정 공지 (29차 스프린트) ───────────────────────────────────
    @GET("api/v1/community/posts/pinned")
    suspend fun getPinnedPosts(): List<CommunityPost>

    // ── 커뮤니티 이벤트 트렌딩 TOP5 (30차 스프린트) ───────────────────────────
    @GET("api/v1/community/posts/event-trending")
    suspend fun getEventTrendingPosts(): List<CommunityPost>

    // ── 다이어리 직접 입력 API (32차 스프린트) ────────────────────────────────
    @POST("api/v1/diary/entries")
    suspend fun createDiaryEntry(@Body request: DiaryEntryRequest): DiaryEntry

    @GET("api/v1/diary/entries")
    suspend fun getDiaryEntries(): List<DiaryEntry>

    @GET("api/v1/diary/weekly-report")
    suspend fun getDiaryWeeklyReport(): DiaryWeeklyReport

    // ── 여름 궁합 메시지 (35차 스프린트) ─────────────────────────────────────
    @GET("api/v1/compatibility/summer/{mbti}")
    suspend fun getSummerMessage(@Path("mbti") mbti: String): SummerMessageResponse

    // ── 16종 전체 완성 메시지 (37차 스프린트) ─────────────────────────────────
    @GET("api/v1/compatibility/all-complete/{mbti}")
    suspend fun getAllCompleteMessage(@Path("mbti") mbti: String): AllCompleteResponse

    // ── 계정 삭제 (S-6, 출시 게이트 A-8) ────────────────────────────────────
    @DELETE("api/v1/account")
    suspend fun deleteAccount(): Response<Unit>

    // ── 호감도 서버 미러링 (S-7 계약 확정) ──────────────────────────────────────
    // 서버: POST /api/v1/affinity/sync  body: {room_id, character_id, score, level}
    @POST("api/v1/affinity/sync")
    suspend fun syncAffinity(@Body req: AffinitySyncRequest): Response<AffinityResponse>

    // 서버: GET /api/v1/affinity/{room_id}  (path param, 재설치 복구용)
    @GET("api/v1/affinity/{room_id}")
    suspend fun restoreAffinity(@Path("room_id") roomId: String): Response<AffinityResponse>
}

// ── 레퍼럴 모델 ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralRedeemRequest(
    @Json(name = "code") val code: String,
    @Json(name = "user_id") val userId: String
)

@JsonClass(generateAdapter = false)
data class ReferralRedeemResponse(
    val success: Boolean,
    val message: String = "",
    @Json(name = "bonus_days") val bonusDays: Int = 0
)

// ── 레퍼럴 V2 통계 모델 (27차 스프린트) ──────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralStatsResponse(
    @Json(name = "invited_count") val invitedCount: Int = 0,
    @Json(name = "reward_days") val rewardDays: Int = 0
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

// ── 트렌딩 게시글 모델 (22차 스프린트) ───────────────────────────────────────

@JsonClass(generateAdapter = false)
data class TrendingPostUi(
    val id: Long,
    @Json(name = "mbti_type") val mbtiType: String,
    val content: String,
    @Json(name = "empathy_count") val empathyCount: Int,
    @Json(name = "comment_count") val commentCount: Int,
)

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

// ── 커뮤니티 신고 모델 (25차 스프린트) ───────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReportRequest(val reason: String)

@JsonClass(generateAdapter = false)
data class ReportResponse(val ok: Boolean)

// ── 온보딩 첫 인사 모델 (26차 스프린트) ──────────────────────────────────────

@JsonClass(generateAdapter = false)
data class GreetingResponse(
    val greeting: String,
    @Json(name = "character_mbti") val characterMbti: String
)

// ── 가정의 달 감사 카드 모델 (26차 스프린트) ──────────────────────────────────

@JsonClass(generateAdapter = false)
data class GratitudeMessage(
    val mbti: String,
    val message: String
)

// ── 레퍼럴 V3 딥링크 모델 (29차 스프린트) ────────────────────────────────────

@JsonClass(generateAdapter = false)
data class ReferralLinkResponse(
    @Json(name = "referral_link") val referralLink: String,
    @Json(name = "referral_code") val referralCode: String,
)

@JsonClass(generateAdapter = false)
data class RedeemRequest(
    @Json(name = "code") val code: String,
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

// ── 호감도 서버 미러링 모델 (S-7 계약 확정) ──────────────────────────────────
// 서버 스키마: POST /api/v1/affinity/sync (body: room_id, character_id, score, level)
//              GET  /api/v1/affinity/{room_id} (path param)
// AffinityResponse: {room_id, character_id, score, level}

@JsonClass(generateAdapter = false)
data class AffinitySyncRequest(
    @Json(name = "room_id") val roomId: String,
    @Json(name = "character_id") val characterId: String,
    @Json(name = "score") val score: Int,
    @Json(name = "level") val level: Int,
)

@JsonClass(generateAdapter = false)
data class AffinityResponse(
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "score") val score: Int = 0,
    @Json(name = "level") val level: Int = 1,
)
