package com.example.mbtichatfriend.data.remote

import android.util.Log
import com.example.mbtichatfriend.R
import com.example.mbtichatfriend.data.MessageConstraints
import com.google.firebase.remoteconfig.FirebaseRemoteConfig
import com.google.firebase.remoteconfig.remoteConfigSettings
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RemoteConfigManager @Inject constructor(
    private val chatApi: ChatApi,
) {

    @Volatile
    private var serverConfig: ClientConfigApiResponse? = null

    private val remoteConfig: FirebaseRemoteConfig? = try {
        FirebaseRemoteConfig.getInstance()
    } catch (e: Exception) {
        Log.w(TAG, "RemoteConfig not available: ${e.message}")
        null
    }

    val isAvailable: Boolean get() = remoteConfig != null

    suspend fun init() {
        val config = remoteConfig
        if (config != null) {
            try {
                val configSettings = remoteConfigSettings {
                    minimumFetchIntervalInSeconds = 3600 // 1시간
                }
                config.setConfigSettingsAsync(configSettings).await()
                config.setDefaultsAsync(R.xml.remote_config_defaults).await()
                config.fetchAndActivate().await()
                Log.d(TAG, "RemoteConfig initialized successfully")
            } catch (e: Exception) {
                Log.w(TAG, "RemoteConfig init failed, using defaults: ${e.message}")
            }
        }

        try {
            serverConfig = chatApi.getClientConfig()
            Log.d(TAG, "Server client config loaded successfully")
        } catch (e: Exception) {
            Log.w(TAG, "Server client config load failed, using local defaults: ${e.message}")
        }
    }

    fun getString(key: String): String {
        return remoteConfig?.getString(key) ?: getDefaultString(key)
    }

    fun getBoolean(key: String): Boolean {
        return remoteConfig?.getBoolean(key) ?: getDefaultBoolean(key)
    }

    fun getLong(key: String): Long {
        val baseValue = remoteConfig?.getLong(key) ?: getDefaultLong(key)
        return when (key) {
            KEY_MAX_MESSAGE_LENGTH -> {
                val serverMax = serverConfig?.maxMessageLength?.toLong()
                    ?: MessageConstraints.MAX_MESSAGE_LENGTH.toLong()
                minOf(baseValue, serverMax)
            }
            KEY_MAX_CONVERSATION_HISTORY -> {
                val serverMax = serverConfig?.maxConversationHistory?.toLong()
                if (serverMax != null && serverMax > 0) minOf(baseValue, serverMax) else baseValue
            }
            else -> baseValue
        }
    }

    private fun getDefaultString(key: String): String = ""

    private fun getDefaultBoolean(key: String): Boolean = when (key) {
        KEY_FEATURE_SSE_ENABLED -> true
        KEY_FEATURE_GOOGLE_SIGNIN -> true
        KEY_FEATURE_PUSH_NOTIFICATION -> true
        KEY_MBTI_COMPATIBILITY_ENABLED -> true
        else -> false
    }

    private fun getDefaultLong(key: String): Long = when (key) {
        KEY_MAX_MESSAGE_LENGTH -> MessageConstraints.MAX_MESSAGE_LENGTH.toLong()
        KEY_MAX_CONVERSATION_HISTORY -> 20L
        KEY_AFFINITY_MAX_DELTA -> 5L
        else -> 0L
    }

    companion object {
        private const val TAG = "RemoteConfigManager"

        const val KEY_MAX_MESSAGE_LENGTH = "max_message_length"
        const val KEY_MAX_CONVERSATION_HISTORY = "max_conversation_history"
        const val KEY_FEATURE_SSE_ENABLED = "feature_sse_enabled"
        const val KEY_FEATURE_GOOGLE_SIGNIN = "feature_google_signin"
        const val KEY_FEATURE_PUSH_NOTIFICATION = "feature_push_notification"
        const val KEY_MBTI_COMPATIBILITY_ENABLED = "mbti_compatibility_enabled"
        const val KEY_AFFINITY_MAX_DELTA = "affinity_max_delta"
    }
}
