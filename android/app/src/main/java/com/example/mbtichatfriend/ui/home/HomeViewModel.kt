package com.example.mbtichatfriend.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageSetRequest
import com.example.mbtichatfriend.data.repository.CharacterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LastMessageInfo(
    val text: String,
    val timestamp: Long,
    val isFromUser: Boolean
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val characterRepo: CharacterRepository,
    private val messageDao: MessageDao,
    private val prefs: UserPreferences,
    val chatApi: ChatApi
) : ViewModel() {

    val characters = characterRepo.observeAll()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val nickname = prefs.nickname
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    private val _lastMessages = MutableStateFlow<Map<Long, LastMessageInfo>>(emptyMap())
    val lastMessages = _lastMessages.asStateFlow()

    init {
        // 캐릭터가 없으면 프리셋 자동 생성
        viewModelScope.launch {
            characterRepo.seedPresetsIfEmpty()
        }

        viewModelScope.launch {
            characters.collect { _ ->
                val lastMsgs = messageDao.getLastMessagePerCharacter()
                val map = lastMsgs.associate { msg ->
                    msg.characterId to LastMessageInfo(
                        text = msg.text,
                        timestamp = msg.createdAt,
                        isFromUser = msg.isFromUser
                    )
                }
                _lastMessages.value = map
            }
        }
    }

    fun createCharacter(
        name: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        avatarId: String,
        revisedPrompt: String? = null,
        onCreated: (Long) -> Unit
    ) {
        viewModelScope.launch {
            val id = characterRepo.create(name, mbti, speechStyle, relationship, avatarId)

            // img: 캐릭터이고 revisedPrompt가 있으면 표정 세트 백그라운드 생성 시작
            if (avatarId.startsWith("img:") && revisedPrompt != null) {
                launch {
                    try {
                        val response = chatApi.generateImageSet(
                            ImageSetRequest(
                                basePrompt = revisedPrompt,
                                characterId = id.toString()
                            )
                        )
                        // taskId를 SharedPreferences에 저장하여 ChatViewModel에서 폴링
                        prefs.setExpressionSetTaskId(id, response.taskId)
                    } catch (e: Exception) {
                        android.util.Log.w("HomeViewModel", "Expression set generation start failed", e)
                    }
                }
            }

            onCreated(id)
        }
    }

    fun deleteCharacter(id: Long) {
        viewModelScope.launch {
            characterRepo.delete(id)
        }
    }
}
