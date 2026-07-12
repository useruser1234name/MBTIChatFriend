package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.RedeemRequest
import com.example.mbtichatfriend.data.repository.AnalyticsEvent
import com.example.mbtichatfriend.data.repository.AnalyticsRepository
import com.example.mbtichatfriend.model.AgeGroup
import com.example.mbtichatfriend.model.Gender
import com.example.mbtichatfriend.model.MbtiType
import com.example.mbtichatfriend.model.PresetCharacter
import com.example.mbtichatfriend.model.Relationship
import com.example.mbtichatfriend.model.SpeechStyle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val prefs: UserPreferences,
    private val chatApi: ChatApi,
    private val analyticsRepository: AnalyticsRepository,
) : ViewModel() {

    val isOnboardingCompleted: Flow<Boolean> = prefs.isOnboardingCompleted

    var nickname by mutableStateOf("")
        private set
    var gender by mutableStateOf(Gender.MALE)
        private set
    var ageGroup by mutableStateOf(AgeGroup.TWENTIES)
        private set
    var partnerMbti by mutableStateOf(MbtiType.ENFP)
        private set
    var speechStyle by mutableStateOf(SpeechStyle.CASUAL)
        private set
    var relationship by mutableStateOf(Relationship.FRIEND)
        private set

    // 3단계 온보딩 통합 — 캐릭터 추천 단계에서 선택된 캐릭터
    var selectedCharacter by mutableStateOf<PresetCharacter?>(null)
        private set

    val nicknameError: String?
        get() = when {
            nickname.isBlank() -> null // 아직 입력 전
            nickname.length < 2 -> "2자 이상 입력해주세요"
            nickname.length > 8 -> "8자 이하로 입력해주세요"
            else -> null
        }

    val isNicknameValid: Boolean
        get() = nickname.length in 2..8

    fun updateNickname(value: String) {
        if (value.length <= 8) nickname = value
    }

    fun updateGender(value: Gender) {
        gender = value
    }

    fun updateAgeGroup(value: AgeGroup) {
        ageGroup = value
    }

    fun updatePartnerMbti(value: MbtiType) {
        partnerMbti = value
    }

    fun updateSpeechStyle(value: SpeechStyle) {
        speechStyle = value
    }

    fun updateRelationship(value: Relationship) {
        relationship = value
    }

    fun updateSelectedCharacter(value: PresetCharacter) {
        selectedCharacter = value
        // 선택된 캐릭터의 말투와 관계를 자동으로 반영
        runCatching { SpeechStyle.valueOf(value.speechStyle) }.getOrNull()
            ?.let { speechStyle = it }
        runCatching { Relationship.valueOf(value.relationship) }.getOrNull()
            ?.let { relationship = it }
    }

    // ── 분석 이벤트 (PM 로드맵 A1) ────────────────────────────────────────────

    /**
     * 온보딩 단계 진입 시 호출. stepIndex 0~4 (Nickname=0, Gender=1, Age=2, Mbti=3, StyleSelect=4).
     * 캐릭터 선택 완료 단계(4)는 [trackCharacterSelected]로 character_id를 포함해 별도 호출.
     */
    fun trackStep(stepIndex: Int) {
        analyticsRepository.track(
            scope = viewModelScope,
            eventType = AnalyticsEvent.ONBOARDING_STEP,
            payload = mapOf("step_index" to stepIndex),
        )
    }

    /**
     * 온보딩 캐릭터 선택 완료 시 호출 (stepIndex=4).
     * character_id(=mbti 코드)와 step_index를 payload에 포함한다.
     */
    fun trackCharacterSelected(character: PresetCharacter) {
        analyticsRepository.track(
            scope = viewModelScope,
            eventType = AnalyticsEvent.ONBOARDING_STEP,
            characterId = character.mbti,
            payload = mapOf(
                "step_index" to 4,
                "character_id" to character.mbti,
            ),
        )
    }

    fun saveOnboarding(onComplete: () -> Unit) {
        viewModelScope.launch {
            prefs.saveOnboardingData(
                nickname = nickname,
                gender = gender.name,
                ageGroup = ageGroup.name,
                partnerMbti = partnerMbti.name,
                speechStyle = speechStyle.name,
                relationship = relationship.name
            )
            analyticsRepository.track(
                scope = viewModelScope,
                eventType = AnalyticsEvent.ONBOARDING_COMPLETE,
                characterId = selectedCharacter?.mbti ?: partnerMbti.name,
                payload = mapOf("character_id" to (selectedCharacter?.mbti ?: partnerMbti.name)),
            )
            onComplete()
        }
    }

    // ── 레퍼럴 코드 적용 (17차 스프린트) ──────────────────────────────────────
    // A8: 서버(/api/v1/referral/redeem)는 RedeemRequest({"code": ...})만 인식(uid는 인증 토큰에서 추출).
    fun redeemReferral(code: String, callback: (Boolean, String?) -> Unit) {
        viewModelScope.launch {
            try {
                val response = chatApi.redeemReferral(
                    RedeemRequest(code = code)
                )
                if (response.isSuccessful && response.body()?.success == true) {
                    callback(true, null)
                } else {
                    val errorMsg = response.body()?.message?.takeIf { it.isNotEmpty() }
                        ?: "코드를 확인해 주세요."
                    callback(false, errorMsg)
                }
            } catch (e: Exception) {
                callback(false, e.message ?: "코드 적용 실패")
            }
        }
    }
}
