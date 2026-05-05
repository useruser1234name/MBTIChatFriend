package com.example.mbtichatfriend.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.YearReportResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class YearReportUiState {
    object Loading : YearReportUiState()
    data class Success(val report: YearReportResponse) : YearReportUiState()
    data class Error(val message: String) : YearReportUiState()
}

@HiltViewModel
class YearReportViewModel @Inject constructor(
    private val api: ChatApi,
    private val prefs: UserPreferences,
) : ViewModel() {

    private val _uiState = MutableStateFlow<YearReportUiState>(YearReportUiState.Loading)
    val uiState: StateFlow<YearReportUiState> = _uiState

    init {
        loadReport()
    }

    fun loadReport() {
        viewModelScope.launch {
            _uiState.value = YearReportUiState.Loading
            try {
                val userId = prefs.firebaseUid.first().takeIf { it.isNotEmpty() } ?: run {
                    _uiState.value = YearReportUiState.Error("로그인이 필요합니다")
                    return@launch
                }
                val report = api.getYearReport(userId)
                _uiState.value = YearReportUiState.Success(report)
            } catch (e: Exception) {
                _uiState.value = YearReportUiState.Error(e.message ?: "리포트를 불러올 수 없어요")
            }
        }
    }
}
