package com.example.mbtichatfriend.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "user_prefs")

@Singleton
class UserPreferences @Inject constructor(
    @ApplicationContext private val context: Context
) {
    // EncryptedSharedPreferences - 민감 정보 (UID, FCM 토큰) 전용
    private val encryptedPrefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "secure_user_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

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
        val AUTH_PROVIDER = stringPreferencesKey("auth_provider") // "anonymous", "google", "none"
        val FCM_TOKEN_SYNCED = booleanPreferencesKey("fcm_token_synced")
        val TODAY_MOOD = stringPreferencesKey("today_mood")
        val MOOD_CHECK_DATE = stringPreferencesKey("mood_check_date")
    }

    // EncryptedSharedPreferences 키 상수
    private object SecureKeys {
        const val FIREBASE_UID = "secure_firebase_uid"
        const val FCM_TOKEN = "secure_fcm_token"
    }

    // ---- EncryptedSharedPreferences 기반 민감 데이터 ----

    private val _firebaseUid = MutableStateFlow(encryptedPrefs.getString(SecureKeys.FIREBASE_UID, "") ?: "")
    val firebaseUid: Flow<String> = _firebaseUid.asStateFlow()

    private val _fcmToken = MutableStateFlow(encryptedPrefs.getString(SecureKeys.FCM_TOKEN, "") ?: "")
    val fcmToken: Flow<String> = _fcmToken.asStateFlow()

    fun updateFirebaseUidSync(uid: String) {
        encryptedPrefs.edit().putString(SecureKeys.FIREBASE_UID, uid).apply()
        _firebaseUid.value = uid
    }

    fun updateFcmTokenSync(token: String) {
        encryptedPrefs.edit().putString(SecureKeys.FCM_TOKEN, token).apply()
        _fcmToken.value = token
    }

    // ---- DataStore 기반 일반 데이터 ----

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

    val authProvider: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.AUTH_PROVIDER] ?: "none"
    }

    val fcmTokenSynced: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.FCM_TOKEN_SYNCED] ?: false
    }

    val todayMood: Flow<String?> = context.dataStore.data.map { prefs ->
        val checkDate = prefs[Keys.MOOD_CHECK_DATE] ?: ""
        val today = java.time.LocalDate.now().toString()
        if (checkDate == today) prefs[Keys.TODAY_MOOD] else null
    }

    suspend fun updateTodayMood(mood: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.TODAY_MOOD] = mood
            prefs[Keys.MOOD_CHECK_DATE] = java.time.LocalDate.now().toString()
        }
    }

    suspend fun updateFirebaseUid(uid: String) {
        updateFirebaseUidSync(uid)
        // 기존 DataStore에 저장된 uid 제거 (마이그레이션)
        context.dataStore.edit { prefs ->
            prefs.remove(stringPreferencesKey("firebase_uid"))
        }
    }

    suspend fun updateAuthProvider(provider: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.AUTH_PROVIDER] = provider
        }
    }

    suspend fun updateFcmToken(token: String) {
        updateFcmTokenSync(token)
        // 기존 DataStore에 저장된 fcm_token 제거 (마이그레이션)
        context.dataStore.edit { prefs ->
            prefs.remove(stringPreferencesKey("fcm_token"))
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
        encryptedPrefs.edit().clear().apply()
        _firebaseUid.value = ""
        _fcmToken.value = ""
    }
}
