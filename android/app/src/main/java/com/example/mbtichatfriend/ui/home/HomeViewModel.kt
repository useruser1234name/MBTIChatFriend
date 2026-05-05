package com.example.mbtichatfriend.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageSetRequest
import com.example.mbtichatfriend.data.remote.MoodCheckinApiRequest
import com.example.mbtichatfriend.data.repository.CharacterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
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

    val todayMood = prefs.todayMood
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private val _moodResponse = MutableStateFlow<String?>(null)
    val moodResponse = _moodResponse.asStateFlow()

    fun dismissMoodResponse() {
        _moodResponse.value = null
    }

    init {
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

    fun selectMood(mood: String) {
        viewModelScope.launch {
            prefs.updateTodayMood(mood)
            try {
                val nick = prefs.nickname.first()
                val chars = characters.value
                val lastMsgMap = _lastMessages.value
                val activeChar = if (lastMsgMap.isNotEmpty()) {
                    val mostRecentId = lastMsgMap.maxByOrNull { it.value.timestamp }?.key
                    chars.firstOrNull { it.id == mostRecentId } ?: chars.firstOrNull()
                } else {
                    chars.firstOrNull()
                }
                val response = chatApi.moodCheckin(
                    MoodCheckinApiRequest(
                        mood = mood,
                        characterId = activeChar?.id?.toString() ?: "",
                        characterName = activeChar?.name ?: "",
                        mbti = activeChar?.mbti ?: "",
                        nickname = nick
                    )
                )
                _moodResponse.value = response.message
            } catch (_: Exception) {
                // Mood check-in should not block local mood persistence.
            }
        }
    }

    fun createCharacter(
        name: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        avatarId: String,
        personaRaw: String = "",
        revisedPrompt: String? = null,
        onCreated: (Long) -> Unit
    ) {
        viewModelScope.launch {
            val safeVisualPrompt = revisedPrompt ?: personaRaw
            val id = characterRepo.create(
                name = name,
                mbti = mbti,
                speechStyle = speechStyle,
                relationship = relationship,
                avatarId = avatarId,
                personaRaw = personaRaw,
                visualPrompt = safeVisualPrompt
            )

            if (avatarId.startsWith("img:") && safeVisualPrompt.isNotBlank()) {
                try {
                    val response = chatApi.generateImageSet(
                        ImageSetRequest(
                            basePrompt = safeVisualPrompt,
                            characterId = id.toString()
                        )
                    )
                    prefs.setExpressionSetTaskId(id, response.taskId)
                } catch (e: Exception) {
                    android.util.Log.w("HomeViewModel", "Expression set generation start failed", e)
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
