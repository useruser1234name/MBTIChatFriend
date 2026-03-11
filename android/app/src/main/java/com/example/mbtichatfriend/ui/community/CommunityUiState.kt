package com.example.mbtichatfriend.ui.community

import com.example.mbtichatfriend.data.remote.CommunityPost

sealed class CommunityUiState {
    object Loading : CommunityUiState()
    data class Success(
        val posts: List<CommunityPostUi>,
        val selectedMbti: String?,
        val isFirstVisit: Boolean = false,
        val pinnedPosts: List<CommunityPostUi> = emptyList(),
    ) : CommunityUiState()
    data class Error(val message: String) : CommunityUiState()
}

data class CommunityPostUi(
    val id: Long,
    val mbti: String,
    val content: String,
    val anonymousName: String,
    val empathyCount: Int,
    val createdAt: String,
    val isEmpathized: Boolean = false,
    val commentCount: Int = 0,
)

fun CommunityPost.toUi() = CommunityPostUi(
    id = id,
    mbti = mbti,
    content = content,
    anonymousName = anonymousName,
    empathyCount = empathyCount,
    createdAt = createdAt,
    commentCount = commentCount,
)
