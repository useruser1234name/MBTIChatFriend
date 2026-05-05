package com.example.mbtichatfriend.ui.community

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.CommunityComment
import com.example.mbtichatfriend.data.remote.CreateCommentRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class PostDetailUiState {
    object Loading : PostDetailUiState()
    data class Success(
        val post: CommunityPostUi,
        val comments: List<CommunityComment>,
    ) : PostDetailUiState()
    data class Error(val message: String) : PostDetailUiState()
}

@HiltViewModel
class PostDetailViewModel @Inject constructor(
    private val api: ChatApi,
    private val prefs: UserPreferences,
) : ViewModel() {

    private val _uiState = MutableStateFlow<PostDetailUiState>(PostDetailUiState.Loading)
    val uiState: StateFlow<PostDetailUiState> = _uiState

    private var currentPostId: Long = -1L

    fun loadPost(postId: Long) {
        currentPostId = postId
        viewModelScope.launch {
            _uiState.value = PostDetailUiState.Loading
            try {
                val postResp = api.getCommunityPosts()
                val commentResp = api.getComments(postId)
                val post = postResp.body()?.find { it.id == postId }?.toUi()
                    ?: return@launch run { _uiState.value = PostDetailUiState.Error("게시글을 찾을 수 없어요") }
                val comments = commentResp.body() ?: emptyList()
                _uiState.value = PostDetailUiState.Success(post, comments)
            } catch (e: Exception) {
                _uiState.value = PostDetailUiState.Error(e.message ?: "오류가 발생했어요")
            }
        }
    }

    fun createComment(content: String) {
        viewModelScope.launch {
            try {
                val userId = prefs.firebaseUid.first().takeIf { it.isNotEmpty() } ?: return@launch
                val userMbti = prefs.userMbti.first().takeIf { it.isNotEmpty() } ?: "MBTI"
                val resp = api.createComment(currentPostId, CreateCommentRequest(userId, userMbti, content))
                if (resp.isSuccessful) {
                    loadPost(currentPostId)
                }
            } catch (e: Exception) { /* 무시 */ }
        }
    }
}
