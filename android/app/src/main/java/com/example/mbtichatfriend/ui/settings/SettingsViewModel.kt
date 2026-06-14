package com.example.mbtichatfriend.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.AppDatabase
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.RedeemRequest
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
    private val db: AppDatabase,
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

    // ── 초대 코드 입력 (Settings 진입점, A8 이후) ────────────────────────────
    sealed interface RedeemState {
        data object Idle : RedeemState
        data object Loading : RedeemState
        data class Success(val bonusDays: Int) : RedeemState
        data class Error(val message: String) : RedeemState
    }

    private val _redeemState = MutableStateFlow<RedeemState>(RedeemState.Idle)
    val redeemState: StateFlow<RedeemState> = _redeemState.asStateFlow()

    /** V3 endpoint `redeemReferral`(body: {"code": "..."}) 재사용. */
    fun redeemInviteCode(code: String) {
        val trimmed = code.trim()
        if (trimmed.isEmpty()) return
        viewModelScope.launch {
            _redeemState.value = RedeemState.Loading
            runCatching {
                chatApi.redeemReferral(RedeemRequest(code = trimmed))
            }.fold(
                onSuccess = { response ->
                    val body = response.body()
                    if (response.isSuccessful && body?.success == true) {
                        _redeemState.value = RedeemState.Success(body.bonusDays)
                    } else {
                        val msg = body?.message?.takeIf { it.isNotEmpty() }
                            ?: "코드를 확인해 주세요."
                        _redeemState.value = RedeemState.Error(msg)
                    }
                },
                onFailure = { e ->
                    _redeemState.value = RedeemState.Error(e.localizedMessage ?: "코드 적용 실패")
                }
            )
        }
    }

    fun clearRedeemState() {
        _redeemState.value = RedeemState.Idle
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

    // ── 계정 삭제 (A-8, S-6) ─────────────────────────────────────────────────

    sealed interface DeleteAccountState {
        data object Idle : DeleteAccountState
        data object Loading : DeleteAccountState
        data object Success : DeleteAccountState
        data class Error(val message: String) : DeleteAccountState
    }

    private val _deleteAccountState = MutableStateFlow<DeleteAccountState>(DeleteAccountState.Idle)
    val deleteAccountState: StateFlow<DeleteAccountState> = _deleteAccountState.asStateFlow()

    /**
     * 계정 삭제 플로우:
     *  1. DELETE /api/v1/account 서버 호출 (S-6 구현 중)
     *  2. 성공(2xx) 또는 서버 미구현(404/405) 시 로컬 데이터 전체 삭제
     *  3. authRepository.signOut() + prefs.clearAll()
     *
     * 서버가 아직 미구현인 경우에도 로컬 삭제는 진행한다(첫 릴리즈 안전장치).
     */
    fun deleteAccount(onSuccess: () -> Unit) {
        viewModelScope.launch {
            _deleteAccountState.value = DeleteAccountState.Loading
            runCatching {
                chatApi.deleteAccount()
            }.onFailure { e ->
                // 네트워크 오류는 중단
                _deleteAccountState.value = DeleteAccountState.Error(
                    e.localizedMessage ?: "계정 삭제 요청 실패"
                )
                return@launch
            }.onSuccess { response ->
                // S-6 미구현(404/405)이면 서버 삭제는 건너뛰고 로컬만 삭제
                if (!response.isSuccessful && response.code() !in listOf(404, 405)) {
                    _deleteAccountState.value = DeleteAccountState.Error(
                        "서버 오류(${response.code()}). 잠시 후 다시 시도해 주세요."
                    )
                    return@launch
                }
            }
            // Room 전체 삭제
            runCatching {
                db.messageDao().deleteAll()
                db.characterDao().deleteAll()
                db.diaryDao().deleteAll()
                db.memoryDao().deleteAll()
                db.feedbackDao().deleteAll()
            }
            authRepository.signOut()
            prefs.clearAll()
            _deleteAccountState.value = DeleteAccountState.Success
            onSuccess()
        }
    }

    fun clearDeleteAccountState() {
        _deleteAccountState.value = DeleteAccountState.Idle
    }
}
