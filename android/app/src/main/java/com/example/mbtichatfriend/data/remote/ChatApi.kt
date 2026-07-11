package com.example.mbtichatfriend.data.remote

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

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

    @POST("api/v1/session-feedback")
    suspend fun submitSessionFeedback(@Body req: SessionFeedbackRequest): Response<Unit>

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
}
