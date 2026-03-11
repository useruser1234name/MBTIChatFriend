package com.example.mbtichatfriend.ui.diary

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.DiaryEntryRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── 32차 스프린트: 사용자 직접 입력 다이어리 ViewModel ────────────────────────

@HiltViewModel
class DiaryEntryViewModel @Inject constructor(
    private val chatApi: ChatApi
) : ViewModel() {

    private val _uiState = MutableStateFlow(DiaryEntryUiState())
    val uiState: StateFlow<DiaryEntryUiState> = _uiState.asStateFlow()

    fun toggleTag(tag: String) {
        _uiState.update { state ->
            val newTags = if (state.selectedTags.contains(tag)) {
                state.selectedTags - tag
            } else {
                state.selectedTags + tag
            }
            state.copy(selectedTags = newTags)
        }
    }

    fun updateContent(content: String) {
        _uiState.update { it.copy(content = content) }
    }

    fun saveDiary() {
        val state = _uiState.value
        if (state.content.isBlank()) return

        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true, errorMessage = null) }
            runCatching {
                chatApi.createDiaryEntry(
                    DiaryEntryRequest(
                        content = state.content,
                        tags = state.selectedTags.toList()
                    )
                )
                _uiState.update { it.copy(isSaving = false, isSaved = true) }
            }.onFailure { e ->
                _uiState.update {
                    it.copy(isSaving = false, errorMessage = e.message ?: "저장에 실패했어요.")
                }
            }
        }
    }
}
