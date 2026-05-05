package com.example.mbtichatfriend.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.CharacterDao
import com.example.mbtichatfriend.data.local.DiaryDao
import com.example.mbtichatfriend.data.local.FeedbackDao
import com.example.mbtichatfriend.data.local.MemoryDao
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.DeleteConversationRequest
import com.example.mbtichatfriend.data.repository.AuthRepository
import com.example.mbtichatfriend.data.repository.CharacterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val prefs: UserPreferences,
    private val characterRepo: CharacterRepository,
    private val authRepository: AuthRepository,
    private val chatApi: ChatApi,
    private val messageDao: MessageDao,
    private val characterDao: CharacterDao,
    private val memoryDao: MemoryDao,
    private val diaryDao: DiaryDao,
    private val feedbackDao: FeedbackDao
) : ViewModel() {

    private val _deleteResult = MutableStateFlow<String?>(null)
    val deleteResult: StateFlow<String?> = _deleteResult.asStateFlow()

    val characters = characterRepo.observeAll()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun deleteConversationData(characterId: String, characterName: String) {
        viewModelScope.launch {
            val currentNickname = nickname.value
            runCatching {
                chatApi.deleteConversation(
                    DeleteConversationRequest(
                        characterId = characterId,
                        characterName = characterName,
                        nickname = currentNickname
                    )
                )
            }.onSuccess { response ->
                val charIdLong = characterId.toLongOrNull()
                if (charIdLong != null) {
                    messageDao.deleteByCharacter(charIdLong)
                    memoryDao.deleteByCharacter(charIdLong)
                    diaryDao.deleteByCharacter(charIdLong)
                    feedbackDao.deleteByCharacter(charIdLong)
                }
                _deleteResult.value = if (response.cleanupWarnings.isNotEmpty()) {
                    "${characterName}의 대화 데이터가 삭제되었습니다. 추가 점검 ${response.cleanupWarnings.size}건"
                } else {
                    "${characterName}의 대화 데이터가 삭제되었습니다"
                }
            }.onFailure {
                _deleteResult.value = "삭제 실패: ${it.message}"
            }
        }
    }

    fun clearDeleteResult() { _deleteResult.value = null }

    val nickname = prefs.nickname
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val darkMode = prefs.darkMode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "system")

    val authProvider = prefs.authProvider
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "none")

    private val _linkError = MutableStateFlow<String?>(null)
    val linkError: StateFlow<String?> = _linkError.asStateFlow()

    fun updateNickname(newNickname: String) {
        if (newNickname.length in 2..8) {
            viewModelScope.launch {
                prefs.updateNickname(newNickname)
            }
        }
    }

    fun updateDarkMode(mode: String) {
        viewModelScope.launch {
            prefs.updateDarkMode(mode)
        }
    }

    fun linkGoogleAccount(activityContext: Context) {
        viewModelScope.launch {
            val result = authRepository.linkGoogleAccount(activityContext)
            result.onFailure { e ->
                _linkError.value = e.localizedMessage ?: "Google 연동 실패"
            }
        }
    }

    fun clearLinkError() {
        _linkError.value = null
    }

    fun logout(onDone: () -> Unit) {
        viewModelScope.launch {
            messageDao.deleteAll()
            characterDao.deleteAll()
            memoryDao.deleteAll()
            diaryDao.deleteAll()
            feedbackDao.deleteAll()
            authRepository.signOut()
            prefs.clearAll()
            onDone()
        }
    }
}
