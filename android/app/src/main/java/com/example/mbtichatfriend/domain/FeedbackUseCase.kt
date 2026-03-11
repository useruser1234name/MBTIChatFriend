package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 사용자 피드백(좋아요/싫어요) 처리 UseCase.
 * ChatViewModel에서 분리 — 8차 스프린트 기술 부채 해소 (ARCH-C 오세진).
 * 분리 후 ChatViewModel 목표: ≤200줄.
 */
@Singleton
class FeedbackUseCase @Inject constructor(
    private val chatRepository: ChatRepository,
) {
    private val _feedbackMap = MutableStateFlow<Map<Long, String>>(emptyMap())
    val feedbackMap: StateFlow<Map<Long, String>> = _feedbackMap

    suspend fun submitFeedback(
        messageId: Long,
        feedbackType: String,
        characterId: Long,
    ) {
        if (_feedbackMap.value.containsKey(messageId)) return
        _feedbackMap.value = _feedbackMap.value + (messageId to feedbackType)
        runCatching {
            chatRepository.submitFeedback(
                messageId = messageId,
                characterId = characterId,
                feedbackType = feedbackType,
            )
        }
    }

    fun getLocalFeedback(messageId: Long): String? = _feedbackMap.value[messageId]
}
