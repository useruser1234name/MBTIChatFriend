package com.example.mbtichatfriend.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── 36차 스프린트: 언어 설정 ViewModel ────────────────────────────────────────

@HiltViewModel
class LanguageSettingViewModel @Inject constructor(
    private val prefs: UserPreferences
) : ViewModel() {

    val languageCode: StateFlow<String> = prefs.languageCode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "ko")

    fun updateLanguage(code: String) {
        viewModelScope.launch {
            prefs.setLanguageCode(code)
        }
    }
}
