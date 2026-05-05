package com.example.mbtichatfriend.ui.diary

// ── 32차 스프린트: 사용자 다이어리 직접 입력 UiState ─────────────────────────

data class DiaryEntryUiState(
    val content: String = "",
    val selectedTags: Set<String> = emptySet(),
    val isSaving: Boolean = false,
    val isSaved: Boolean = false,
    val errorMessage: String? = null
)
