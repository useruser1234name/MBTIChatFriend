package com.example.mbtichatfriend.ui.community

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.CreatePostRequest
import com.example.mbtichatfriend.data.remote.EmpathyToggleRequest
import com.example.mbtichatfriend.data.remote.ReportRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlinx.coroutines.flow.map

@HiltViewModel
class CommunityViewModel @Inject constructor(
    private val api: ChatApi,
    private val prefs: UserPreferences,
) : ViewModel() {

    val userId: StateFlow<String> = prefs.firebaseUid
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val userMbti: StateFlow<String> = prefs.userMbti
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val guidelineShown: StateFlow<Boolean> = prefs.isCommunityGuidelineShown
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    private val _uiState = MutableStateFlow<CommunityUiState>(CommunityUiState.Loading)
    val uiState: StateFlow<CommunityUiState> = _uiState

    private var currentMbti: String? = null

    init {
        loadPosts()
        loadPinnedPosts()
    }

    fun loadPosts(mbti: String? = currentMbti) {
        currentMbti = mbti
        viewModelScope.launch {
            _uiState.value = CommunityUiState.Loading
            try {
                val response = api.getCommunityPosts(mbti)
                if (response.isSuccessful) {
                    val posts = response.body()?.map { it.toUi() } ?: emptyList()
                    val currentPinned = (_uiState.value as? CommunityUiState.Success)?.pinnedPosts
                        ?: _pendingPinnedPosts
                    _pendingPinnedPosts = emptyList()
                    _uiState.value = CommunityUiState.Success(
                        posts = posts,
                        selectedMbti = mbti,
                        pinnedPosts = currentPinned,
                    )
                } else {
                    _uiState.value = CommunityUiState.Error("게시글을 불러오지 못했어요")
                }
            } catch (e: Exception) {
                _uiState.value = CommunityUiState.Error(e.message ?: "오류가 발생했어요")
            }
        }
    }

    private fun loadPinnedPosts() {
        viewModelScope.launch {
            runCatching {
                val pinned = api.getPinnedPosts().map { it.toUi() }
                val current = _uiState.value
                if (current is CommunityUiState.Success) {
                    _uiState.value = current.copy(pinnedPosts = pinned)
                } else {
                    // 일반 목록 로드 전에 고정 공지가 먼저 도착한 경우 임시 보관
                    _pendingPinnedPosts = pinned
                }
            }.onFailure { e ->
                android.util.Log.w("CommunityViewModel", "고정 공지 로드 실패", e)
            }
        }
    }

    private var _pendingPinnedPosts: List<CommunityPostUi> = emptyList()

    fun filterByMbti(mbti: String?) {
        loadPosts(mbti)
    }

    fun toggleEmpathy(postId: Long, userId: String) {
        viewModelScope.launch {
            try {
                val response = api.toggleEmpathy(postId, EmpathyToggleRequest(userId))
                if (response.isSuccessful) {
                    val empathized = response.body()?.empathized ?: return@launch
                    val state = _uiState.value
                    if (state is CommunityUiState.Success) {
                        _uiState.value = state.copy(
                            posts = state.posts.map { post ->
                                if (post.id == postId) post.copy(
                                    isEmpathized = empathized,
                                    empathyCount = if (empathized) post.empathyCount + 1 else post.empathyCount - 1,
                                ) else post
                            }
                        )
                    }
                }
            } catch (e: Exception) { /* 무시 */ }
        }
    }

    fun createPost(userId: String, mbti: String, content: String, onSuccess: () -> Unit) {
        viewModelScope.launch {
            try {
                val response = api.createPost(CreatePostRequest(userId, mbti, content))
                if (response.isSuccessful) {
                    loadPosts()
                    onSuccess()
                }
            } catch (e: Exception) { /* 무시 */ }
        }
    }

    fun reportPost(postId: Long, reason: String) {
        viewModelScope.launch {
            try {
                api.reportPost(postId, ReportRequest(reason))
            } catch (e: Exception) { /* 무시 */ }
        }
    }

    fun markGuidelineShown() {
        viewModelScope.launch {
            prefs.setCommunityGuidelineShown(true)
        }
    }
}
