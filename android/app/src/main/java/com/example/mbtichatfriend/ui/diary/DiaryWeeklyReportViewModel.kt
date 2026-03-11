package com.example.mbtichatfriend.ui.diary

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.remote.ChatApi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── 32차 스프린트: 주간 감정 리포트 ViewModel ─────────────────────────────────

data class DiaryWeeklyReportUiState(
    val emotionCounts: Map<String, Int> = mapOf(
        "\uD83D\uDE0A 기쁨" to 0,
        "\uD83D\uDE14 슬픔" to 0,
        "\uD83D\uDE30 불안" to 0,
        "\uD83D\uDE24 화남" to 0,
        "\uD83E\uDD14 복잡" to 0
    ),
    val weeklySummary: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

@HiltViewModel
class DiaryWeeklyReportViewModel @Inject constructor(
    private val chatApi: ChatApi
) : ViewModel() {

    private val _uiState = MutableStateFlow(DiaryWeeklyReportUiState())
    val uiState: StateFlow<DiaryWeeklyReportUiState> = _uiState.asStateFlow()

    init {
        loadWeeklyReport()
    }

    private fun loadWeeklyReport() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            runCatching {
                val report = chatApi.getDiaryWeeklyReport()
                val emotionMap = linkedMapOf(
                    "\uD83D\uDE0A 기쁨" to (report.emotionCounts["\uD83D\uDE0A 기쁨"] ?: 0),
                    "\uD83D\uDE14 슬픔" to (report.emotionCounts["\uD83D\uDE14 슬픔"] ?: 0),
                    "\uD83D\uDE30 불안" to (report.emotionCounts["\uD83D\uDE30 불안"] ?: 0),
                    "\uD83D\uDE24 화남" to (report.emotionCounts["\uD83D\uDE24 화남"] ?: 0),
                    "\uD83E\uDD14 복잡" to (report.emotionCounts["\uD83E\uDD14 복잡"] ?: 0)
                )
                _uiState.value = DiaryWeeklyReportUiState(
                    emotionCounts = emotionMap,
                    weeklySummary = report.summary,
                    isLoading = false
                )
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = e.message
                )
            }
        }
    }
}
