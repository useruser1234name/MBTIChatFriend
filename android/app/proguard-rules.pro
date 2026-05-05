# ====== 디버깅용 라인 번호 보존 ======
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ====== Retrofit + Moshi ======
-keep class com.example.mbtichatfriend.data.remote.** { *; }
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
