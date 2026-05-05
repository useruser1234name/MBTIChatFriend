package com.example.mbtichatfriend.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
import com.example.mbtichatfriend.data.remote.ReferralLinkResponse
import com.example.mbtichatfriend.data.remote.ReferralStatsResponse
import com.example.mbtichatfriend.data.repository.AuthRepository
import com.example.mbtichatfriend.data.repository.CharacterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val prefs: UserPreferences,
    private val characterRepo: CharacterRepository,
    private val authRepository: AuthRepository,
    private val chatApi: ChatApi,
    private val remoteConfigManager: RemoteConfigManager,
) : ViewModel() {

    val nickname = prefs.nickname
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val darkMode = prefs.darkMode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "system")

    val authProvider = prefs.authProvider
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "none")

    private val _linkError = MutableStateFlow<String?>(null)
    val linkError: StateFlow<String?> = _linkError.asStateFlow()

    // ── 레퍼럴 V2 (27차 스프린트) ─────────────────────────────────────────────
    private val _referralCode = MutableStateFlow("")
    val referralCode: StateFlow<String> = _referralCode.asStateFlow()

    private val _referralStats = MutableStateFlow<ReferralStatsResponse?>(null)
    val referralStats: StateFlow<ReferralStatsResponse?> = _referralStats.asStateFlow()

    // ── 레퍼럴 V3 딥링크 (29차 스프린트) ─────────────────────────────────────
    private val _referralDeepLink = MutableStateFlow<ReferralLinkResponse?>(null)
    val referralDeepLink: StateFlow<ReferralLinkResponse?> = _referralDeepLink.asStateFlow()

    // ── 레퍼럴 CTA A/B 테스트 (30차 스프린트) ────────────────────────────────
    val referralCtaText: String
        get() {
            val abVariant = remoteConfigManager.getString("ab_variant")
            return if (abVariant == "referral_cta_v1_b") {
                "친구에게 7일 무료 선물하기"
            } else {
                "친구 초대하기"
            }
        }

    init {
        loadReferralData()
    }

    private fun loadReferralData() {
        viewModelScope.launch {
            // referral code = firebase uid의 앞 8자리를 대문자로 사용 (서버 측 동일 로직)
            val uid = prefs.firebaseUid.first()
            if (uid.isNotEmpty()) {
                _referralCode.value = uid.take(8).uppercase()
            }
            runCatching {
                val stats = chatApi.getReferralStats()
                _referralStats.value = stats
            }.onFailure { e ->
                android.util.Log.w("SettingsViewModel", "Failed to load referral stats", e)
            }
        }
    }

    /** 레퍼럴 V3: 딥링크 URL 생성 후 결과를 [referralDeepLink]에 노출 */
    fun generateReferralLink(onSuccess: (String) -> Unit) {
        viewModelScope.launch {
            runCatching {
                val result = chatApi.generateReferralLink()
                _referralDeepLink.value = result
                onSuccess(result.referralLink)
            }.onFailure { e ->
                android.util.Log.w("SettingsViewModel", "레퍼럴 V3 링크 생성 실패", e)
                // 폴백: 기존 코드 기반 텍스트 공유
                val code = _referralCode.value
                val fallbackText = if (code.isNotEmpty()) {
                    "MBTIChatFriend에서 나의 MBTI 친구를 만나보세요! 초대 코드: $code"
                } else {
                    "MBTIChatFriend에서 나의 MBTI 친구를 만나보세요!"
                }
                onSuccess(fallbackText)
            }
        }
    }

    fun updateNickname(newNickname: String) {
        if (newNickname.length in 2..8) {
            viewModelScope.launch {
                prefs.updateNickname(newNickname)
            }
        }
    }

    fun updateDarkMode(mode: String) {
        viewModelScope.launch {
            prefs.updateDarkMode(mode)
        }
    }

    fun linkGoogleAccount(activityContext: Context) {
        viewModelScope.launch {
            val result = authRepository.linkGoogleAccount(activityContext)
            result.onFailure { e ->
                _linkError.value = e.localizedMessage ?: "Google 연동 실패"
            }
        }
    }

    fun clearLinkError() {
        _linkError.value = null
    }

    fun logout(onDone: () -> Unit) {
        viewModelScope.launch {
            authRepository.signOut()
            prefs.clearAll()
            onDone()
        }
    }
}
