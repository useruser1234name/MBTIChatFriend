# ====== 디버깅용 라인 번호 보존 ======
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ====== Retrofit + Moshi ======
# API 인터페이스 보존
-keep interface com.example.mbtichatfriend.data.remote.ChatApi { *; }
# Moshi JSON 직렬화 대상 data class만 보존 (패키지 전체 아님)
-keep class com.example.mbtichatfriend.data.remote.ChatRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.ChatResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.ReplyPart { *; }
-keep class com.example.mbtichatfriend.data.remote.FcmTokenRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.DiaryRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.DiaryResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.MemoryItem { *; }
-keep class com.example.mbtichatfriend.data.remote.MemoryExtractRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.MemoryExtractResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.MemoryListApiResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.FinetuneStartRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.FinetuneStartResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.FinetuneStatusResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.FinetuneActivateRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.ImageGenerateRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.ImageGenerateResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.ImageSetRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.ImageSetResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.ImageSetStatusResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.FeedbackRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.SessionStartRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.SessionStartResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.MoodCheckinApiRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.MoodCheckinApiResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.CompatibilityApiRequest { *; }
-keep class com.example.mbtichatfriend.data.remote.CompatibilityApiResponse { *; }
-keep class com.example.mbtichatfriend.data.remote.DeleteConversationRequest { *; }
-keep class com.example.mbtichatfriend.model.** { *; }

# Moshi
-keepclassmembers class * {
    @com.squareup.moshi.Json <fields>;
}
-keep class com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

# ====== Room ======
-keep class com.example.mbtichatfriend.data.local.*Entity { *; }
-keep class com.example.mbtichatfriend.data.local.*Dao { *; }

# ====== Firebase ======
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# ====== OkHttp ======
-dontwarn okhttp3.**
-dontwarn okio.**

# ====== Hilt ======
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep @dagger.hilt.android.lifecycle.HiltViewModel class * { *; }

# ====== Compose ======
-dontwarn androidx.compose.**

# ====== Lottie ======
-dontwarn com.airbnb.lottie.**

# ====== Credentials / Google Identity ======
-keep class com.google.android.libraries.identity.** { *; }
-dontwarn com.google.android.libraries.identity.**
