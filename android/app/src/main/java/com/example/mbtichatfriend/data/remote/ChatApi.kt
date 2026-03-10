package com.example.mbtichatfriend.data.remote

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

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
}
