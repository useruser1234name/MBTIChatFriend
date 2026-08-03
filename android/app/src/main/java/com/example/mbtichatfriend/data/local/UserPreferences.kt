package com.example.mbtichatfriend.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
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
        val OPEN_BETA_BANNER_DISMISSED = booleanPreferencesKey("open_beta_banner_dismissed")
        val DAU_10K_BANNER_DISMISSED = booleanPreferencesKey("dau_10k_milestone_shown")
        val COMMUNITY_GUIDELINE_SHOWN = booleanPreferencesKey("community_guideline_shown")
        val LORA8_BANNER_SHOWN = booleanPreferencesKey("lora8_banner_shown")
        val LORA9_BANNER_SHOWN = booleanPreferencesKey("lora9_banner_shown")
        // 33차 스프린트: ESFP 10종 완성
        val LORA10_BANNER_SHOWN = booleanPreferencesKey("lora10_banner_shown")
        // 34차 스프린트: ENTJ 11종, ISTJ 12종 완성
        val LORA11_BANNER_SHOWN = booleanPreferencesKey("lora11_banner_shown")
        val LORA12_BANNER_SHOWN = booleanPreferencesKey("lora12_banner_shown")
        // 35차 스프린트: ESTP 13종 완성
        val LORA13_BANNER_SHOWN = booleanPreferencesKey("lora13_banner_shown")
        // 36차 스프린트: ENFJ 14종 완성, 언어 코드
        val LORA14_BANNER_SHOWN = booleanPreferencesKey("lora14_banner_shown")
        val LANGUAGE_CODE = stringPreferencesKey("language_code")
        // 37차 스프린트: 16종 전체 완성
        val ALL_MBTI_BANNER_SHOWN = booleanPreferencesKey("all_mbti_banner_shown")
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

    // ── R1: 선톡(캐릭터가 먼저 말 걸기) 상태 ─────────────────────────────────
    // 서버가 chat done/REST 응답으로 내려주는 next_hook과 마지막 대화 시각을
    // 캐릭터별로 보관한다. Room 스키마 변경 없이 프로세스 재시작에도 유지되도록
    // expr_task_$characterId와 동일한 "동적 키" DataStore 패턴을 따른다.
    private fun nextHookKey(characterId: Long) = stringPreferencesKey("next_hook_$characterId")
    private fun usedNextHookKey(characterId: Long) = stringPreferencesKey("next_hook_used_$characterId")
    private fun lastChatAtKey(characterId: Long) = longPreferencesKey("last_chat_at_$characterId")

    suspend fun setNextHook(characterId: Long, hook: String) {
        context.dataStore.edit { prefs -> prefs[nextHookKey(characterId)] = hook }
    }

    suspend fun getNextHook(characterId: Long): String =
        context.dataStore.data.map { prefs -> prefs[nextHookKey(characterId)] ?: "" }.first()

    /**
     * 선톡으로 소비한 훅을 기록하고 보관 훅을 제거한다.
     * 소비 기록을 영속화하는 이유: 서버가 같은 next_hook을 다시 내려주더라도
     * 동일한 훅으로 두 번 선톡하지 않기 위함(1회성 보장).
     */
    suspend fun consumeNextHook(characterId: Long, hook: String) {
        context.dataStore.edit { prefs ->
            prefs[usedNextHookKey(characterId)] = hook
            prefs.remove(nextHookKey(characterId))
        }
    }

    suspend fun getUsedNextHook(characterId: Long): String =
        context.dataStore.data.map { prefs -> prefs[usedNextHookKey(characterId)] ?: "" }.first()

    suspend fun setLastChatAt(characterId: Long, epochMs: Long) {
        context.dataStore.edit { prefs -> prefs[lastChatAtKey(characterId)] = epochMs }
    }

    suspend fun getLastChatAt(characterId: Long): Long =
        context.dataStore.data.map { prefs -> prefs[lastChatAtKey(characterId)] ?: 0L }.first()

    val isOpenBetaBannerDismissed: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.OPEN_BETA_BANNER_DISMISSED] ?: false
    }

    suspend fun setOpenBetaBannerDismissed(dismissed: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.OPEN_BETA_BANNER_DISMISSED] = dismissed
        }
    }

    val isDau10kBannerDismissed: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.DAU_10K_BANNER_DISMISSED] ?: false
    }

    suspend fun setDau10kBannerDismissed(dismissed: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.DAU_10K_BANNER_DISMISSED] = dismissed
        }
    }

    val isCommunityGuidelineShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.COMMUNITY_GUIDELINE_SHOWN] ?: false
    }

    suspend fun setCommunityGuidelineShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.COMMUNITY_GUIDELINE_SHOWN] = shown
        }
    }

    val isLora8BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA8_BANNER_SHOWN] ?: false
    }

    suspend fun setLora8BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA8_BANNER_SHOWN] = shown
        }
    }

    val isLora9BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA9_BANNER_SHOWN] ?: false
    }

    suspend fun setLora9BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA9_BANNER_SHOWN] = shown
        }
    }

    // ── 33차: ESFP 10종 완성 배너 ────────────────────────────────────────────
    val isLora10BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA10_BANNER_SHOWN] ?: false
    }

    suspend fun setLora10BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA10_BANNER_SHOWN] = shown
        }
    }

    // ── 34차: ENTJ 11종, ISTJ 12종 완성 배너 ─────────────────────────────────
    val isLora11BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA11_BANNER_SHOWN] ?: false
    }

    suspend fun setLora11BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA11_BANNER_SHOWN] = shown
        }
    }

    val isLora12BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA12_BANNER_SHOWN] ?: false
    }

    suspend fun setLora12BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA12_BANNER_SHOWN] = shown
        }
    }

    // ── 35차: ESTP 13종 완성 배너 ────────────────────────────────────────────
    val isLora13BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA13_BANNER_SHOWN] ?: false
    }

    suspend fun setLora13BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA13_BANNER_SHOWN] = shown
        }
    }

    // ── 36차: ENFJ 14종 완성 배너, 언어 설정 ─────────────────────────────────
    val isLora14BannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.LORA14_BANNER_SHOWN] ?: false
    }

    suspend fun setLora14BannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LORA14_BANNER_SHOWN] = shown
        }
    }

    val languageCode: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.LANGUAGE_CODE] ?: "ko"
    }

    suspend fun setLanguageCode(code: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.LANGUAGE_CODE] = code
        }
    }

    // ── 37차: 16종 전체 완성 배너 ────────────────────────────────────────────
    val isAllMbtiBannerShown: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.ALL_MBTI_BANNER_SHOWN] ?: false
    }

    suspend fun setAllMbtiBannerShown(shown: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.ALL_MBTI_BANNER_SHOWN] = shown
        }
    }

    suspend fun clearAll() {
        context.dataStore.edit { it.clear() }
    }
}
