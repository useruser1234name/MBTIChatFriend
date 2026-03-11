package com.example.mbtichatfriend.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.AppNotification
import com.example.mbtichatfriend.data.remote.ChatApi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NotificationViewModel @Inject constructor(
    private val api: ChatApi,
    private val prefs: UserPreferences,
) : ViewModel() {

    private val _notifications = MutableStateFlow<List<AppNotification>>(emptyList())
    val notifications: StateFlow<List<AppNotification>> = _notifications

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading

    fun loadAndMarkRead() {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                val userId = prefs.firebaseUid.first()
                val response = api.getNotifications(userId)
                if (response.isSuccessful) {
                    _notifications.value = response.body() ?: emptyList()
                    // 전체 읽음 처리
                    runCatching { api.markAllRead(userId) }
                }
            } catch (_: Exception) {
                // 오류 시 빈 목록 유지
            } finally {
                _isLoading.value = false
            }
        }
    }
}
