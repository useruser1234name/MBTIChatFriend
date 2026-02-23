package com.example.mbtichatfriend.ui.diary

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.DiaryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DiaryViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val diaryRepo: DiaryRepository,
    private val characterRepo: CharacterRepository,
    private val chatRepo: ChatRepository,
    private val prefs: UserPreferences
) : ViewModel() {

    val characterId: Long = savedStateHandle.get<String>("characterId")?.toLongOrNull() ?: 0L

    val character = characterRepo.observeById(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val diaries = diaryRepo.observeDiaries(characterId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    var isGenerating by mutableStateOf(false)
        private set

    var errorMessage by mutableStateOf<String?>(null)
        private set

    fun dismissError() {
        errorMessage = null
    }

    fun generateTodayDiary() {
        viewModelScope.launch {
            isGenerating = true
            errorMessage = null

            val ch = characterRepo.getById(characterId) ?: run {
                isGenerating = false
                errorMessage = "캐릭터 정보를 불러올 수 없어요."
                return@launch
            }

            val nickname = prefs.nickname.first()

            val recentMessages = chatRepo.observeMessages(characterId).first()
                .takeLast(30)
                .map { entity ->
                    mapOf(
                        "role" to if (entity.isFromUser) "user" else "assistant",
                        "content" to entity.text
                    )
                }

            val result = diaryRepo.generateDiary(
                characterId = characterId,
                characterName = ch.name,
                mbti = ch.mbti,
                speechStyle = ch.speechStyle,
                nickname = nickname,
                affinityLevel = ch.affinityLevel,
                conversationHistory = recentMessages
            )

            if (result.diary.contains("나중에 다시 써야겠다")) {
                errorMessage = "일기 생성에 실패했어요. 서버 연결을 확인해주세요."
            }

            isGenerating = false
        }
    }
}
