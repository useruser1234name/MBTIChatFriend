package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.http.Body
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
    @Json(name = "persona_raw") val personaRaw: String = "",
    @Json(name = "persona_summary") val personaSummary: String = "",
    @Json(name = "dialogue_prompt") val dialoguePrompt: String = "",
    @Json(name = "visual_prompt") val visualPrompt: String = "",
    val memories: List<MemoryItem> = emptyList(),
    @Json(name = "room_id") val roomId: String = "",
    @Json(name = "end_of_session") val endOfSession: Boolean = false,
    @Json(name = "client_local_hour") val clientLocalHour: Int? = null,
    val mood: String? = null
)

@JsonClass(generateAdapter = false)
data class ChatResponse(
    val replies: List<ReplyPart>,
    @Json(name = "affinity_delta") val affinityDelta: Int = 0,
    @Json(name = "night_diary_generated") val nightDiaryGenerated: Boolean = false,
    @Json(name = "next_hook") val nextHook: String? = null,
    @Json(name = "next_goal") val nextGoal: String? = null
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

@JsonClass(generateAdapter = false)
data class SessionStartRequest(
    @Json(name = "character_id") val characterId: String,
    @Json(name = "current_affinity_score") val currentAffinityScore: Int,
    @Json(name = "current_affinity_level") val currentAffinityLevel: Int,
    @Json(name = "last_chat_iso") val lastChatIso: String? = null
)

@JsonClass(generateAdapter = false)
data class SessionStartResponse(
    @Json(name = "adjusted_score") val adjustedScore: Int = 0,
    @Json(name = "return_bonus") val returnBonus: Int = 0,
    @Json(name = "original_score") val originalScore: Int = 0,
    @Json(name = "days_inactive") val daysInactive: Int = 0
)

@JsonClass(generateAdapter = false)
data class MoodCheckinApiRequest(
    val mood: String,
    @Json(name = "character_id") val characterId: String = "",
    @Json(name = "character_name") val characterName: String = "",
    val mbti: String = "",
    val nickname: String = ""
)

@JsonClass(generateAdapter = false)
data class MoodCheckinApiResponse(
    val message: String,
    val emotion: String = "NEUTRAL"
)

@JsonClass(generateAdapter = false)
data class CompatibilityApiRequest(
    @Json(name = "user_mbti") val userMbti: String,
    @Json(name = "character_mbti") val characterMbti: String
)

@JsonClass(generateAdapter = false)
data class CompatibilityApiResponse(
    val score: Int,
    val description: String,
    val strengths: List<String> = emptyList(),
    val challenges: List<String> = emptyList()
)

@JsonClass(generateAdapter = false)
data class MemoryListApiResponse(
    val summary: String = "",
    val facts: List<Map<String, String>> = emptyList(),
    @Json(name = "total_conversations") val totalConversations: Int = 0
)

@JsonClass(generateAdapter = false)
data class ClientConfigApiResponse(
    @Json(name = "max_message_length") val maxMessageLength: Int = 0,
    @Json(name = "max_conversation_history") val maxConversationHistory: Int = 0
)

@JsonClass(generateAdapter = false)
data class DeleteConversationRequest(
    @Json(name = "character_id") val characterId: String,
    @Json(name = "character_name") val characterName: String = "",
    val nickname: String = ""
)

@JsonClass(generateAdapter = false)
data class DeleteConversationApiResponse(
    @Json(name = "deleted_count") val deletedCount: Int = 0,
    val status: String = "ok",
    @Json(name = "deleted_targets") val deletedTargets: List<String> = emptyList(),
    @Json(name = "cleanup_warnings") val cleanupWarnings: List<String> = emptyList()
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

    @POST("api/v1/session/start")
    suspend fun startSession(@Body req: SessionStartRequest): SessionStartResponse

    @POST("api/v1/mood/checkin")
    suspend fun moodCheckin(@Body req: MoodCheckinApiRequest): MoodCheckinApiResponse

    @POST("api/v1/compatibility/check")
    suspend fun checkCompatibility(@Body req: CompatibilityApiRequest): CompatibilityApiResponse

    @GET("api/v1/config/client")
    suspend fun getClientConfig(): ClientConfigApiResponse

    @GET("api/v1/memory/{characterName}/{nickname}")
    suspend fun getMemories(
        @Path("characterName") characterName: String,
        @Path("nickname") nickname: String,
        @Query("character_id") characterId: String = ""
    ): MemoryListApiResponse

    @POST("api/v1/data/delete-conversation")
    suspend fun deleteConversation(@Body req: DeleteConversationRequest): DeleteConversationApiResponse
}
