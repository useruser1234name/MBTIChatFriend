package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.model.AgeGroup
import com.example.mbtichatfriend.model.Gender
import com.example.mbtichatfriend.model.MbtiType
import com.example.mbtichatfriend.model.Relationship
import com.example.mbtichatfriend.model.SpeechStyle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val prefs: UserPreferences
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
            onComplete()
        }
    }
}
