package com.example.mbtichatfriend.data.remote

import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import java.util.concurrent.Executors
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val authManager: FirebaseAuthManager
) : Interceptor {

    // 캐시된 토큰 (Firebase 토큰은 1시간 유효)
    @Volatile
    private var cachedToken: String? = null

    @Volatile
    private var tokenExpiry: Long = 0L

    // OkHttp 스레드풀과 격리된 전용 디스패처 (데드락 방지)
    private val tokenDispatcher = Executors.newSingleThreadExecutor { r ->
        Thread(r, "auth-token-refresh").apply { isDaemon = true }
    }.asCoroutineDispatcher()

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()

        val token = getCachedOrFreshToken()

        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }

        return chain.proceed(request)
    }

    private fun getCachedOrFreshToken(): String? {
        // 캐시된 토큰이 아직 유효하면 재사용 (runBlocking 불필요)
        val now = System.currentTimeMillis()
        cachedToken?.let { token ->
            if (now < tokenExpiry - REFRESH_MARGIN_MS) {
                return token
            }
        }

        // 토큰 갱신: OkHttp 스레드풀과 격리된 전용 디스패처 사용
        return try {
            val token = runBlocking(tokenDispatcher) { authManager.getIdToken() }
            if (token != null) {
                cachedToken = token
                tokenExpiry = now + TOKEN_LIFETIME_MS
            }
            token
        } catch (e: Exception) {
            cachedToken = null
            tokenExpiry = 0L
            null
        }
    }

    fun invalidateToken() {
        cachedToken = null
        tokenExpiry = 0L
    }

    companion object {
        private const val TOKEN_LIFETIME_MS = 55 * 60 * 1000L // 55분 (1시간 유효, 5분 여유)
        private const val REFRESH_MARGIN_MS = 5 * 60 * 1000L  // 만료 5분 전 갱신
    }
}
