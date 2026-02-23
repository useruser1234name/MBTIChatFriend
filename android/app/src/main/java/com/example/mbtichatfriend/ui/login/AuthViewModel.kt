package com.example.mbtichatfriend.ui.login

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AuthUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val isSignedIn: Boolean = false,
    val isFirebaseAvailable: Boolean = true
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthUiState(
        isFirebaseAvailable = authRepository.isFirebaseAvailable
    ))
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun signInAnonymously() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = authRepository.signInAnonymously()
            result.fold(
                onSuccess = {
                    _uiState.update { it.copy(isLoading = false, isSignedIn = true) }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isLoading = false, error = e.localizedMessage ?: "로그인 실패")
                    }
                }
            )
        }
    }

    fun signInWithGoogle(activityContext: Context) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val result = authRepository.signInWithGoogle(activityContext)
            result.fold(
                onSuccess = {
                    _uiState.update { it.copy(isLoading = false, isSignedIn = true) }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isLoading = false, error = e.localizedMessage ?: "Google 로그인 실패")
                    }
                }
            )
        }
    }

    fun skipAuth() {
        authRepository.skipAuth()
        _uiState.update { it.copy(isSignedIn = true) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
