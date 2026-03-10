package com.example.mbtichatfriend.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "user_prefs")

@Singleton
class UserPreferences @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private object Keys {
        val ONBOARDING_COMPLETED = booleanPreferencesKey("onboarding_completed")
        val NICKNAME = stringPreferencesKey("nickname")
        val GENDER = stringPreferencesKey("gender")
        val AGE_GROUP = stringPreferencesKey("age_group")
        val PARTNER_MBTI = stringPreferencesKey("partner_mbti")
        val USER_MBTI = stringPreferencesKey("user_mbti")
        val SPEECH_STYLE = stringPreferencesKey("speech_style")
        val RELATIONSHIP = stringPreferencesKey("relationship")
        val DARK_MODE = stringPreferencesKey("dark_mode") // "system", "light", "dark"
        val FIREBASE_UID = stringPreferencesKey("firebase_uid")
        val AUTH_PROVIDER = stringPreferencesKey("auth_provider") // "anonymous", "google", "none"
        val FCM_TOKEN = stringPreferencesKey("fcm_token")
        val FCM_TOKEN_SYNCED = booleanPreferencesKey("fcm_token_synced")
        val OPENAI_API_KEY = stringPreferencesKey("openai_api_key")
    }

    val isOnboardingCompleted: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.ONBOARDING_COMPLETED] ?: false
    }

    val nickname: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.NICKNAME] ?: ""
    }

    val gender: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.GENDER] ?: "MALE"
    }

    val ageGroup: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.AGE_GROUP] ?: "TWENTIES"
    }

    val partnerMbti: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.PARTNER_MBTI] ?: "ENFP"
    }

    val userMbti: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.USER_MBTI] ?: ""
    }

    val speechStyle: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.SPEECH_STYLE] ?: "CASUAL"
    }

    val relationship: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.RELATIONSHIP] ?: "FRIEND"
    }

    val darkMode: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.DARK_MODE] ?: "system"
    }

    val firebaseUid: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.FIREBASE_UID] ?: ""
    }

    val authProvider: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.AUTH_PROVIDER] ?: "none"
    }

    val fcmToken: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.FCM_TOKEN] ?: ""
    }

    val fcmTokenSynced: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.FCM_TOKEN_SYNCED] ?: false
    }

    suspend fun updateFirebaseUid(uid: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.FIREBASE_UID] = uid
        }
    }

    suspend fun updateAuthProvider(provider: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.AUTH_PROVIDER] = provider
        }
    }

    suspend fun updateFcmToken(token: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.FCM_TOKEN] = token
            prefs[Keys.FCM_TOKEN_SYNCED] = false
        }
    }

    suspend fun markFcmTokenSynced() {
        context.dataStore.edit { prefs ->
            prefs[Keys.FCM_TOKEN_SYNCED] = true
        }
    }

    suspend fun updateNickname(nickname: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.NICKNAME] = nickname
        }
    }

    suspend fun updateDarkMode(mode: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.DARK_MODE] = mode
        }
    }

    suspend fun updateUserMbti(mbti: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.USER_MBTI] = mbti
        }
    }

    suspend fun saveOnboardingData(
        nickname: String,
        gender: String,
        ageGroup: String,
        partnerMbti: String,
        speechStyle: String,
        relationship: String,
        userMbti: String = ""
    ) {
        context.dataStore.edit { prefs ->
            prefs[Keys.NICKNAME] = nickname
            prefs[Keys.GENDER] = gender
            prefs[Keys.AGE_GROUP] = ageGroup
            prefs[Keys.PARTNER_MBTI] = partnerMbti
            prefs[Keys.SPEECH_STYLE] = speechStyle
            prefs[Keys.RELATIONSHIP] = relationship
            prefs[Keys.ONBOARDING_COMPLETED] = true
            if (userMbti.isNotEmpty()) {
                prefs[Keys.USER_MBTI] = userMbti
            }
        }
    }

    val openAiApiKey: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.OPENAI_API_KEY] ?: ""
    }

    suspend fun updateOpenAiApiKey(key: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.OPENAI_API_KEY] = key
        }
    }

    suspend fun setExpressionSetTaskId(characterId: Long, taskId: String) {
        context.dataStore.edit { prefs ->
            prefs[stringPreferencesKey("expr_task_$characterId")] = taskId
        }
    }

    suspend fun getExpressionSetTaskId(characterId: Long): String? {
        return context.dataStore.data.map { prefs ->
            prefs[stringPreferencesKey("expr_task_$characterId")]
        }.first()
    }

    suspend fun clearExpressionSetTaskId(characterId: Long) {
        context.dataStore.edit { prefs ->
            prefs.remove(stringPreferencesKey("expr_task_$characterId"))
        }
    }

    suspend fun clearAll() {
        context.dataStore.edit { it.clear() }
    }
}
