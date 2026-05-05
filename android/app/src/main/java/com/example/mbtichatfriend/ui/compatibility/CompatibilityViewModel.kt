package com.example.mbtichatfriend.ui.compatibility

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.CompatibilityResult
import com.example.mbtichatfriend.data.remote.ValentineMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class CompatibilityUiState {
    object Loading : CompatibilityUiState()
    data class Success(
        val result: CompatibilityResult,
        val valentineMessage: ValentineMessage? = null,
    ) : CompatibilityUiState()
    data class Error(val message: String) : CompatibilityUiState()
}

@HiltViewModel
class CompatibilityViewModel @Inject constructor(
    private val api: ChatApi,
) : ViewModel() {

    private val _uiState = MutableStateFlow<CompatibilityUiState>(CompatibilityUiState.Loading)
    val uiState: StateFlow<CompatibilityUiState> = _uiState

    fun loadCompatibility(mbtiA: String, mbtiB: String) {
        viewModelScope.launch {
            _uiState.value = CompatibilityUiState.Loading
            try {
                val response = api.getCompatibility(mbtiA, mbtiB)
                if (response.isSuccessful) {
                    _uiState.value = CompatibilityUiState.Success(response.body()!!)
                } else {
                    _uiState.value = CompatibilityUiState.Error("궁합 정보를 불러오지 못했어요")
                }
            } catch (e: Exception) {
                _uiState.value = CompatibilityUiState.Error(e.message ?: "오류가 발생했어요")
            }
        }
    }

    fun loadValentineMessage(myMbti: String) {
        viewModelScope.launch {
            try {
                val valentine = api.getValentineMessage(myMbti)
                val current = _uiState.value
                if (current is CompatibilityUiState.Success) {
                    _uiState.value = current.copy(valentineMessage = valentine)
                }
            } catch (e: Exception) {
                // 발렌타인 메시지 실패는 무시 — 메인 궁합 화면 영향 없음
            }
        }
    }
}
