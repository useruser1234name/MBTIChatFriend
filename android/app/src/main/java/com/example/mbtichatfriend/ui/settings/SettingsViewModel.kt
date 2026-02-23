package com.example.mbtichatfriend.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.repository.AuthRepository
import com.example.mbtichatfriend.data.repository.CharacterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val prefs: UserPreferences,
    private val characterRepo: CharacterRepository,
    private val authRepository: AuthRepository
) : ViewModel() {

    val nickname = prefs.nickname
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val darkMode = prefs.darkMode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "system")

    val authProvider = prefs.authProvider
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "none")

    private val _linkError = MutableStateFlow<String?>(null)
    val linkError: StateFlow<String?> = _linkError.asStateFlow()

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
